"""Contrato HTTP de login (C-11, 3.2) contra PostgreSQL real."""

from http.cookies import SimpleCookie

import httpx
import pytest

from app.core.security import decode_access_token
from app.modules.usuarios import service
from tests.conftest import cabecera_cookie, contar_intentos

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
LOGIN = "/auth/login"


async def test_login_rechaza_campo_no_declarado(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        LOGIN,
        json={"email": "ana@example.com", "password": PASSWORD, "rol": "ADMIN"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert "access_token" not in response.headers.get("set-cookie", "")


async def test_login_rechaza_password_mayor_a_72_bytes_antes_de_bcrypt(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas = 0

    async def prohibida(*args, **kwargs) -> bool:
        nonlocal llamadas
        llamadas += 1
        raise AssertionError("bcrypt no debe correr para una entrada inválida")

    monkeypatch.setattr(service, "verify_password", prohibida)

    response = await api_client.post(
        LOGIN, json={"email": "ana@example.com", "password": "ñ" * 37}
    )

    assert response.status_code == 422
    assert llamadas == 0


async def test_login_correcto_emite_cookie_sin_token_en_el_cuerpo(
    api_client: httpx.AsyncClient,
    api_app,
    settings,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(
        password=PASSWORD, roles=("ADMIN", "VENDEDOR"), debe_cambiar_password=True
    )

    response = await api_client.post(
        LOGIN, json={"email": usuario.email, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["debe_cambiar_password"] is True
    assert body["expira_en_segundos"] == settings.ACCESS_TOKEN_TTL_MIN * 60
    assert set(body) == {"mensaje", "debe_cambiar_password", "expira_en_segundos"}

    cookie = SimpleCookie()
    cookie.load(cabecera_cookie(response))
    access = cookie["access_token"]
    assert access["httponly"]
    assert access["samesite"] == "lax"
    assert access["max-age"] == str(settings.ACCESS_TOKEN_TTL_MIN * 60)
    assert bool(access["secure"]) is settings.COOKIE_SECURE

    payload = decode_access_token(access.value, secret=settings.JWT_SECRET)
    assert payload["sub"] == str(usuario.id)
    assert payload["roles"] == ["ADMIN", "VENDEDOR"]
    assert access.value not in response.text
    assert "password_hash" not in response.text
    assert await contar_intentos(api_app.state.sessionmaker, usuario.email) == 1


async def test_los_tres_401_tienen_el_mismo_cuerpo(
    api_client: httpx.AsyncClient,
    email_desconocido_factory,
    usuario_factory,
) -> None:
    activo = await usuario_factory(password=PASSWORD)
    inactivo = await usuario_factory(password=PASSWORD, activo=False)
    desconocido = email_desconocido_factory()

    cuerpos: list[dict] = []
    for email, password in (
        (activo.email, "clave-mala"),
        (desconocido, PASSWORD),
        (inactivo.email, PASSWORD),
    ):
        response = await api_client.post(
            LOGIN, json={"email": email, "password": password}
        )
        assert response.status_code == 401
        cuerpos.append(response.json())
        assert "set-cookie" not in response.headers

    assert cuerpos[0] == cuerpos[1] == cuerpos[2]
    assert "token" not in str(cuerpos[0]).lower()
    assert "hash" not in str(cuerpos[0]).lower()


async def test_sexto_intento_da_429_sin_bcrypt_y_queda_registrado(
    api_client: httpx.AsyncClient,
    api_app,
    usuario_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = await usuario_factory(password=PASSWORD)

    for _ in range(5):
        response = await api_client.post(
            LOGIN, json={"email": usuario.email, "password": "clave-mala"}
        )
        assert response.status_code == 401

    llamadas = 0

    async def prohibida(*args, **kwargs) -> bool:
        nonlocal llamadas
        llamadas += 1
        raise AssertionError("bcrypt no debe ejecutarse en el 429")

    monkeypatch.setattr(service, "verify_password", prohibida)

    response = await api_client.post(
        LOGIN, json={"email": usuario.email, "password": PASSWORD}
    )

    assert response.status_code == 429
    retry_after = response.headers["Retry-After"]
    assert retry_after.isdigit()
    assert int(retry_after) > 0
    assert "set-cookie" not in response.headers
    assert llamadas == 0
    assert await contar_intentos(api_app.state.sessionmaker, usuario.email) == 6


async def test_login_correcto_reinicia_el_conteo(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD)

    for _ in range(4):
        response = await api_client.post(
            LOGIN, json={"email": usuario.email, "password": "clave-mala"}
        )
        assert response.status_code == 401

    response = await api_client.post(
        LOGIN, json={"email": usuario.email, "password": PASSWORD}
    )
    assert response.status_code == 200

    for _ in range(5):
        response = await api_client.post(
            LOGIN, json={"email": usuario.email, "password": "clave-mala"}
        )
        assert response.status_code == 401

    response = await api_client.post(
        LOGIN, json={"email": usuario.email, "password": "clave-mala"}
    )
    assert response.status_code == 429
