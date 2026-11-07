"""Repositorios y Unit of Work de administración (C-15, tarea 3).

Contra PostgreSQL real: `get_abierta`, `listar_por_usuario`,
`contar_admins_vigentes`, `cerrar` y `abrir`. Los repositorios sólo hacen
`flush()`, nunca `commit()` (CV-02); `selectinload` no se usa aquí (CV-03).
"""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usuarios.models import AsignacionRol, Usuario
from app.modules.usuarios.repository import (
    AbiertaRol,
    AsignacionRolRepository,
)
from app.modules.usuarios.unit_of_work import (
    AdminUnitOfWork,
    get_admin_uow,
)

pytestmark = pytest.mark.asyncio


async def _crear_usuario(session: AsyncSession, email: str) -> Usuario:
    u = Usuario(
        email=email,
        nombre="Usuario repo",
        password_hash="$2b$12$x",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u)
    await session.flush()
    return u


async def _crear_asignacion(
    session: AsyncSession,
    usuario_id: int,
    rol: str,
    *,
    desde=None,
    vence_en=None,
    revocada_en=None,
    otorgada_por=None,
) -> AsignacionRol:
    a = AsignacionRol(
        usuario_id=usuario_id,
        rol=rol,
        desde=desde or datetime.now(timezone.utc),
        vence_en=vence_en,
        revocada_en=revocada_en,
        otorgada_por=otorgada_por,
    )
    session.add(a)
    await session.flush()
    return a


async def _limpiar(session: AsyncSession, *usuario_ids: int) -> None:
    for usuario_id in usuario_ids:
        await session.execute(
            delete(AsignacionRol).where(AsignacionRol.usuario_id == usuario_id)
        )
        await session.execute(delete(Usuario).where(Usuario.id == usuario_id))
    await session.commit()


# --- get_abierta ---


async def test_get_abierta_vigente_cuando_vence_en_nulo(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-vigente-nulo@example.com")
            await _crear_asignacion(session, u.id, "ADMIN")
            repo = AsignacionRolRepository(session)
            abierta = await repo.get_abierta(u.id, "ADMIN")
            assert isinstance(abierta, AbiertaRol)
            assert abierta.vigente is True
            assert abierta.asignacion.rol == "ADMIN"
        finally:
            await _limpiar(session, u.id)


async def test_get_abierta_vigente_cuando_vence_en_futuro(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-vigente-futuro@example.com")
            await _crear_asignacion(
                session,
                u.id,
                "VENDEDOR",
                vence_en=datetime.now(timezone.utc) + timedelta(days=1),
            )
            repo = AsignacionRolRepository(session)
            abierta = await repo.get_abierta(u.id, "VENDEDOR")
            assert abierta is not None
            assert abierta.vigente is True
        finally:
            await _limpiar(session, u.id)


async def test_get_abierta_no_vigente_cuando_vence_en_pasado(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-vencido@example.com")
            await _crear_asignacion(
                session,
                u.id,
                "ADMIN",
                vence_en=datetime.now(timezone.utc) - timedelta(days=1),
            )
            repo = AsignacionRolRepository(session)
            abierta = await repo.get_abierta(u.id, "ADMIN")
            assert abierta is not None
            assert abierta.vigente is False
        finally:
            await _limpiar(session, u.id)


async def test_get_abierta_ignora_fila_revocada(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-revocada@example.com")
            await _crear_asignacion(
                session, u.id, "ADMIN", revocada_en=datetime.now(timezone.utc)
            )
            repo = AsignacionRolRepository(session)
            assert await repo.get_abierta(u.id, "ADMIN") is None
        finally:
            await _limpiar(session, u.id)


async def test_get_abierta_sin_filas_devuelve_none(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-sin-filas@example.com")
            repo = AsignacionRolRepository(session)
            assert await repo.get_abierta(u.id, "ADMIN") is None
        finally:
            await _limpiar(session, u.id)


# --- listar_por_usuario ---


async def test_listar_por_usuario_incluye_todas_ordenadas_desc(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-historial@example.com")
            ahora = datetime.now(timezone.utc)
            await _crear_asignacion(session, u.id, "VENDEDOR", desde=ahora - timedelta(days=2))
            await _crear_asignacion(session, u.id, "ADMIN", desde=ahora - timedelta(days=1))
            await _crear_asignacion(
                session, u.id, "CLIENTE", revocada_en=ahora, desde=ahora
            )
            repo = AsignacionRolRepository(session)
            filas = await repo.listar_por_usuario(u.id)
            assert len(filas) == 3
            assert [f.rol for f in filas] == ["CLIENTE", "ADMIN", "VENDEDOR"]
            assert filas[0].desde >= filas[1].desde >= filas[2].desde
        finally:
            await _limpiar(session, u.id)


async def test_listar_por_usuario_vacio_si_no_hay_asignaciones(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-vacio@example.com")
            repo = AsignacionRolRepository(session)
            assert await repo.listar_por_usuario(u.id) == []
        finally:
            await _limpiar(session, u.id)


# --- contar_admins_vigentes ---


async def test_contar_admins_vigentes_solo_vigentes(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            ids = []
            asignacion_ids = []
            ahora = datetime.now(timezone.utc)
            repo = AsignacionRolRepository(session)
            # Contar admins vigentes preexistentes para aislar el test
            base = await repo.contar_admins_vigentes()
            for correo in (
                f"rep-a1-{uuid.uuid4().hex}@example.com",
                f"rep-a2-{uuid.uuid4().hex}@example.com",
                f"rep-a3-{uuid.uuid4().hex}@example.com",
            ):
                u = await _crear_usuario(session, correo)
                ids.append(u.id)
            asignacion_ids.append((await _crear_asignacion(session, ids[0], "ADMIN", desde=ahora)).id)  # vigente
            asignacion_ids.append((await _crear_asignacion(session, ids[1], "ADMIN", desde=ahora)).id)  # vigente
            await _crear_asignacion(
                session, ids[2], "ADMIN", desde=ahora,
                vence_en=ahora - timedelta(days=1),  # vencida -> no cuenta
            )
            assert await repo.contar_admins_vigentes() == base + 2
            assert await repo.contar_admins_vigentes(excluir_id=asignacion_ids[0]) == base + 1
        finally:
            async with db_sessionmaker() as limpieza:
                await _limpiar(limpieza, *ids)


async def test_contar_admins_vigentes_no_cuenta_revocadas(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            ids = []
            ahora = datetime.now(timezone.utc)
            repo = AsignacionRolRepository(session)
            # Contar admins vigentes preexistentes para aislar el test
            base = await repo.contar_admins_vigentes()
            for correo in (
                f"rep-a4-{uuid.uuid4().hex}@example.com",
                f"rep-a5-{uuid.uuid4().hex}@example.com",
            ):
                u = await _crear_usuario(session, correo)
                ids.append(u.id)
            await _crear_asignacion(session, ids[0], "ADMIN", desde=ahora)  # vigente
            await _crear_asignacion(
                session, ids[1], "ADMIN", desde=ahora, revocada_en=ahora
            )  # revocada -> no cuenta
            assert await repo.contar_admins_vigentes() == base + 1
        finally:
            async with db_sessionmaker() as limpieza:
                await _limpiar(limpieza, *ids)


# --- cerrar / abrir ---


async def test_cerrar_escribe_revocada_en_y_hace_flush(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-cerrar@example.com")
            a = AsignacionRol(
                usuario_id=u.id,
                rol="ADMIN",
                desde=datetime.now(timezone.utc),
            )
            session.add(a)
            assert a.id is None  # aún no se hizo flush
            repo = AsignacionRolRepository(session)
            await repo.cerrar(a)
            assert a.id is not None  # flush asignó el id
            assert a.revocada_en is not None
            assert a.revocada_en.tzinfo is not None
        finally:
            await _limpiar(session, u.id)


async def test_abrir_agrega_asignacion_y_hace_flush(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-abrir@example.com")
            repo = AsignacionRolRepository(session)
            a = await repo.abrir(u.id, "VENDEDOR", vence_en=None, otorgada_por=u.id)
            assert a.id is not None  # flush asignó el id
            assert a.usuario_id == u.id
            assert a.rol == "VENDEDOR"
            assert a.revocada_en is None
            assert a.desde.tzinfo is not None
            # Queda abierta y vigente
            abierta = await repo.get_abierta(u.id, "VENDEDOR")
            assert abierta is not None
            assert abierta.vigente is True
        finally:
            await _limpiar(session, u.id)


# --- AdminUnitOfWork ---


async def test_admin_uow_comparte_sesion_entre_repositorios(db_sessionmaker):
    async with db_sessionmaker() as session:
        try:
            u = await _crear_usuario(session, "rep-uow@example.com")
            uow = AdminUnitOfWork(session)
            assert uow.usuarios._session is session
            assert uow.roles._session is session
            assert uow.eventos._session is session
            assert uow.session is session
        finally:
            await _limpiar(session, u.id)


async def test_get_admin_uow_devuelve_admin_unit_of_work():
    from types import SimpleNamespace

    session = SimpleNamespace()
    uow = await get_admin_uow(session)
    assert isinstance(uow, AdminUnitOfWork)
    assert uow.session is session
