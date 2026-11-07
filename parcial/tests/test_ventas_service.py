"""Servicio atómico de venta (RN-09, RN-10, RN-11) — RED antes de implementar.

Pruebas puras con un Unit of Work falso (sin PostgreSQL). Verifican:
- orden de escrituras cliente → libros → stock → venta → renglones → movimientos,
- 409 por cliente inexistente, libro inexistente, libro dado de baja y
  stock insuficiente, sin ninguna escritura,
- copia de `precio_unitario` y `total = Σ(cantidad × precio)` por el servidor,
- `libro_id` repetido → 422 **después** de los 409 (cliente/libros/baja/stock
  agregado), dentro del UoW y sin escribir,
- `IntegrityError` traducido a 409 **fuera** del bloque con rollback total,
- fallo en la última escritura (movimiento) con rollback total.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import IdentidadActual
from app.modules.clientes.models import Cliente
from app.modules.libros.models import Libro
from app.modules.usuarios.models import Usuario
from app.modules.ventas import service
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.schemas import RenglonCreate, VentaCreate


class _FakeLibroRepo:
    def __init__(self, libros):
        self._por_id = {libro.id: libro for libro in libros}
        self.aplicado = []  # (libro_id, cantidad, motivo, usuario_id, venta_id)

    async def get_by_ids(self, ids):
        return [self._por_id[i] for i in ids if i in self._por_id]

    async def aplicar_movimiento(self, libro, cantidad, motivo, usuario_id, venta_id=None):
        libro.stock += cantidad
        self.aplicado.append((libro.id, cantidad, motivo, usuario_id, venta_id))


class _FakeClienteRepo:
    def __init__(self, clientes):
        self._por_id = {cliente.id: cliente for cliente in clientes}

    async def get_by_id(self, id):
        return self._por_id.get(id)


class _FakeRepo:
    def __init__(self):
        self.adds = []
        self.secuencia = []  # nombres de entidad añadida, en orden

    async def add(self, entity):
        self.adds.append(entity)
        if entity.id is None:
            entity.id = len(self.adds)
        self.secuencia.append(type(entity).__name__)
        return entity

    async def get_by_id(self, id):
        for entity in self.adds:
            if getattr(entity, "id", None) == id:
                return entity
        return None


class _FakeRepoFalla(_FakeRepo):
    async def add(self, entity):
        raise IntegrityError("insert", (), Exception("fk o check de base"))


class _FakeUoW:
    def __init__(self, clientes, libros):
        self.clientes = _FakeClienteRepo(clientes)
        self.libros = _FakeLibroRepo(libros)
        self.ventas = _FakeRepo()
        self.renglones = _FakeRepo()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commits += 1
        else:
            self.rollbacks += 1
        return False


def _usuario(id=9):
    return IdentidadActual(
        usuario=Usuario(id=id, email=f"vendedor{id}@example.com", nombre="V", password_hash="x"),
        roles_db=("VENDEDOR",),
        roles_token=(),
    )


def _libro(id, precio, stock, borrado_en=None):
    return Libro(
        id=id,
        isbn=f"isbn-{id}",
        titulo=f"Libro {id}",
        precio=precio,
        stock=stock,
        editorial_id=1,
        borrado_en=borrado_en,
    )


def _cliente(id):
    return Cliente(id=id, nombre=f"Cliente {id}", email=f"c{id}@example.com")


def _dto(renglones):
    return VentaCreate(
        cliente_id=1,
        renglones=[
            RenglonCreate(libro_id=libro_id, cantidad=cantidad) for libro_id, cantidad in renglones
        ],
    )


@pytest.mark.asyncio
async def test_cliente_inexistente_devuelve_409_sin_escribir():
    uow = _FakeUoW(clientes=[], libros=[_libro(1, Decimal("10"), 5)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.ventas.adds == []
    assert uow.renglones.adds == []
    assert uow.libros.aplicado == []
    assert uow.commits == 0
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_libro_inexistente_devuelve_409_sin_escribir():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 5)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(99, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.ventas.adds == []
    assert uow.renglones.adds == []
    assert uow.libros.aplicado == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_libro_dado_de_baja_devuelve_409_sin_escribir():
    uow = _FakeUoW(
        clientes=[_cliente(1)],
        libros=[_libro(1, Decimal("10"), 5, borrado_en=datetime.now(timezone.utc))],
    )
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.ventas.adds == []
    assert uow.renglones.adds == []
    assert uow.libros.aplicado == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_stock_insuficiente_devuelve_409_sin_escribir():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 1)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.ventas.adds == []
    assert uow.renglones.adds == []
    assert uow.libros.aplicado == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_libro_id_repetido_devuelve_422_sin_escribir():
    """El duplicado se detecta dentro del UoW, después de los 409."""
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 5)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2), (1, 3)]), _usuario())

    assert excinfo.value.status_code == 422
    assert "mismo libro" in excinfo.value.detail.lower()
    assert uow.ventas.adds == []
    assert uow.renglones.adds == []
    assert uow.libros.aplicado == []
    assert uow.commits == 0
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_duplicado_con_cliente_inexistente_devuelve_409():
    uow = _FakeUoW(clientes=[], libros=[_libro(1, Decimal("10"), 5)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 1), (1, 1)]), _usuario())

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "El cliente indicado no existe"
    assert uow.ventas.adds == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_duplicado_con_libro_inexistente_devuelve_409():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(99, 1), (99, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "Uno o más libros indicados no existen"
    assert uow.ventas.adds == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_duplicado_con_stock_agregado_insuficiente_devuelve_409():
    # Cada renglón por separado (2 <= 3) pasaría; la suma agregada (4) no.
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 3)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2), (1, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert "Stock insuficiente" in excinfo.value.detail
    assert uow.ventas.adds == []
    assert uow.libros.aplicado == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_duplicado_con_libro_dado_de_baja_devuelve_409():
    uow = _FakeUoW(
        clientes=[_cliente(1)],
        libros=[_libro(1, Decimal("10"), 10, borrado_en=datetime.now(timezone.utc))],
    )
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 1), (1, 1)]), _usuario())

    assert excinfo.value.status_code == 409
    assert "dado de baja" in excinfo.value.detail
    assert uow.ventas.adds == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_duplicado_valido_con_stock_agregado_suficiente_devuelve_422():
    # Suma agregada 5 == stock 5: los 409 no aplican y gana el 422 del contrato.
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 5)])
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2), (1, 3)]), _usuario())

    assert excinfo.value.status_code == 422
    assert uow.ventas.adds == []
    assert uow.rollbacks == 1


@pytest.mark.asyncio
async def test_venta_valida_copia_precio_calcula_total_y_descuenta_stock():
    uow = _FakeUoW(
        clientes=[_cliente(1)],
        libros=[_libro(1, Decimal("10.00"), 5), _libro(2, Decimal("20.00"), 4)],
    )
    venta = await service.registrar_venta(
        uow, _dto([(1, 2), (2, 3)]), _usuario()
    )

    assert venta.id == 1
    assert venta.total == Decimal("80.00")  # 2*10 + 3*20

    # Orden de escrituras: venta, luego renglones, luego movimientos.
    assert uow.ventas.secuencia == ["Venta"]
    assert uow.renglones.secuencia == ["RenglonVenta", "RenglonVenta"]
    assert len(uow.libros.aplicado) == 2

    # Precio unitario copiado del libro.
    r1, r2 = uow.renglones.adds
    assert isinstance(r1, RenglonVenta)
    assert r1.venta_id == 1
    assert r1.libro_id == 1
    assert r1.cantidad == 2
    assert r1.precio_unitario == Decimal("10.00")
    assert r2.precio_unitario == Decimal("20.00")

    # Movimiento negativo por renglón con venta_id y usuario_id del vendedor.
    assert uow.libros.aplicado[0] == (1, -2, "Venta", 9, 1)
    assert uow.libros.aplicado[1] == (2, -3, "Venta", 9, 1)

    # Stock descontado.
    assert uow.libros._por_id[1].stock == 3
    assert uow.libros._por_id[2].stock == 1

    assert uow.commits == 1
    assert uow.rollbacks == 0


@pytest.mark.asyncio
async def test_stock_justo_es_valido():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("7.50"), 2)])
    venta = await service.registrar_venta(uow, _dto([(1, 2)]), _usuario())
    assert venta.total == Decimal("15.00")
    assert uow.libros._por_id[1].stock == 0
    assert uow.libros.aplicado[0] == (1, -2, "Venta", 9, 1)
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_un_solo_renglon():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("100"), 10)])
    venta = await service.registrar_venta(uow, _dto([(1, 1)]), _usuario())
    assert venta.total == Decimal("100")
    assert len(uow.renglones.adds) == 1
    assert len(uow.libros.aplicado) == 1
    assert uow.commits == 1


class _FakeLibroRepoFallaUltimo(_FakeLibroRepo):
    """Falla al aplicar el movimiento del segundo renglón (última escritura)."""

    async def aplicar_movimiento(self, libro, cantidad, motivo, usuario_id, venta_id=None):
        if self.aplicado:
            raise IntegrityError("insert", (), Exception("ck movimiento"))
        return await super().aplicar_movimiento(
            libro, cantidad, motivo, usuario_id, venta_id
        )


@pytest.mark.asyncio
async def test_fallo_en_el_ultimo_movimiento_revierte_todo():
    uow = _FakeUoW(
        clientes=[_cliente(1)],
        libros=[_libro(1, Decimal("10"), 5), _libro(2, Decimal("20"), 4)],
    )
    uow.libros = _FakeLibroRepoFallaUltimo(list(uow.libros._por_id.values()))

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 1), (2, 1)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.commits == 0
    assert uow.rollbacks == 1
    # La venta y ambos renglones se habían escrito en el UoW falso, pero el
    # rollback del `__aexit__` es el que garantiza la atomicidad real.
    assert len(uow.libros.aplicado) == 1


@pytest.mark.asyncio
async def test_integrity_error_en_escritura_devuelve_409_con_rollback():
    uow = _FakeUoW(clientes=[_cliente(1)], libros=[_libro(1, Decimal("10"), 5)])
    uow.ventas = _FakeRepoFalla()
    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto([(1, 2)]), _usuario())

    assert excinfo.value.status_code == 409
    assert uow.commits == 0
    assert uow.rollbacks == 1
    assert uow.libros.aplicado == []
