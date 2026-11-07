"""Tests de servicio para POST /ventas (C-16) — contra PostgreSQL real."""
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import IdentidadActual
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.libros.models import Libro, MovimientoStock
from app.modules.usuarios.models import AsignacionRol, Usuario
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.schemas import VentaCreate
from app.modules.ventas.service import registrar_venta
from app.modules.ventas.unit_of_work import VentasUnitOfWork

pytestmark = pytest.mark.asyncio


async def _crear_editorial(session: AsyncSession, nombre: str | None = None) -> Editorial:
    e = Editorial(
        nombre=nombre or f"Editorial {uuid.uuid4().hex}",
        pais="Argentina",
    )
    session.add(e)
    await session.flush()
    await session.commit()
    return e


async def _crear_usuario_vendedor(session: AsyncSession, email: str) -> Usuario:
    u = Usuario(
        email=email,
        nombre="Vendedor de prueba",
        password_hash="$2b$12$x",
        activo=True,
        debe_cambiar_password=False,
    )
    session.add(u)
    await session.flush()
    session.add(
        AsignacionRol(
            usuario_id=u.id,
            rol="VENDEDOR",
            desde=datetime.now(timezone.utc),
        )
    )
    await session.flush()
    await session.commit()
    return u


async def _crear_cliente(session: AsyncSession, email: str) -> Cliente:
    c = Cliente(
        nombre="Cliente de prueba",
        email=email,
    )
    session.add(c)
    await session.flush()
    await session.commit()
    return c


async def _crear_libro(
    session: AsyncSession,
    editorial: Editorial,
    titulo: str,
    precio: Decimal,
    stock: int,
) -> Libro:
    l = Libro(
        isbn=f"isbn-{uuid.uuid4().hex}",
        titulo=titulo,
        precio=precio,
        stock=stock,
        editorial_id=editorial.id,
    )
    session.add(l)
    await session.flush()
    await session.commit()
    return l


class TestServicioCrearVenta:
    async def test_venta_valida_201(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            try:
                vendedor = await _crear_usuario_vendedor(
                    session, f"v-{uuid.uuid4().hex}@example.com"
                )
                editorial = await _crear_editorial(session)
                cliente = await _crear_cliente(session, f"c-{uuid.uuid4().hex}@example.com")
                libro1 = await _crear_libro(session, editorial, "Libro A", Decimal("10.00"), 10)
                libro2 = await _crear_libro(session, editorial, "Libro B", Decimal("20.00"), 5)

                actual = IdentidadActual(
                    usuario=vendedor,
                    roles_db=("VENDEDOR",),
                    roles_token=(),
                )

                uow = VentasUnitOfWork(session)
                data = VentaCreate(
                    cliente_id=cliente.id,
                    renglones=[
                        {"libro_id": libro1.id, "cantidad": 2},
                        {"libro_id": libro2.id, "cantidad": 1},
                    ],
                )

                venta = await registrar_venta(uow, data, actual=actual)

                assert venta.id is not None
                assert venta.cliente_id == cliente.id
                assert venta.total == Decimal("40.00")  # 2*10 + 1*20

                # Verificar renglones
                result = await session.execute(
                    select(RenglonVenta).where(RenglonVenta.venta_id == venta.id)
                )
                renglones = list(result.scalars().all())
                assert len(renglones) == 2
                precios = {r.libro_id: r.precio_unitario for r in renglones}
                assert precios[libro1.id] == Decimal("10.00")
                assert precios[libro2.id] == Decimal("20.00")

                # Verificar descuento de stock
                result = await session.execute(
                    select(Libro).where(Libro.id.in_([libro1.id, libro2.id]))
                )
                libros = {l.id: l for l in result.scalars().all()}
                assert libros[libro1.id].stock == 8  # 10 - 2
                assert libros[libro2.id].stock == 4  # 5 - 1

                # Verificar movimientos de stock
                result = await session.execute(
                    select(MovimientoStock).where(
                        MovimientoStock.venta_id == venta.id
                    )
                )
                movimientos = list(result.scalars().all())
                assert len(movimientos) == 2
                for m in movimientos:
                    assert m.cantidad < 0
                    assert m.motivo == "Venta"
                    assert m.usuario_id == vendedor.id
                    assert m.venta_id == venta.id

            finally:
                pass  # No hay limpieza: movimiento_stock es append-only; datos únicos por test

    async def test_stock_insuficiente_409(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            try:
                vendedor = await _crear_usuario_vendedor(
                    session, f"v2-{uuid.uuid4().hex}@example.com"
                )
                editorial = await _crear_editorial(session)
                cliente = await _crear_cliente(session, f"c2-{uuid.uuid4().hex}@example.com")
                libro = await _crear_libro(session, editorial, "Libro Stock", Decimal("10.00"), 1)

                actual = IdentidadActual(
                    usuario=vendedor,
                    roles_db=("VENDEDOR",),
                    roles_token=(),
                )

                uow = VentasUnitOfWork(session)
                data = VentaCreate(
                    cliente_id=cliente.id,
                    renglones=[
                        {"libro_id": libro.id, "cantidad": 5},
                    ],
                )

                with pytest.raises(Exception):
                    await registrar_venta(uow, data, actual=actual)

            finally:
                pass

    async def test_cliente_inexistente_409(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            try:
                vendedor = await _crear_usuario_vendedor(
                    session, f"v3-{uuid.uuid4().hex}@example.com"
                )
                editorial = await _crear_editorial(session)
                libro = await _crear_libro(session, editorial, "Libro C", Decimal("10.00"), 10)

                actual = IdentidadActual(
                    usuario=vendedor,
                    roles_db=("VENDEDOR",),
                    roles_token=(),
                )

                uow = VentasUnitOfWork(session)
                data = VentaCreate(
                    cliente_id=99999,
                    renglones=[
                        {"libro_id": libro.id, "cantidad": 1},
                    ],
                )

                with pytest.raises(Exception):
                    await registrar_venta(uow, data, actual=actual)

            finally:
                pass

    async def test_libro_inexistente_409(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            try:
                vendedor = await _crear_usuario_vendedor(
                    session, f"v4-{uuid.uuid4().hex}@example.com"
                )
                cliente = await _crear_cliente(session, f"c4-{uuid.uuid4().hex}@example.com")

                actual = IdentidadActual(
                    usuario=vendedor,
                    roles_db=("VENDEDOR",),
                    roles_token=(),
                )

                uow = VentasUnitOfWork(session)
                data = VentaCreate(
                    cliente_id=cliente.id,
                    renglones=[
                        {"libro_id": 99999, "cantidad": 1},
                    ],
                )

                with pytest.raises(Exception):
                    await registrar_venta(uow, data, actual=actual)

            finally:
                pass
