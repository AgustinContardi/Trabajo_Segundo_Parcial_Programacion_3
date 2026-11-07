"""Contrato de entrada de POST /ventas (RN-09, RN-15, CHECKLIST §8).

`VentaCreate` acepta SOLO `cliente_id` y `renglones: [{libro_id, cantidad}]`;
`extra="forbid"` rechaza `precio`/`total`/`fecha`, `min_length=1` rechaza cero
renglones y `gt=0` rechaza `cantidad <= 0`. Pruebas puras, sin base de datos.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.ventas.schemas import RenglonCreate, VentaCreate

CLIENTE_ID = 7
LIBRO_ID = 3


def _valido(renglones=None):
    if renglones is None:
        renglones = [{"libro_id": LIBRO_ID, "cantidad": 2}]
    return VentaCreate(cliente_id=CLIENTE_ID, renglones=renglones)


def _tipos(excinfo: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {error["type"] for error in excinfo.value.errors()}


def test_venta_create_acepta_cliente_id_y_renglones_validos():
    data = _valido()
    assert data.cliente_id == CLIENTE_ID
    assert len(data.renglones) == 1
    assert data.renglones[0].libro_id == LIBRO_ID
    assert data.renglones[0].cantidad == 2


@pytest.mark.parametrize("campo_extra", ["precio", "total", "fecha", "descuento"])
def test_venta_create_rechaza_campos_extra(campo_extra: str):
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(
            cliente_id=CLIENTE_ID,
            renglones=[{"libro_id": LIBRO_ID, "cantidad": 2}],
            **{campo_extra: 1},
        )
    assert "extra_forbidden" in _tipos(excinfo)


def test_venta_create_rechaza_cero_renglones():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(cliente_id=CLIENTE_ID, renglones=[])
    assert "too_short" in _tipos(excinfo)


@pytest.mark.parametrize("cantidad", [0, -1, -5])
def test_renglon_create_rechaza_cantidad_no_positiva(cantidad: int):
    with pytest.raises(ValidationError) as excinfo:
        RenglonCreate(libro_id=LIBRO_ID, cantidad=cantidad)
    assert "greater_than" in _tipos(excinfo)


def test_renglon_create_acepta_cantidad_positiva():
    data = RenglonCreate(libro_id=LIBRO_ID, cantidad=1)
    assert data.cantidad == 1


def test_venta_create_exige_cliente_id():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(renglones=[{"libro_id": LIBRO_ID, "cantidad": 2}])
    assert "missing" in _tipos(excinfo)


def test_venta_create_exige_renglones():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(cliente_id=CLIENTE_ID)
    assert "missing" in _tipos(excinfo)


def test_venta_create_rechaza_cuerpo_vacio():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate()
    assert "missing" in _tipos(excinfo)


def test_venta_create_rechaza_renglon_sin_libro_id():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(cliente_id=CLIENTE_ID, renglones=[{"cantidad": 2}])
    assert "missing" in _tipos(excinfo)


def test_venta_create_rechaza_renglon_sin_cantidad():
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(cliente_id=CLIENTE_ID, renglones=[{"libro_id": LIBRO_ID}])
    assert "missing" in _tipos(excinfo)


def test_venta_create_el_libro_id_repetido_no_es_un_error_de_schema():
    """El duplicado de libro_id se valida en el servicio (422), no en Pydantic."""
    data = _valido(
        renglones=[
            {"libro_id": LIBRO_ID, "cantidad": 2},
            {"libro_id": LIBRO_ID, "cantidad": 3},
        ]
    )
    assert len(data.renglones) == 2
