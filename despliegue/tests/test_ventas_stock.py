"""Regresión del descuento de stock en la venta del TP cap. 1-4."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

# Importar los modelos completa el registry de SQLAlchemy antes de crear Venta.
import app.modules.autores.models  # noqa: F401
import app.modules.editoriales.models  # noqa: F401
import app.modules.generos.models  # noqa: F401
from app.modules.clientes.models import Cliente
from app.modules.libros.models import Libro
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.service import crear


class FakeSession:
    def __init__(self, cliente, libros):
        self.cliente = cliente
        self.libros = libros
        self.added = []
        self.rolled_back = 0

    async def get(self, model, id_):
        if model is Cliente:
            return self.cliente
        if model is Libro:
            return self.libros.get(id_)
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, Venta) and obj.id is None:
                obj.id = 1
            elif isinstance(obj, RenglonVenta) and obj.id is None:
                obj.id = len([x for x in self.added if isinstance(x, RenglonVenta)])

    async def rollback(self):
        self.rolled_back += 1

    async def refresh(self, obj):
        return None


def renglon(libro_id, cantidad):
    return SimpleNamespace(libro_id=libro_id, cantidad=cantidad)


@pytest.mark.asyncio
async def test_venta_descuenta_stock_y_calcula_total():
    libro = SimpleNamespace(
        id=1, titulo="Rayuela", precio=Decimal("25000.00"), stock=3
    )
    session = FakeSession(SimpleNamespace(id=1), {1: libro})

    venta = await crear(session, 1, [renglon(1, 2)])

    assert libro.stock == 1
    assert venta.total == Decimal("50000.00")


@pytest.mark.asyncio
async def test_stock_insuficiente_no_escribe_ni_descuenta():
    libro = SimpleNamespace(
        id=1, titulo="Rayuela", precio=Decimal("25000.00"), stock=1
    )
    session = FakeSession(SimpleNamespace(id=1), {1: libro})

    with pytest.raises(HTTPException) as exc:
        await crear(session, 1, [renglon(1, 2)])

    assert exc.value.status_code == 409
    assert "Stock insuficiente" in exc.value.detail
    assert libro.stock == 1
    assert session.added == []
    assert session.rolled_back == 0
