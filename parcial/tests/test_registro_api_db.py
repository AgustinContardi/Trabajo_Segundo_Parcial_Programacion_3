"""Integración de `POST /auth/registro` con PostgreSQL real (C-12, §5).

Complementa `test_registro_api.py` (dobles en memoria): acá se usa la
aplicación real con su `lifespan`, `Settings` del entorno y la base
`libreria`, y se verifican los efectos con `SELECT`/`count(*)`, no con listas
en memoria. Nunca SQLite (regla del proyecto).

Cada prueba registra los emails que usa y el teardown borra sólo esas filas,
en orden de FK: `asignacion_rol` → `cliente` → `usuario`. Así la suite puede
correrse dos veces seguidas con el mismo resultado (§5.6).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, Usuario
from tests.conftest import email_unico

pytestmark = pytest.mark.asyncio

NOMBRE = "Ana Pérez"
PASSWORD = "clave-segura-123"

CAMPOS_RESPUESTA = {
    "id",
    "email",
    "nombre",
    "activo",
    "debe_cambiar_password",
}


def _cuerpo(email: str, *, nombre: str = NOMBRE, **extra: object) -> dict[str, object]:
    cuerpo: dict[str, object] = {
        "email": email,
        "nombre": nombre,
        "password": PASSWORD,
    }
    cuerpo.update(extra)
    return cuerpo


@pytest_asyncio.fixture
async def limpiar_registros(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Callable[[str], None]]:
    """Registra emails creados por la prueba y los borra al terminar."""
    emails: list[str] = []

    def registrar(email: str) -> None:
        emails.append(email)

    yield registrar

    if not emails:
        return
    async with db_sessionmaker() as session:
        ids = list(
            (
                await session.execute(
                    select(Usuario.id).where(Usuario.email.in_(emails))
                )
            ).scalars()
        )
        if ids:
            await session.execute(
                delete(AsignacionRol).where(AsignacionRol.usuario_id.in_(ids))
            )
            await session.execute(
                delete(AsignacionRol).where(AsignacionRol.otorgada_por.in_(ids))
            )
        await session.execute(
            delete(Cliente).where(
                or_(
                    Cliente.email.in_(emails),
                    Cliente.usuario_id.in_(ids or [-1]),
                )
            )
        )
        await session.execute(delete(Usuario).where(Usuario.email.in_(emails)))
        await session.commit()


async def contar_tres(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> tuple[int, int, int]:
    """`(count(usuario), count(asignacion_rol), count(cliente))` reales."""
    async with sessionmaker() as session:
        usuarios = int(
            (await session.execute(select(func.count()).select_from(Usuario))).scalar_one()
        )
        roles = int(
            (
                await session.execute(
                    select(func.count()).select_from(AsignacionRol)
                )
            ).scalar_one()
        )
        clientes = int(
            (await session.execute(select(func.count()).select_from(Cliente))).scalar_one()
        )
    return usuarios, roles, clientes


async def _usuario_por_email(
    sessionmaker: async_sessionmaker[AsyncSession], email: str
) -> Usuario | None:
    async with sessionmaker() as session:
        return (
            await session.execute(select(Usuario).where(Usuario.email == email))
        ).scalars().first()


# ---------------------------------------------------------------------------
# 5.1 Alta válida contra PostgreSQL real
# ---------------------------------------------------------------------------


async def test_registro_alta_valida_en_postgresql_crea_tres_filas(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    limpiar_registros,
) -> None:
    email = email_unico("c12-alta")
    limpiar_registros(email)

    respuesta = await api_client.post("/auth/registro", json=_cuerpo(email))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_RESPUESTA
    assert cuerpo["email"] == email
    assert cuerpo["nombre"] == NOMBRE
    assert cuerpo["activo"] is True
    assert cuerpo["debe_cambiar_password"] is False
    assert "password_hash" not in respuesta.text
    assert PASSWORD not in respuesta.text
    assert respuesta.headers.get_list("set-cookie") == []

    usuario = await _usuario_por_email(db_sessionmaker, email)
    assert usuario is not None
    assert usuario.password_hash.startswith("$2b$")
    assert usuario.password_hash != PASSWORD

    async with db_sessionmaker() as session:
        asignaciones = list(
            (
                await session.execute(
                    select(AsignacionRol).where(
                        AsignacionRol.usuario_id == usuario.id
                    )
                )
            ).scalars()
        )
        ficha = (
            await session.execute(
                select(Cliente).where(Cliente.email == email)
            )
        ).scalars().first()

    assert len(asignaciones) == 1
    asignacion = asignaciones[0]
    assert asignacion.rol == "CLIENTE"
    assert asignacion.desde is not None
    assert asignacion.desde.tzinfo is not None
    assert asignacion.vence_en is None
    assert asignacion.revocada_en is None

    assert ficha is not None
    assert ficha.usuario_id == usuario.id
    assert (ficha.email, ficha.nombre) == (email, NOMBRE)


async def test_registro_dos_altas_validas_crean_dos_juegos_independientes(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    limpiar_registros,
) -> None:
    """Triangulación de 5.1: dos correos distintos no comparten filas."""
    primero = email_unico("c12-dos-a")
    segundo = email_unico("c12-dos-b")
    limpiar_registros(primero)
    limpiar_registros(segundo)
    antes = await contar_tres(db_sessionmaker)

    uno = await api_client.post("/auth/registro", json=_cuerpo(primero))
    dos = await api_client.post(
        "/auth/registro", json=_cuerpo(segundo, nombre="Beto Gómez")
    )

    assert (uno.status_code, dos.status_code) == (201, 201)
    assert uno.json()["id"] != dos.json()["id"]
    assert await contar_tres(db_sessionmaker) == (
        antes[0] + 2,
        antes[1] + 2,
        antes[2] + 2,
    )

    async with db_sessionmaker() as session:
        usuarios = list(
            (
                await session.execute(
                    select(Usuario)
                    .where(Usuario.email.in_([primero, segundo]))
                    .order_by(Usuario.id)
                )
            ).scalars()
        )
        fichas = list(
            (
                await session.execute(
                    select(Cliente)
                    .where(Cliente.email.in_([primero, segundo]))
                    .order_by(Cliente.id)
                )
            ).scalars()
        )

    assert [u.email for u in usuarios] == [primero, segundo]
    assert [f.usuario_id for f in fichas] == [u.id for u in usuarios]


# ---------------------------------------------------------------------------
# 5.2 Contrato de entrada en la API real, con counts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"rol": "ADMIN"},
        {"activo": False},
        {"password": "a" * 73},
        {"password": "ñ" * 40},
    ],
    ids=["rol", "campo-extra", "73-bytes", "40-enes"],
)
async def test_registro_contrato_invalido_da_422_sin_cambiar_los_counts(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    limpiar_registros,
    extra: dict[str, object],
) -> None:
    email = email_unico("c12-contrato")
    limpiar_registros(email)
    antes = await contar_tres(db_sessionmaker)

    respuesta = await api_client.post("/auth/registro", json=_cuerpo(email, **extra))

    assert respuesta.status_code == 422
    assert await contar_tres(db_sessionmaker) == antes
    assert await _usuario_por_email(db_sessionmaker, email) is None
    async with db_sessionmaker() as session:
        assert (
            await session.execute(
                select(func.count()).select_from(Cliente).where(Cliente.email == email)
            )
        ).scalar_one() == 0


@pytest.mark.parametrize(
    "password",
    ["a" * 72, "ñ" * 36],
    ids=["ascii-72", "multibyte-72"],
)
async def test_registro_contrato_acepta_72_bytes_en_postgresql(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    limpiar_registros,
    password: str,
) -> None:
    """Triangulación del límite: 72 bytes se aceptan (73 no, en el test previo)."""
    email = email_unico("c12-72")
    limpiar_registros(email)

    respuesta = await api_client.post(
        "/auth/registro", json=_cuerpo(email, password=password)
    )

    assert respuesta.status_code == 201
    usuario = await _usuario_por_email(db_sessionmaker, email)
    assert usuario is not None
    assert usuario.password_hash != password


# ---------------------------------------------------------------------------
# 5.3 Correo ya usado como usuario
# ---------------------------------------------------------------------------


async def test_registro_usuario_duplicado_da_409_sin_filas_nuevas(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    usuario_factory,
    limpiar_registros,
) -> None:
    email = email_unico("c12-dup-usuario")
    limpiar_registros(email)
    existente = await usuario_factory(email=email, roles=())
    antes = await contar_tres(db_sessionmaker)

    respuesta = await api_client.post("/auth/registro", json=_cuerpo(email))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya existe un usuario con ese email"
    assert "uq_usuario_email" not in respuesta.text
    assert "duplicate key" not in respuesta.text
    assert await contar_tres(db_sessionmaker) == antes
    async with db_sessionmaker() as session:
        usuarios = list(
            (
                await session.execute(
                    select(Usuario).where(Usuario.email == email)
                )
            ).scalars()
        )
        fichas = list(
            (
                await session.execute(
                    select(Cliente).where(Cliente.email == email)
                )
            ).scalars()
        )
    assert [u.id for u in usuarios] == [existente.id]
    assert fichas == []


# ---------------------------------------------------------------------------
# 5.4 Correo ya usado como cliente (ficha ajena intacta)
# ---------------------------------------------------------------------------


async def test_registro_cliente_duplicado_da_409_y_no_toca_la_ficha(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    cliente_factory,
    limpiar_registros,
) -> None:
    email = email_unico("c12-dup-cliente")
    limpiar_registros(email)
    ficha = await cliente_factory(nombre="Ficha ajena", email=email)
    antes = await contar_tres(db_sessionmaker)

    respuesta = await api_client.post("/auth/registro", json=_cuerpo(email))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya existe un cliente con ese email"
    assert "uq_cliente_email" not in respuesta.text
    assert await contar_tres(db_sessionmaker) == antes
    assert await _usuario_por_email(db_sessionmaker, email) is None

    async with db_sessionmaker() as session:
        actual = await session.get(Cliente, ficha.id)
        fichas_mismo_email = list(
            (
                await session.execute(
                    select(Cliente).where(Cliente.email == email)
                )
            ).scalars()
        )

    assert actual is not None
    assert actual.usuario_id is None
    assert (actual.nombre, actual.email) == ("Ficha ajena", email)
    assert [f.id for f in fichas_mismo_email] == [ficha.id]


# ---------------------------------------------------------------------------
# 5.5 Atomicidad: el fallo en la tercera escritura revierte las dos primeras
# ---------------------------------------------------------------------------


async def test_registro_atomicidad_no_deja_usuario_ni_rol_tras_el_409(
    api_client,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    cliente_factory,
    limpiar_registros,
) -> None:
    email = email_unico("c12-atomico")
    limpiar_registros(email)
    ficha = await cliente_factory(nombre="Ficha sembrada", email=email)

    async with db_sessionmaker() as session:
        usuarios_antes = int(
            (
                await session.execute(
                    select(func.count()).select_from(Usuario)
                )
            ).scalar_one()
        )
        roles_antes = int(
            (
                await session.execute(
                    select(func.count()).select_from(AsignacionRol)
                )
            ).scalar_one()
        )
        usuarios_con_email = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Usuario)
                    .where(Usuario.email == email)
                )
            ).scalar_one()
        )

    respuesta = await api_client.post("/auth/registro", json=_cuerpo(email))

    assert respuesta.status_code == 409

    async with db_sessionmaker() as session:
        usuarios_despues = int(
            (
                await session.execute(
                    select(func.count()).select_from(Usuario)
                )
            ).scalar_one()
        )
        roles_despues = int(
            (
                await session.execute(
                    select(func.count()).select_from(AsignacionRol)
                )
            ).scalar_one()
        )
        ficha_despues = await session.get(Cliente, ficha.id)
        fichas_mismo_email = list(
            (
                await session.execute(
                    select(Cliente).where(Cliente.email == email)
                )
            ).scalars()
        )

    # Las dos primeras escrituras (usuario y asignacion_rol) se revirtieron.
    assert usuarios_con_email == 0
    assert usuarios_despues == usuarios_antes
    assert roles_despues == roles_antes
    assert [f.id for f in fichas_mismo_email] == [ficha.id]
    assert ficha_despues is not None
    assert ficha_despues.usuario_id is None
    assert (ficha_despues.nombre, ficha_despues.email) == ("Ficha sembrada", email)
