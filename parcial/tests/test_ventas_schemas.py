"""Contrato de entrada de POST /ventas (RN-09, RN-15, CHECKLIST §8).

`VentaCreate` acepta SOLO `cliente_id` y `renglones: [{libro_id, cantidad}]`;
`extra="forbid"` rechaza `precio`/`total`/`fecha`, `min_length=1` rechaza cero
renglones y los enteros son **estrictos y acotados**: `cliente_id`/`libro_id`
hasta `BIGINT` y `cantidad` hasta `integer`, sin coerción de booleanos,
strings ni floats. Pruebas puras, sin base de datos.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.ventas.schemas import RenglonCreate, VentaCreate

CLIENTE_ID = 7
LIBRO_ID = 3

BIGINT_MAX = 2**63 - 1
INT_MAX = 2**31 - 1
TIPOS_ENTERO_INVALIDO = {"int_type", "int_parsing", "int_from_float"}


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
    assert _tipos(excinfo) & {"greater_than", "greater_than_equal"}


@pytest.mark.parametrize("valor", [10**30, BIGINT_MAX + 1, 2**63, 2**70])
def test_venta_create_rechaza_cliente_id_fuera_del_rango_bigint(valor: int):
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(
            cliente_id=valor,
            renglones=[{"libro_id": LIBRO_ID, "cantidad": 1}],
        )
    assert "less_than_equal" in _tipos(excinfo)


@pytest.mark.parametrize("valor", [10**30, BIGINT_MAX + 1, 2**63, 2**70])
def test_renglon_create_rechaza_libro_id_fuera_del_rango_bigint(valor: int):
    with pytest.raises(ValidationError) as excinfo:
        RenglonCreate(libro_id=valor, cantidad=1)
    assert "less_than_equal" in _tipos(excinfo)


@pytest.mark.parametrize("valor", [INT_MAX + 1, 2**31, 2**40])
def test_renglon_create_rechaza_cantidad_fuera_del_rango_integer(valor: int):
    with pytest.raises(ValidationError) as excinfo:
        RenglonCreate(libro_id=LIBRO_ID, cantidad=valor)
    assert "less_than_equal" in _tipos(excinfo)


@pytest.mark.parametrize("cantidad", [True, False, "1", "2", 1.0, 1.5, Decimal("2")])
def test_renglon_create_rechaza_cantidad_booleana_string_o_float(cantidad):
    with pytest.raises(ValidationError) as excinfo:
        RenglonCreate(libro_id=LIBRO_ID, cantidad=cantidad)
    assert _tipos(excinfo) & TIPOS_ENTERO_INVALIDO


@pytest.mark.parametrize("valor", [True, "7", 7.0, 7.5])
def test_venta_create_rechaza_cliente_id_no_entero(valor):
    with pytest.raises(ValidationError) as excinfo:
        VentaCreate(
            cliente_id=valor,
            renglones=[{"libro_id": LIBRO_ID, "cantidad": 1}],
        )
    assert _tipos(excinfo) & TIPOS_ENTERO_INVALIDO


@pytest.mark.parametrize("valor", [True, "3", 3.0, 3.5])
def test_renglon_create_rechaza_libro_id_no_entero(valor):
    with pytest.raises(ValidationError) as excinfo:
        RenglonCreate(libro_id=valor, cantidad=1)
    assert _tipos(excinfo) & TIPOS_ENTERO_INVALIDO


def test_schemas_aceptan_los_limites_exactos_de_las_columnas():
    data = VentaCreate(
        cliente_id=BIGINT_MAX,
        renglones=[{"libro_id": BIGINT_MAX, "cantidad": INT_MAX}],
    )
    assert data.cliente_id == BIGINT_MAX
    assert data.renglones[0].libro_id == BIGINT_MAX
    assert data.renglones[0].cantidad == INT_MAX


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
