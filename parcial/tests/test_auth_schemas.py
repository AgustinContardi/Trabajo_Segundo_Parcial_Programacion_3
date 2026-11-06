"""Contrato de entrada del login (C-11, 3.1)."""

import pytest
from pydantic import ValidationError

from app.modules.usuarios.schemas import LoginRequest, LoginResponse


def test_login_request_rejects_undeclared_fields() -> None:
    with pytest.raises(ValidationError) as excinfo:
        LoginRequest(
            email="ana@example.com",
            password="clave-segura-123",
            rol="ADMIN",
        )

    assert any(
        error["type"] == "extra_forbidden" for error in excinfo.value.errors()
    )


def test_login_request_rejects_password_over_72_bytes() -> None:
    with pytest.raises(ValidationError, match="72 bytes"):
        LoginRequest(email="ana@example.com", password="ñ" * 37)


def test_login_request_accepts_password_at_72_bytes() -> None:
    request = LoginRequest(email="ana@example.com", password="a" * 72)

    assert len(request.password.encode("utf-8")) == 72


def test_login_response_has_no_token_field() -> None:
    response = LoginResponse(
        mensaje="Sesión iniciada",
        debe_cambiar_password=False,
        expira_en_segundos=1800,
    )

    assert set(response.model_dump()) == {
        "mensaje",
        "debe_cambiar_password",
        "expira_en_segundos",
    }
