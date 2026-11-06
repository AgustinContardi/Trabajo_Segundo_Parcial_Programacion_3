"""API de cambio de contraseña con main.app + dependency_overrides — sin PostgreSQL (C-14)."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException

from app.core.dependencies import (
    IdentidadActual,
    control_cambio_password,
    get_sesion_actual,
)
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.unit_of_work import (
    CambioPasswordUnitOfWork,
    get_cambio_password_uow,
)
from app.modules.usuarios import service

try:
    from main import app
except ImportError:  # pragma: no cover
    import importlib
    app = importlib.import_module("main").app

pytestmark = pytest.mark.asyncio

PASSWORD_ACTUAL = "clave-actual-123"
PASSWORD_NUEVA = "clave-nueva-abc"
EMAIL = "usuario@example.com"


def _haz_usuario(*, debe_cambiar_password: bool = False) -> Usuario:
    return Usuario(
        id=1,
        email=EMAIL,
        nombre="Usuario de prueba",
        password_hash="hash-viejo",
        activo=True,
        debe_cambiar_password=debe_cambiar_password,
    )


def _haz_uow(*, usuario: Usuario | None = None) -> CambioPasswordUnitOfWork:
    uow = Mock(spec=CambioPasswordUnitOfWork)
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.usuarios = Mock()
    uow.usuarios.get_by_email = AsyncMock(return_value=usuario)
    uow.eventos = Mock()
    uow.eventos.add = AsyncMock()
    return uow


async def _cliente_con_overrides(
    monkeypatch: pytest.MonkeyPatch,
    *,
    debe_cambiar_password: bool = False,
    password_actual_valida: bool = True,
):
    """Cliente ASGI contra main.app con dependencias dobles y estado del lifespan."""
    usuario = _haz_usuario(debe_cambiar_password=debe_cambiar_password)
    uow = _haz_uow(usuario=usuario)

    async def fake_sesion_actual() -> IdentidadActual:
        return IdentidadActual(
            usuario=usuario,
            roles_db=("CLIENTE",),
            roles_token=("CLIENTE",),
        )

    async def fake_uow_dep() -> CambioPasswordUnitOfWork:
        return uow

    app.dependency_overrides[get_sesion_actual] = fake_sesion_actual
    app.dependency_overrides[get_cambio_password_uow] = fake_uow_dep

    # El lifespan no se arranca: fijar estado manualmente para que el router
    # pueda leer settings y semaphore (son ignorados por los mocks de bcrypt).
    app.state.settings = SimpleNamespace(BCRYPT_ROUNDS=12)
    app.state.bcrypt_sem = asyncio.Semaphore(4)

    async def fake_verify(password: str, password_hash: str, semaphore) -> bool:
        return password == PASSWORD_ACTUAL if password_actual_valida else False

    async def fake_hash(password: str, *, rounds: int, semaphore) -> str:
        return "hash-nuevo-falso"

    monkeypatch.setattr(service, "verify_password", fake_verify)
    monkeypatch.setattr(service, "hash_password", fake_hash)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client, uow, usuario

    app.dependency_overrides.clear()


async def test_cambiar_password_exitoso_devuelve_200_y_no_rotar_cookie(
    monkeypatch: pytest.MonkeyPatch,
):
    """200, cuerpo {mensaje}, no hay Set-Cookie, UoW confirmado."""
    async for client, uow, usuario in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=False
    ):
        response = await client.post(
            "/auth/cambiar-password",
            json={
                "password_actual": PASSWORD_ACTUAL,
                "password_nueva": PASSWORD_NUEVA,
            },
        )

        assert response.status_code == 200, response.text
        assert response.json() == {"mensaje": "Contraseña actualizada"}

        # No emite token nuevo ni rota la cookie (IN-03, DD-07).
        set_cookie = response.headers.get_list("set-cookie")
        assert not any(
            c.startswith("access_token=") for c in set_cookie
        ), set_cookie

        # El UoW se confirmó (hash + bandera + evento en una transacción).
        assert uow.__aenter__.call_count >= 1

        # Se escribió una línea de evento_seguridad con actor = email (RN-16).
        uow.eventos.add.assert_awaited_once()
        evento = uow.eventos.add.call_args[0][0]
        assert evento.actor == EMAIL
        assert evento.accion == "Cambio de contraseña"

        # El usuario quedó con debe_cambiar_password = false (se lee en la base).
        assert usuario.debe_cambiar_password is False


async def test_cambiar_password_sin_cookie_devuelve_401(
    monkeypatch: pytest.MonkeyPatch,
):
    """Sin cookie válida -> 401 (RN-06)."""
    async for client, _, _ in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=False
    ):
        # Sobrescribir get_sesion_actual para que lance 401 (simula sin cookie).
        async def sesion_que_rechaza() -> IdentidadActual:
            raise HTTPException(status_code=401, detail="No autenticado")

        app.dependency_overrides[get_sesion_actual] = sesion_que_rechaza
        try:
            response = await client.post(
                "/auth/cambiar-password",
                json={
                    "password_actual": PASSWORD_ACTUAL,
                    "password_nueva": PASSWORD_NUEVA,
                },
            )
            assert response.status_code == 401
            assert response.json() == {"detail": "No autenticado"}
        finally:
            app.dependency_overrides.clear()


async def test_clave_actual_incorrecta_devuelve_401_sin_evento(
    monkeypatch: pytest.MonkeyPatch,
):
    """Contraseña actual incorrecta -> 401, no se escribe evento_seguridad."""
    async for client, uow, _ in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=False, password_actual_valida=False
    ):
        response = await client.post(
            "/auth/cambiar-password",
            json={
                "password_actual": "clave-mala",
                "password_nueva": PASSWORD_NUEVA,
            },
        )

        assert response.status_code == 401, response.text
        assert response.json() == {"detail": "Credenciales inválidas"}

        # No se escribió evento de seguridad.
        uow.eventos.add.assert_not_awaited()


async def test_password_de_73_bytes_devuelve_422_antes_de_bcrypt(
    monkeypatch: pytest.MonkeyPatch,
):
    """Contraseña nueva > 72 bytes -> 422, sin ejecutar bcrypt ni escribir en base."""
    async for client, uow, _ in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=False
    ):
        bcrypt_llamado = False

        async def fake_hash_que_no_debe_llamarse(
            password: str, *, rounds: int, semaphore
        ) -> str:
            nonlocal bcrypt_llamado
            bcrypt_llamado = True
            return "x"

        # Re-sobrescribir hash_password para detectar llamadas.
        from app.modules.usuarios import service as svc

        monkeypatch.setattr(svc, "hash_password", fake_hash_que_no_debe_llamarse)

        try:
            response = await client.post(
                "/auth/cambiar-password",
                json={
                    "password_actual": PASSWORD_ACTUAL,
                    "password_nueva": "a" * 73,
                },
            )

            assert response.status_code == 422, response.text
            assert not bcrypt_llamado
            uow.eventos.add.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()


async def test_cambiar_password_con_debe_cambiar_password_true_sigue_funcionando(
    monkeypatch: pytest.MonkeyPatch,
):
    """La ruta /auth/cambiar-password está en el grupo abierto: funciona incluso
    con debe_cambiar_password = true (es la salida del estado pendiente)."""
    async for client, uow, usuario in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=True
    ):
        response = await client.post(
            "/auth/cambiar-password",
            json={
                "password_actual": PASSWORD_ACTUAL,
                "password_nueva": PASSWORD_NUEVA,
            },
        )

        assert response.status_code == 200, response.text
        assert response.json() == {"mensaje": "Contraseña actualizada"}
        # Tras el cambio, la bandera se desactiva en la misma transacción.
        assert usuario.debe_cambiar_password is False


async def test_ruta_protegida_con_debe_cambiar_password_true_devuelve_403(
    monkeypatch: pytest.MonkeyPatch,
):
    """Una ruta del grupo protegido (clientes) devuelve 403 cuando
    debe_cambiar_password = true; el control está montado una sola vez."""
    async for client, _, _ in _cliente_con_overrides(
        monkeypatch, debe_cambiar_password=True
    ):
        # Sobrescribir control_cambio_password para que rechace con 403.
        async def control_que_rechaza() -> Usuario:
            raise HTTPException(status_code=403, detail="No autorizado")

        app.dependency_overrides[control_cambio_password] = control_que_rechaza
        try:
            response = await client.get("/ventas/mis-ventas")
            assert response.status_code == 403, response.text
            assert response.json() == {"detail": "No autorizado"}
        finally:
            app.dependency_overrides.clear()
