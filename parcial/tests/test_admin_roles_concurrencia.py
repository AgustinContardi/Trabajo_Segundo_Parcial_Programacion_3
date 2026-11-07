"""Concurrencia de `RN-05` contra PostgreSQL real (C-15, tarea 5.6).

Dos sesiones revocan simultáneamente los dos últimos `ADMIN` vigentes: el
`SELECT ... FOR UPDATE` de `contar_admins_vigentes(bloquear=True)` serializa
las operaciones, de modo que una revocación gana y la otra termina en 409.
Siempre queda exactamente un administrador vigente.
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.modules.usuarios import service
from app.modules.usuarios.repository import AsignacionRolRepository
from app.modules.usuarios.unit_of_work import AdminUnitOfWork

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


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
