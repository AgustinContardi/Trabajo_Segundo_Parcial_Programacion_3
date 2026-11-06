"""Contrato de `GET /auth/yo` (C-13, 1.3) contra PostgreSQL real."""

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import update

from tests.conftest import token_manual

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
YO = "/auth/yo"


async def _revocar_rol(db_sessionmaker, usuario_id: int, rol: str) -> None:
    from app.modules.usuarios.models import AsignacionRol

    async with db_sessionmaker() as session:
        await session.execute(
            update(AsignacionRol)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.rol == rol,
            )
            .values(revocada_en=datetime.now(timezone.utc))
        )
        await session.commit()


async def test_yo_devuelve_usuario_y_ambos_conjuntos_sin_hash_ni_token(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(
        password=PASSWORD, roles=("CLIENTE",), debe_cambiar_password=False
    )
    login = await api_client.post(
        "/auth/login", json={"email": usuario.email, "password": PASSWORD}
    )
    assert login.status_code == 200
    token = api_client.cookies.get("access_token")
    assert token

    response = await api_client.get(YO)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"usuario", "roles", "roles_token"}
    assert body["usuario"] == {
        "id": usuario.id,
        "email": usuario.email,
        "nombre": usuario.nombre,
        "activo": True,
        "debe_cambiar_password": False,
    }
    assert body["roles"] == ["CLIENTE"]
    assert body["roles_token"] == ["CLIENTE"]
    assert "password_hash" not in response.text
    assert token not in response.text


async def test_yo_muestra_la_diferencia_tras_revocar_un_rol(
    api_client: httpx.AsyncClient, db_sessionmaker, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE", "ADMIN"))
    login = await api_client.post(
        "/auth/login", json={"email": usuario.email, "password": PASSWORD}
    )
    assert login.status_code == 200

    await _revocar_rol(db_sessionmaker, usuario.id, "ADMIN")

    response = await api_client.get(YO)

    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["CLIENTE"]
    assert body["roles_token"] == ["ADMIN", "CLIENTE"]


@pytest.mark.parametrize(
    "cookie",
    [None, "esto-no-es-un-jwt"],
)
async def test_yo_sin_cookie_valida_da_401(
    api_client: httpx.AsyncClient, cookie: str | None
) -> None:
    if cookie is not None:
        api_client.cookies.set("access_token", cookie)

    response = await api_client.get(YO)

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


async def test_yo_con_usuario_inactivo_da_401(
    api_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, activo=False)
    api_client.cookies.set(
        "access_token",
        token_manual(
            subject=usuario.id,
            secret=settings.JWT_SECRET.get_secret_value(),
        ),
    )

    response = await api_client.get(YO)

    assert response.status_code == 401
