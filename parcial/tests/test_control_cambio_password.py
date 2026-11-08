"""Dependencia control_cambio_password (C-14).

Mezcla pruebas unitarias (sin base) y una integración real: la última verifica
el orden 401 → 403 sobre una ruta del grupo protegido con PostgreSQL.
"""

import httpx
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.core.dependencies import control_cambio_password

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura" + "-123"


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


async def test_orden_401_antes_de_403_en_una_ruta_protegida(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    """Sin cookie la ruta responde 401; con cambio pendiente, 403.

    El control se monta una sola vez en el grupo protegido: primero autentica
    (`get_usuario_actual` → 401) y sólo después evalúa la bandera (→ 403). Si
    el orden se invirtiera, la petición sin cookie recibiría 403.
    """
    api_client.cookies.clear()
    sin_cookie = await api_client.get("/clientes/1")
    assert sin_cookie.status_code == 401, sin_cookie.text
    assert sin_cookie.json() == {"detail": "No autenticado"}

    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=True
    )
    login = await api_client.post(
        "/auth/login", json={"email": admin.email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text

    con_cambio_pendiente = await api_client.get("/clientes/1")
    assert con_cambio_pendiente.status_code == 403, con_cambio_pendiente.text
    assert con_cambio_pendiente.json() == {"detail": "No autorizado"}
