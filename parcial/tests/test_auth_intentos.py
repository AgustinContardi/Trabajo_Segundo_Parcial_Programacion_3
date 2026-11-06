"""Registro de intentos en sesión y transacción propias (C-11, 2.2)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.usuarios.models import IntentoAcceso
from app.modules.usuarios.service import registrar_intento_acceso
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork
from tests.conftest import contar_intentos

pytestmark = pytest.mark.asyncio


async def test_intento_fallido_sobrevive_al_rollback_del_login(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    usuario = await usuario_factory()
    ip = "203.0.113.41"

    with pytest.raises(RuntimeError, match="falla posterior"):
        async with db_sessionmaker() as session:
            uow = UsuariosUnitOfWork(session)
            async with uow:
                await registrar_intento_acceso(
                    db_sessionmaker, email=usuario.email, ip=ip, exito=False
                )
                # Simula el 401 o un error después de registrar el intento:
                # el UoW revierte su transacción de lectura/login.
                raise RuntimeError("falla posterior")

    async with db_sessionmaker() as session:
        filas = list(
            (
                await session.execute(
                    select(IntentoAcceso).where(IntentoAcceso.email == usuario.email)
                )
            ).scalars()
        )

    assert len(filas) == 1
    assert filas[0].ip == ip
    assert filas[0].exito is False
    assert filas[0].cuando is not None
    assert filas[0].cuando.tzinfo is not None


async def test_intento_exitoso_se_confirma_con_su_propio_commit(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    usuario = await usuario_factory()
    ip = "203.0.113.42"

    await registrar_intento_acceso(
        db_sessionmaker, email=usuario.email, ip=ip, exito=True
    )

    async with db_sessionmaker() as session:
        fila = (
            await session.execute(
                select(IntentoAcceso).where(IntentoAcceso.email == usuario.email)
            )
        ).scalars().one()

    assert fila.exito is True
    assert fila.ip == ip
    assert abs((datetime.now(timezone.utc) - fila.cuando).total_seconds()) < 5


async def test_cada_llamada_deja_su_propia_fila(
    db_sessionmaker: async_sessionmaker[AsyncSession], usuario_factory
) -> None:
    usuario = await usuario_factory()
    ip = "203.0.113.43"

    await registrar_intento_acceso(
        db_sessionmaker, email=usuario.email, ip=ip, exito=False
    )
    await registrar_intento_acceso(
        db_sessionmaker, email=usuario.email, ip=ip, exito=False
    )

    assert await contar_intentos(db_sessionmaker, usuario.email) == 2
