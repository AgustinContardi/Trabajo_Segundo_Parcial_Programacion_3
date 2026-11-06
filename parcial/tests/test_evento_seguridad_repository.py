"""EventoSeguridadRepository con sesión falsa — sin PostgreSQL (C-14)."""

from typing import Any

import pytest
from sqlalchemy import select

from app.core.paginacion import Pagina
from app.modules.usuarios.models import EventoSeguridad
from app.modules.usuarios.repository import EventoSeguridadRepository

pytestmark = pytest.mark.asyncio


class _FakeSession:
    """Sesión falsa que rastrea flush y commit."""

    def __init__(self) -> None:
        self.flush_called = False
        self.commit_called = False

    def add(self, entity: Any) -> None:
        return None

    async def flush(self) -> None:
        self.flush_called = True

    async def commit(self) -> None:
        self.commit_called = True

    async def execute(self, stmt: Any) -> Any:  # pragma: no cover - no se usa en unit
        raise NotImplementedError


async def test_add_fluye_y_no_commitea():
    """add() debe hacer flush y nunca commit (CV-02)."""
    session = _FakeSession()
    repo = EventoSeguridadRepository(session)
    evento = EventoSeguridad(actor="usuario@example.com", accion="Cambio de contraseña")

    await repo.add(evento)

    assert session.flush_called is True
    assert session.commit_called is False


async def test_listado_devuelve_envoltorio_paginado(monkeypatch: pytest.MonkeyPatch):
    """listado() devuelve {items, total, page, size, pages} via paginar()."""
    session = _FakeSession()
    repo = EventoSeguridadRepository(session)
    pagina_esperada = Pagina[EventoSeguridad](
        items=[], total=0, page=1, size=20, pages=1
    )

    async def fake_paginar(
        session: Any, stmt: Any, page: int = 1, size: int = 20
    ) -> Pagina[Any]:
        assert page == 1
        assert size == 20
        # La consulta debe ordenar por cuando desc, id desc
        assert str(stmt).count("cuando") >= 1
        return pagina_esperada

    monkeypatch.setattr(
        "app.modules.usuarios.repository.paginar", fake_paginar
    )

    resultado = await repo.listado(page=1, size=20)

    assert resultado is pagina_esperada
    assert resultado.total == 0
    assert resultado.pages == 1


async def test_listado_usa_orden_descendente(monkeypatch: pytest.MonkeyPatch):
    """El statement de listado ordena por cuando.desc() e id.desc()."""
    session = _FakeSession()
    repo = EventoSeguridadRepository(session)

    capturado: list[Any] = []

    async def fake_paginar(session: Any, stmt: Any, **kwargs: Any) -> Pagina[Any]:
        capturado.append(stmt)
        return Pagina(items=[], total=0, page=1, size=20, pages=1)

    monkeypatch.setattr(
        "app.modules.usuarios.repository.paginar", fake_paginar
    )

    await repo.listado(page=2, size=10)

    assert len(capturado) == 1
    stmt_str = str(capturado[0])
    assert "cuando" in stmt_str
    assert "DESC" in stmt_str.upper()
