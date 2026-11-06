"""Logout: expiración de la cookie de acceso (C-11, 3.3)."""

from http.cookies import SimpleCookie

import httpx
import pytest

from tests.conftest import cabecera_cookie

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def test_logout_responde_200_y_expira_la_cookie(
    api_client: httpx.AsyncClient, settings
) -> None:
    response = await api_client.post("/auth/logout")

    assert response.status_code == 200
    cookie = SimpleCookie()
    cookie.load(cabecera_cookie(response))
    access = cookie["access_token"]
    assert access.value == ""
    assert access["max-age"] == "0"
    assert access["httponly"]
    assert access["samesite"] == "lax"
    assert bool(access["secure"]) is settings.COOKIE_SECURE
    assert access["path"] == "/"


async def test_logout_tras_login_borra_la_cookie_del_cliente(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD)
    login = await api_client.post(
        "/auth/login", json={"email": usuario.email, "password": PASSWORD}
    )
    assert login.status_code == 200
    assert "access_token" in api_client.cookies

    logout = await api_client.post("/auth/logout")

    assert logout.status_code == 200
    assert "access_token" not in api_client.cookies
