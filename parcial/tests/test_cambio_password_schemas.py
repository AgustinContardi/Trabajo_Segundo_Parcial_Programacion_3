"""Esquemas de cambio de contraseña (C-14) — sin base de datos."""

import pytest
from pydantic import ValidationError

from app.modules.usuarios.schemas import (
    CambiarPasswordRequest,
    CambiarPasswordResponse,
)


def test_request_valido_se_parsea():
    req = CambiarPasswordRequest(
        password_actual="clave-actual-123",
        password_nueva="clave-nueva-abc",
    )
    assert req.password_actual == "clave-actual-123"
    assert req.password_nueva == "clave-nueva-abc"


def test_request_campo_extra_devuelve_422():
    with pytest.raises(ValidationError):
        CambiarPasswordRequest(
            password_actual="clave-actual",
            password_nueva="clave-nueva",
            campo_extra="no-debe-estar",
        )


def test_password_nueva_mayor_72_bytes_devuelve_422():
    with pytest.raises(ValidationError):
        CambiarPasswordRequest(
            password_actual="clave-actual",
            password_nueva="a" * 73,
        )


def test_password_actual_mayor_72_bytes_devuelve_422():
    with pytest.raises(ValidationError):
        CambiarPasswordRequest(
            password_actual="a" * 73,
            password_nueva="clave-nueva",
        )


def test_password_exactamente_72_bytes_es_valido():
    req = CambiarPasswordRequest(
        password_actual="a" * 72,
        password_nueva="b" * 72,
    )
    assert len(req.password_actual.encode("utf-8")) == 72
    assert len(req.password_nueva.encode("utf-8")) == 72


def test_response_solo_tiene_mensaje_sin_hash_ni_token():
    resp = CambiarPasswordResponse(mensaje="Contraseña actualizada")
    assert resp.mensaje == "Contraseña actualizada"
    assert not hasattr(resp, "password_hash")
    assert not hasattr(resp, "token")
    assert set(resp.model_dump()) == {"mensaje"}
