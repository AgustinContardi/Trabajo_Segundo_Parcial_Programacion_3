"""Contrato HTTP de `POST /usuarios` (C-15, tarea 6.1) contra PostgreSQL real.

Alta de personal en el grupo protegido: 201, 409 email repetido, 422 campo
extra / rol inválido, 401 sin cookie, 403 VENDEDOR y 403 ADMIN con cambio
pendiente.
"""

from datetime import timezone

import httpx
import pytest
import uuid

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
USUARIOS = "/usuarios/"


def _email(prefijo: str = "usu") -> str:
    return f"{prefijo}-{uuid.uuid4().hex}@example.com"


async def _login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _admin_sin_cambio_pendiente(
    api_client: httpx.AsyncClient, usuario_factory
):
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=False
    )
    await _login(api_client, admin.email)
    return admin


async def _admin_con_cambio_pendiente(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=True
    )
    await _login(api_client, admin.email)


async def test_usuarios_alta_valida_da_201(
    api_client: httpx.AsyncClient,
    usuario_factory,
    db_sessionmaker,
) -> None:
    admin = await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    cuerpo = {
        "email": _email("nueva-persona"),
        "nombre": "Nueva Persona",
        "password": "clave-segura-123",
        "rol": "VENDEDOR",
    }
    response = await api_client.post(USUARIOS, json=cuerpo)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == cuerpo["email"].strip().lower()
    assert body["nombre"] == "Nueva Persona"
    assert body["activo"] is True
    assert body["debe_cambiar_password"] is True
    assert set(body) == {"id", "email", "nombre", "activo", "debe_cambiar_password"}
    assert "password_hash" not in response.text

    # Limpieza del usuario creado por la API: su asignación referencia al admin
    # como `otorgada_por`, por lo que debe borrarse antes de que el factory
    # intente eliminar al admin (FK `asignacion_rol_otorgada_por_fkey`).
    try:
        pass
    finally:
        await _borrar_usuario_api(db_sessionmaker, body["id"], cuerpo["email"].strip().lower(), admin.id)


async def _borrar_usuario_api(
    db_sessionmaker, usuario_id: int, email: str, otorgante_id: int
) -> None:
    from sqlalchemy import delete, or_

    from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario

    async with db_sessionmaker() as session:
        await session.execute(
            delete(AsignacionRol).where(
                or_(
                    AsignacionRol.usuario_id == usuario_id,
                    AsignacionRol.otorgada_por == otorgante_id,
                )
            )
        )
        await session.execute(delete(Usuario).where(Usuario.id == usuario_id))
        await session.execute(delete(IntentoAcceso).where(IntentoAcceso.email == email))
        await session.commit()


async def test_usuarios_alta_admin_da_201(
    api_client: httpx.AsyncClient,
    usuario_factory,
    db_sessionmaker,
) -> None:
    admin = await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    cuerpo = {
        "email": _email("otro-admin"),
        "nombre": "Otro Admin",
        "password": PASSWORD,
        "rol": "ADMIN",
    }
    response = await api_client.post(USUARIOS, json=cuerpo)
    assert response.status_code == 201, response.text
    assert response.json()["debe_cambiar_password"] is True
    await _borrar_usuario_api(
        db_sessionmaker, response.json()["id"], cuerpo["email"], admin.id
    )


async def test_usuarios_alta_email_repetido_da_409(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    correo = _email("duplicado")
    await usuario_factory(password=PASSWORD, email=correo, roles=("VENDEDOR",))
    response = await api_client.post(
        USUARIOS,
        json={"email": correo.upper(), "nombre": "X", "password": PASSWORD, "rol": "VENDEDOR"},
    )
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "Ya existe un usuario con ese email"}


async def test_usuarios_alta_campo_extra_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    response = await api_client.post(
        USUARIOS,
        json={
            "email": "extra@example.com",
            "nombre": "X",
            "password": PASSWORD,
            "rol": "VENDEDOR",
            "departamento": "ventas",
        },
    )
    assert response.status_code == 422, response.text


async def test_usuarios_alta_rol_invalido_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    response = await api_client.post(
        USUARIOS,
        json={"email": "invalido@example.com", "nombre": "X", "password": PASSWORD, "rol": "CLIENTE"},
    )
    assert response.status_code == 422, response.text


async def test_usuarios_alta_rol_faltante_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin_sin_cambio_pendiente(api_client, usuario_factory)
    response = await api_client.post(
        USUARIOS,
        json={"email": "sinrol@example.com", "nombre": "X", "password": PASSWORD},
    )
    assert response.status_code == 422, response.text


async def test_usuarios_alta_sin_cookie_da_401(
    api_client: httpx.AsyncClient,
) -> None:
    api_client.cookies.clear()
    response = await api_client.post(
        USUARIOS,
        json={"email": "x@example.com", "nombre": "X", "password": PASSWORD, "rol": "VENDEDOR"},
    )
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "No autenticado"}


async def test_usuarios_alta_vendedor_da_403(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    vendedor = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    await _login(api_client, vendedor.email)
    response = await api_client.post(
        USUARIOS,
        json={"email": "x@example.com", "nombre": "X", "password": PASSWORD, "rol": "VENDEDOR"},
    )
    assert response.status_code == 403, response.text


async def test_usuarios_alta_admin_con_cambio_pendiente_da_403(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin_con_cambio_pendiente(api_client, usuario_factory)
    response = await api_client.post(
        USUARIOS,
        json={"email": "x@example.com", "nombre": "X", "password": PASSWORD, "rol": "VENDEDOR"},
    )
    assert response.status_code == 403, response.text
