"""Concurrencia de `RN-05` contra PostgreSQL real (C-15, tarea 5.6).

Dos sesiones revocan simultáneamente los dos últimos `ADMIN` vigentes: el
`SELECT ... FOR UPDATE` de `contar_admins_vigentes(bloquear=True)` serializa
las operaciones, de modo que una revocación gana y la otra termina en 409.
Siempre queda exactamente un administrador vigente.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

from app.modules.usuarios import service
from app.modules.usuarios.models import AsignacionRol
from app.modules.usuarios.repository import AsignacionRolRepository
from app.modules.usuarios.unit_of_work import AdminUnitOfWork

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def _cerrar_admins_existentes(db_sessionmaker) -> list[int]:
    """Cierra temporalmente los `ADMIN` vigentes para aislar el escenario.

    El seed de C-17 deja `admin` y `admin2` con rol `ADMIN` (lo exige el PDF),
    así que «los dos últimos administradores» de esta prueba tienen que ser los
    que crea la propia prueba. Se cierran por SQL —sin pasar por el servicio,
    que rechazaría dejar cero administradores— y se restauran en `finally`.
    """
    async with db_sessionmaker() as session:
        ids = list(
            (
                await session.execute(
                    select(AsignacionRol.id).where(
                        AsignacionRol.rol == "ADMIN",
                        AsignacionRol.revocada_en.is_(None),
                    )
                )
            ).scalars()
        )
        if ids:
            await session.execute(
                update(AsignacionRol)
                .where(AsignacionRol.id.in_(ids))
                .values(revocada_en=datetime.now(timezone.utc))
            )
        await session.commit()
    return ids


async def _restaurar_admins(db_sessionmaker, ids: list[int]) -> None:
    """Reabre las asignaciones que `_cerrar_admins_existentes` cerró."""
    if not ids:
        return
    async with db_sessionmaker() as session:
        await session.execute(
            update(AsignacionRol)
            .where(AsignacionRol.id.in_(ids))
            .values(revocada_en=None)
        )
        await session.commit()


async def _revocar(db_sessionmaker, actor, objetivo_id: int) -> int:
    async with db_sessionmaker() as session:
        uow = AdminUnitOfWork(session)
        try:
            await service.revocar_rol(uow, objetivo_id, "ADMIN", admin=actor)
            return 200
        except HTTPException as exc:
            return exc.status_code


async def test_dos_revocaciones_concurrentes_de_los_ultimos_admins_serializan(
    db_sessionmaker,
    usuario_factory,
) -> None:
    admins_previos = await _cerrar_admins_existentes(db_sessionmaker)
    try:
        async with db_sessionmaker() as session:
            base = await AsignacionRolRepository(session).contar_admins_vigentes()
        assert base == 0, (
            "El test de concurrencia necesita la base de pruebas sin ADMIN "
            f"vigentes; encontró {base}"
        )

        admin_a = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
        admin_b = await usuario_factory(password=PASSWORD, roles=("ADMIN",))

        resultados = await asyncio.gather(
            _revocar(db_sessionmaker, admin_a, admin_b.id),
            _revocar(db_sessionmaker, admin_b, admin_a.id),
        )

        assert sorted(resultados) == [200, 409], resultados

        async with db_sessionmaker() as session:
            repo = AsignacionRolRepository(session)
            vigentes = await repo.contar_admins_vigentes()
            filas = await repo.listar_por_usuario(admin_a.id)
            filas += await repo.listar_por_usuario(admin_b.id)

        assert vigentes == 1
        assert len([f for f in filas if f.revocada_en is not None]) == 1
    finally:
        await _restaurar_admins(db_sessionmaker, admins_previos)
