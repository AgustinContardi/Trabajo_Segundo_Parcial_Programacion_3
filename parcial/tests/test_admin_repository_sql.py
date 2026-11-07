"""SQL compilado de `contar_admins_vigentes` (C-15, tarea 3.5).

El bloqueo de filas de `RN-05` se verifica sobre la sentencia que el
repositorio construye, sin base de datos: con `bloquear=True` el SQL lleva
`FOR UPDATE`; sin bloqueo no lo lleva.
"""

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.usuarios.repository import AsignacionRolRepository

pytestmark = pytest.mark.asyncio


class _ResultadoVacio:
    def scalars(self):
        return self

    def all(self):
        return []


class _SesionCaptura:
    """Sesión mínima que guarda la sentencia ejecutada."""

    def __init__(self) -> None:
        self.stmt = None

    async def execute(self, stmt):
        self.stmt = stmt
        return _ResultadoVacio()


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


async def test_con_bloqueo_emite_for_update_y_sin_bloqueo_no() -> None:
    sesion = _SesionCaptura()
    repo = AsignacionRolRepository(sesion)

    assert await repo.contar_admins_vigentes(bloquear=True) == 0
    assert "FOR UPDATE" in _sql(sesion.stmt)

    assert await repo.contar_admins_vigentes(bloquear=False) == 0
    assert "FOR UPDATE" not in _sql(sesion.stmt)
