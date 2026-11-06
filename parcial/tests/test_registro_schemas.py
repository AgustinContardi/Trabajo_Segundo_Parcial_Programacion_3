"""Contrato de entrada del auto-registro (C-12, 1.1/1.3).

`POST /auth/registro` reutiliza `UsuarioCreate`: sólo `email`, `nombre` y
`password`; cualquier campo extra (incluido `rol`) se rechaza, la contraseña no
supera 72 bytes y el email se normaliza. `UsuarioRead` nunca declara
`password_hash`.
"""

import pytest
from pydantic import ValidationError

from app.modules.usuarios.schemas import UsuarioCreate, UsuarioRead

EMAIL = "ana@example.com"
NOMBRE = "Ana Pérez"
PASSWORD = "clave-segura-123"


def _errores(excinfo: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {error["type"] for error in excinfo.value.errors()}


def test_usuario_create_rechaza_rol_como_campo_extra() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UsuarioCreate(
            email=EMAIL,
            nombre=NOMBRE,
            password=PASSWORD,
            rol="ADMIN",
        )

    assert "extra_forbidden" in _errores(excinfo)


def test_usuario_create_rechaza_cualquier_otro_campo_no_declarado() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UsuarioCreate(
            email=EMAIL,
            nombre=NOMBRE,
            password=PASSWORD,
            activo=False,
        )

    assert "extra_forbidden" in _errores(excinfo)


def test_usuario_create_no_declara_el_campo_rol() -> None:
    assert "rol" not in UsuarioCreate.model_fields


def test_usuario_create_rechaza_password_de_73_bytes() -> None:
    with pytest.raises(ValidationError, match="72 bytes"):
        UsuarioCreate(email=EMAIL, nombre=NOMBRE, password="a" * 73)


def test_usuario_create_rechaza_40_enes_que_ocupan_80_bytes() -> None:
    password = "ñ" * 40
    assert len(password.encode("utf-8")) == 80

    with pytest.raises(ValidationError, match="72 bytes"):
        UsuarioCreate(email=EMAIL, nombre=NOMBRE, password=password)


def test_usuario_create_acepta_password_de_exactamente_72_bytes() -> None:
    data = UsuarioCreate(email=EMAIL, nombre=NOMBRE, password="a" * 72)

    assert len(data.password.encode("utf-8")) == 72


def test_usuario_create_acepta_72_bytes_multibyte() -> None:
    password = "ñ" * 36
    assert len(password.encode("utf-8")) == 72

    data = UsuarioCreate(email=EMAIL, nombre=NOMBRE, password=password)

    assert data.password == password


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("email", "ana\x00@example.com"),
        ("nombre", "Ana\x00Pérez"),
        ("password", "clave\x00segura"),
    ],
)
def test_usuario_create_rechaza_el_caracter_nulo(campo: str, valor: str) -> None:
    cuerpo = {"email": EMAIL, "nombre": NOMBRE, "password": PASSWORD, campo: valor}

    with pytest.raises(ValidationError, match="carácter nulo"):
        UsuarioCreate(**cuerpo)


def test_usuario_create_normaliza_el_email() -> None:
    data = UsuarioCreate(
        email="  Ana.Perez@Example.COM  ",
        nombre=NOMBRE,
        password=PASSWORD,
    )

    assert data.email == "ana.perez@example.com"


def test_usuario_create_exige_los_tres_campos() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UsuarioCreate()

    assert "missing" in _errores(excinfo)


def test_usuario_read_no_declara_password_hash() -> None:
    assert "password_hash" not in UsuarioRead.model_fields


def test_usuario_read_proyecta_solo_los_campos_publicos() -> None:
    class _Usuario:
        id = 7
        email = EMAIL
        nombre = NOMBRE
        activo = True
        debe_cambiar_password = False
        password_hash = "$2b$12$no-debe-salir"

    data = UsuarioRead.model_validate(_Usuario())

    assert set(data.model_dump()) == {
        "id",
        "email",
        "nombre",
        "activo",
        "debe_cambiar_password",
    }
