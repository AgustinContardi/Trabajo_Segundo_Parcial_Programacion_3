"""Identidad actual desde la cookie `access_token` (C-11, 4.1/4.2)."""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio

from app.modules.usuarios.repository import UsuarioRepository
from tests.conftest import token_manual

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def protegido_client(
    settings,
) -> AsyncIterator[httpx.AsyncClient]:
    """App de prueba con una ruta protegida real que usa `get_usuario_actual`."""
    from fastapi import Depends, FastAPI

    from app.core.dependencies import get_usuario_actual
    from app.modules.usuarios.models import Usuario
    from main import lifespan

    app = FastAPI(lifespan=lifespan)

    @app.get("/_test/protegido")
    async def protegido(usuario: Usuario = Depends(get_usuario_actual)):
        return {"id": usuario.id, "email": usuario.email}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client


async def test_cookie_valida_resuelve_la_identidad(
    protegido_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=())
    token = token_manual(subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value())
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 200
    assert response.json() == {"id": usuario.id, "email": usuario.email}


async def test_sin_cookie_da_401(
    protegido_client: httpx.AsyncClient,
) -> None:
    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda secret: "esto-no-es-un-jwt",
        lambda secret: token_manual(
            subject=1,
            secret="otro-secreto-de-prueba-de-32-bytes-o-mas",
        ),
    ],
)
async def test_token_invalido_da_401_sin_detalles_criptograficos(
    protegido_client: httpx.AsyncClient, settings, token_factory
) -> None:
    token = token_factory(settings.JWT_SECRET.get_secret_value())
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401
    texto = response.text.lower()
    assert "jwt" not in texto
    assert "signature" not in texto
    assert "expired" not in texto
    assert "crypto" not in texto


async def test_token_vencido_da_401(
    protegido_client: httpx.AsyncClient, settings
) -> None:
    token = token_manual(
        subject=1,
        secret=settings.JWT_SECRET.get_secret_value(),
        exp_offset_seconds=-1,
    )
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "1"},
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        {"sub": "no-numerico", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
    ],
)
async def test_token_sin_claims_validos_o_sub_no_numerico_da_401(
    protegido_client: httpx.AsyncClient, settings, payload
) -> None:
    token = jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401


async def test_authorization_bearer_sin_cookie_no_autentica(
    protegido_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=())
    token = token_manual(subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value())

    response = await protegido_client.get(
        "/_test/protegido", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_usuario_inexistente_da_401(
    protegido_client: httpx.AsyncClient, settings
) -> None:
    token = token_manual(subject=999_999_999, secret=settings.JWT_SECRET.get_secret_value())
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401


async def test_usuario_inactivo_da_401(
    protegido_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(activo=False)
    token = token_manual(subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value())
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 401


async def test_la_dependencia_no_consulta_roles_ni_autoriza(
    protegido_client: httpx.AsyncClient,
    settings,
    usuario_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = await usuario_factory(roles=())

    async def prohibida(*args, **kwargs):
        raise AssertionError("get_usuario_actual no debe consultar roles")

    monkeypatch.setattr(UsuarioRepository, "roles_vigentes", prohibida)
    token = token_manual(subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value())
    protegido_client.cookies.set("access_token", token)

    response = await protegido_client.get("/_test/protegido")

    assert response.status_code == 200
    assert response.json()["id"] == usuario.id
