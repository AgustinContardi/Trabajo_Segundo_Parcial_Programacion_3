"""Una sola sesión por petición para identidad, roles y UoW (C-13, 5.1)."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.clientes.repository import ClienteRepository
from app.modules.usuarios.repository import UsuarioRepository

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def test_identidad_roles_y_uow_comparten_una_sola_sesion(
    api_client: httpx.AsyncClient,
    api_app,
    usuario_factory,
    cliente_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    cliente = await cliente_factory()
    login = await api_client.post(
        "/auth/login", json={"email": usuario.email, "password": PASSWORD}
    )
    assert login.status_code == 200

    llamadas = 0
    cerradas = 0
    creadas: list[AsyncSession] = []
    sesiones: dict[str, list] = {"usuarios": [], "clientes": []}

    async def contador(request: Request) -> AsyncIterator:
        nonlocal llamadas
        llamadas += 1
        session = request.app.state.sessionmaker()
        creadas.append(session)
        try:
            yield session
        finally:
            await session.close()

    original_close = AsyncSession.close

    async def close(self) -> None:
        nonlocal cerradas
        if creadas and self is creadas[0]:
            cerradas += 1
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "close", close)
    original_usuarios = UsuarioRepository.__init__
    original_clientes = ClienteRepository.__init__

    def usuarios_init(self, session):
        sesiones["usuarios"].append(session)
        original_usuarios(self, session)

    def clientes_init(self, session):
        sesiones["clientes"].append(session)
        original_clientes(self, session)

    monkeypatch.setattr(UsuarioRepository, "__init__", usuarios_init)
    monkeypatch.setattr(ClienteRepository, "__init__", clientes_init)
    api_app.dependency_overrides[get_session] = contador
    try:
        response = await api_client.get(f"/clientes/{cliente.id}/ventas")
    finally:
        api_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert llamadas == 1
    assert sesiones["usuarios"], "la identidad y los roles deben usar la sesión"
    assert sesiones["clientes"], "el UoW debe usar la sesión"
    primera = sesiones["usuarios"][0]
    assert all(s is primera for s in sesiones["usuarios"])
    assert all(s is primera for s in sesiones["clientes"])
    assert cerradas == 1, "la sesión compartida se cierra una sola vez"
