"""Pruebas de PostgreSQL real para el repositorio/UoW de usuarios (C-11, 2.1)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.usuarios.models import AsignacionRol, IntentoAcceso
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

pytestmark = pytest.mark.asyncio


def _hace(segundos: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=segundos)


async def test_busca_usuario_por_email_y_carga_solo_roles_vigentes(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    async with db_sessionmaker() as session:
        session.add(
            AsignacionRol(
                usuario_id=usuario.id,
                rol="CLIENTE",
                desde=_hace(120),
                revocada_en=_hace(60),
            )
        )
        session.add(
            AsignacionRol(
                usuario_id=usuario.id,
                rol="VENDEDOR",
                desde=_hace(120),
                vence_en=_hace(1),
            )
        )
        await session.commit()

    async with db_sessionmaker() as session:
        uow = UsuariosUnitOfWork(session)
        async with uow:
            encontrado = await uow.usuarios.get_by_email(usuario.email)
            assert encontrado is not None
            assert encontrado.id == usuario.id
            assert await uow.usuarios.get_by_email("no-existe@example.com") is None

            roles = await uow.usuarios.roles_vigentes(usuario.id)
            assert roles == ["ADMIN"]

            por_id = await uow.usuarios.get_by_id(usuario.id)
            assert por_id is not None
            assert por_id.email == usuario.email


async def test_conteo_de_fallos_ignora_exitos_ventana_y_fallos_previos_al_ultimo_exito(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    principal = await usuario_factory()
    otro = await usuario_factory()
    ip = "203.0.113.10"

    async with db_sessionmaker() as session:
        session.add_all(
            [
                # Éxito antiguo que habilita un fallo dentro de la ventana pero
                # anterior al último éxito: no debe contar.
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=True, cuando=_hace(200)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(120)
                ),
                # Último éxito del par: corta la cuenta de fallos anteriores.
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=True, cuando=_hace(50)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(55)
                ),
                # Cinco fallos contabilizables.
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(40)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(30)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(20)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(10)
                ),
                IntentoAcceso(
                    email=principal.email, ip=ip, exito=False, cuando=_hace(5)
                ),
                # Otro email y otra IP no contaminan el conteo.
                IntentoAcceso(
                    email=otro.email, ip=ip, exito=False, cuando=_hace(10)
                ),
                IntentoAcceso(
                    email=principal.email,
                    ip="198.51.100.7",
                    exito=False,
                    cuando=_hace(10),
                ),
            ]
        )
        await session.commit()

    async with db_sessionmaker() as session:
        uow = UsuariosUnitOfWork(session)
        async with uow:
            resumen = await uow.intentos.resumen_fallos(
                principal.email, ip, ventana_segundos=60
            )

    assert resumen.cantidad == 5
    assert resumen.primer_fallo is not None
    assert abs((datetime.now(timezone.utc) - resumen.primer_fallo).total_seconds() - 40) < 5


async def test_conteo_sin_exitos_previos_toma_los_fallos_de_la_ventana(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    usuario = await usuario_factory()
    ip = "203.0.113.20"

    async with db_sessionmaker() as session:
        session.add_all(
            [
                IntentoAcceso(
                    email=usuario.email, ip=ip, exito=False, cuando=_hace(90)
                ),
                IntentoAcceso(
                    email=usuario.email, ip=ip, exito=False, cuando=_hace(30)
                ),
                IntentoAcceso(
                    email=usuario.email, ip=ip, exito=False, cuando=_hace(10)
                ),
            ]
        )
        await session.commit()

    async with db_sessionmaker() as session:
        uow = UsuariosUnitOfWork(session)
        async with uow:
            resumen = await uow.intentos.resumen_fallos(
                usuario.email, ip, ventana_segundos=60
            )

    assert resumen.cantidad == 2
    assert resumen.primer_fallo is not None


@pytest.mark.parametrize("ventana", [60, 1])
async def test_conteo_respeta_la_ventana_configurada(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    usuario_factory,
    ventana: int,
) -> None:
    usuario = await usuario_factory()
    ip = "203.0.113.30"

    async with db_sessionmaker() as session:
        antiguedad = ventana + 5
        session.add(
            IntentoAcceso(
                email=usuario.email, ip=ip, exito=False, cuando=_hace(antiguedad)
            )
        )
        await session.commit()

    async with db_sessionmaker() as session:
        uow = UsuariosUnitOfWork(session)
        async with uow:
            resumen = await uow.intentos.resumen_fallos(
                usuario.email, ip, ventana_segundos=ventana
            )

    assert resumen.cantidad == 0
    assert resumen.primer_fallo is None
