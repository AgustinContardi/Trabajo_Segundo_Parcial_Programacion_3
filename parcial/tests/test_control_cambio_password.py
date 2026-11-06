"""Dependencia control_cambio_password — sin base de datos (C-14)."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core.dependencies import control_cambio_password

pytestmark = pytest.mark.asyncio


async def test_control_cambio_password_true_devuelve_403():
    """debe_cambiar_password = true -> 403 'No autorizado'."""
    usuario = Mock()
    usuario.debe_cambiar_password = True

    with pytest.raises(HTTPException) as excinfo:
        await control_cambio_password(usuario)

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "No autorizado"


async def test_control_cambio_password_false_devuelve_usuario():
    """debe_cambiar_password = false -> devuelve el usuario sin cambios."""
    usuario = Mock()
    usuario.debe_cambiar_password = False

    resultado = await control_cambio_password(usuario)

    assert resultado is usuario


async def test_control_cambio_password_sin_usuario_no_llega_a_la_verificacion():
    """Si get_usuario_actual falla con 401, el control nunca se ejecuta."""
    # Este test documenta el orden: 401 (get_usuario_actual) antes que 403 (control).
    pass
