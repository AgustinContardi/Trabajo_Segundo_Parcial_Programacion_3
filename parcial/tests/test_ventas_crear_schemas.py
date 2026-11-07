"""Tests de schemas para POST /ventas (C-16) — sin base de datos."""
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.ventas.schemas import RenglonCreate, VentaCreate


class TestVentaCreateCamposProhibidos:
    """Campos extra en el cuerpo → 422."""

    def test_campo_precio_extra(self):
        with pytest.raises(ValidationError):
            VentaCreate(
                cliente_id=1,
                renglones=[{"libro_id": 1, "cantidad": 1}],
                precio=Decimal("10.00"),
            )

    def test_campo_total_extra(self):
        with pytest.raises(ValidationError):
            VentaCreate(
                cliente_id=1,
                renglones=[{"libro_id": 1, "cantidad": 1}],
                total=Decimal("10.00"),
            )

    def test_campo_fecha_extra(self):
        with pytest.raises(ValidationError):
            VentaCreate(
                cliente_id=1,
                renglones=[{"libro_id": 1, "cantidad": 1}],
                fecha="2026-01-01",
            )

    def test_campo_desconocido_extra(self):
        with pytest.raises(ValidationError):
            VentaCreate(
                cliente_id=1,
                renglones=[{"libro_id": 1, "cantidad": 1}],
                campo_extra="no",
            )


class TestVentaCreateRenglones:
    """Validación de renglones."""

    def test_cero_renglones(self):
        with pytest.raises(ValidationError):
            VentaCreate(cliente_id=1, renglones=[])

    def test_libro_repetido(self):
        # min_length=1 y cada RenglonCreate tiene libro_id+cantidad
        # El duplicado se detecta a nivel de servicio, no de schema
        data = VentaCreate(
            cliente_id=1,
            renglones=[
                {"libro_id": 1, "cantidad": 1},
                {"libro_id": 1, "cantidad": 2},
            ],
        )
        assert len(data.renglones) == 2
        assert data.renglones[0].libro_id == data.renglones[1].libro_id


class TestRenglonCreate:
    """Schema de renglón individual."""

    def test_valido(self):
        r = RenglonCreate(libro_id=1, cantidad=3)
        assert r.libro_id == 1
        assert r.cantidad == 3

    def test_cantidad_cero(self):
        with pytest.raises(ValidationError):
            RenglonCreate(libro_id=1, cantidad=0)

    def test_cantidad_negativa(self):
        with pytest.raises(ValidationError):
            RenglonCreate(libro_id=1, cantidad=-1)

    def test_campo_extra(self):
        with pytest.raises(ValidationError):
            RenglonCreate(libro_id=1, cantidad=1, precio=Decimal("10.00"))
