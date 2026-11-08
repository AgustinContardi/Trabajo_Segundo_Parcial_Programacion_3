"""Mensajes 422 propios en español (RN-15, RD-03, CHECKLIST §8).

El handler de `RequestValidationError` debe conservar `loc` y `type` (los tests
existentes los usan) y reemplazar `msg` por un texto propio en español según el
tipo de error, sin filtrar el texto de Pydantic ni de PostgreSQL.

Pruebas puras: no tocan la base ni levantan el lifespan.
"""

import json

import pytest
from fastapi.exceptions import RequestValidationError

from app.core.errors import manejador_request_validation_error

pytestmark = pytest.mark.asyncio

TEXTOS_PROHIBIDOS = (
    "input should",
    "value error",
    "field required",
    "extra inputs",
    "string",
    "postgres",
    "asyncpg",
    "sqlalchemy",
    "constraint",
    "traceback",
)


async def _detalle(tipo: str, loc=("body", "campo"), msg: str = "mensaje Pydantic") -> list[dict]:
    exc = RequestValidationError(
        [{"loc": list(loc), "msg": msg, "type": tipo, "input": "x"}]
    )
    response = await manejador_request_validation_error(None, exc)
    assert response.status_code == 422
    return json.loads(response.body)["detail"]


@pytest.mark.parametrize(
    ("tipo", "esperado"),
    [
        ("missing", "Falta un campo obligatorio"),
        ("extra_forbidden", "El campo no está permitido"),
        ("int_parsing", "Debe ser un número entero válido"),
        ("int_type", "Debe ser un número entero válido"),
        ("int_from_float", "Debe ser un número entero válido"),
        ("bool_type", "Debe ser un valor booleano válido"),
        ("float_type", "Debe ser un número válido"),
        ("decimal_parsing", "Debe ser un número válido"),
        ("greater_than", "El valor debe ser mayor que el mínimo permitido"),
        ("greater_than_equal", "El valor debe ser mayor que el mínimo permitido"),
        ("less_than_equal", "El valor supera el máximo permitido"),
        ("too_short", "La lista no puede estar vacía"),
        ("tipo_desconocido", "Los datos enviados no son válidos"),
    ],
)
async def test_tipo_de_error_devuelve_mensaje_en_espanol(tipo: str, esperado: str) -> None:
    detalle = await _detalle(tipo)
    assert len(detalle) == 1
    assert detalle[0]["msg"] == esperado
    assert detalle[0]["type"] == tipo
    assert detalle[0]["loc"] == ["body", "campo"]


async def test_el_handler_conserva_loc_y_no_filtra_textos_internos() -> None:
    detalle = await _detalle(
        "int_parsing",
        loc=("body", "renglones", 0, "cantidad"),
        msg="Input should be a valid integer, unable to parse string as an integer",
    )

    assert detalle[0]["loc"] == ["body", "renglones", 0, "cantidad"]
    texto = detalle[0]["msg"].lower()
    for prohibido in TEXTOS_PROHIBIDOS:
        assert prohibido not in texto
    assert texto == "debe ser un número entero válido"


async def test_varios_errores_conservan_orden_tipos_y_mensajes() -> None:
    exc = RequestValidationError(
        [
            {"loc": ["body", "precio"], "msg": "Extra inputs are not permitted", "type": "extra_forbidden"},
            {"loc": ["body", "renglones"], "msg": "List should have at least 1 item", "type": "too_short"},
        ]
    )
    response = await manejador_request_validation_error(None, exc)
    detalle = json.loads(response.body)["detail"]

    assert [item["type"] for item in detalle] == ["extra_forbidden", "too_short"]
    assert [item["msg"] for item in detalle] == [
        "El campo no está permitido",
        "La lista no puede estar vacía",
    ]
