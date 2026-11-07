"""Tests de servicio para POST /ventas (C-16) — contra PostgreSQL real.

Aislamiento: cada prueba crea datos con emails/ISBN únicos y asserta deltas o
conteos relativos. No hay teardown destructivo porque `movimiento_stock` es de
sólo agregado (RN-12) y su FK `NO ACTION` pincha los libros vendidos.

El stock inicial se siembra siempre con `LibroRepository.aplicar_movimiento`,
nunca escribiendo `Libro(stock=N)` directo (RN-11).
"""
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import IdentidadActual
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.libros.models import Libro, MovimientoStock
from app.modules.libros.repository import LibroRepository
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
    usuario_id: int,
) -> Libro:
    """Crea el libro con stock 0 y siembra el stock por el punto único."""
    l = Libro(
        isbn=f"isbn-{uuid.uuid4().hex}",
        titulo=titulo,
        precio=precio,
        stock=0,
        editorial_id=editorial.id,
    )
    session.add(l)
    await session.flush()
    if stock:
        await LibroRepository(session).aplicar_movimiento(
            l, stock, "Stock inicial", usuario_id
        )
    await session.commit()
    return l



async def _crear_base(session: AsyncSession) -> tuple[Usuario, Editorial, Cliente]:
    vendedor = await _crear_usuario_vendedor(
        session, f"v-{uuid.uuid4().hex}@example.com"
    )
    editorial = await _crear_editorial(session)
    cliente = await _crear_cliente(session, f"c-{uuid.uuid4().hex}@example.com")
    return vendedor, editorial, cliente


def _actual(vendedor: Usuario) -> IdentidadActual:
    return IdentidadActual(
        usuario=vendedor,
        roles_db=("VENDEDOR",),
        roles_token=(),
    )


async def _conteos(sessionmaker) -> tuple[int, int, int]:
    async with sessionmaker() as session:
        ventas = (
            await session.execute(select(func.count()).select_from(Venta))
        ).scalar_one()
        renglones = (
            await session.execute(select(func.count()).select_from(RenglonVenta))
        ).scalar_one()
        movimientos = (
            await session.execute(select(func.count()).select_from(MovimientoStock))
        ).scalar_one()
    return int(ventas), int(renglones), int(movimientos)


async def _stock_y_suma(sessionmaker, libro_id: int) -> tuple[int, Decimal]:
    async with sessionmaker() as session:
        stock = (
            await session.execute(select(Libro.stock).where(Libro.id == libro_id))
        ).scalar_one()
        suma = (
            await session.execute(
                select(func.coalesce(func.sum(MovimientoStock.cantidad), 0)).where(
                    MovimientoStock.libro_id == libro_id
                )
            )
        ).scalar_one()
    return int(stock), Decimal(suma or 0)


class TestServicioCrearVenta:
    async def test_venta_valida_201(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            vendedor, editorial, cliente = await _crear_base(session)
            libro1 = await _crear_libro(
                session, editorial, "Libro A", Decimal("10.00"), 10, vendedor.id
            )
            libro2 = await _crear_libro(
                session, editorial, "Libro B", Decimal("20.00"), 5, vendedor.id
            )

            uow = VentasUnitOfWork(session)
            data = VentaCreate(
                cliente_id=cliente.id,
                renglones=[
                    {"libro_id": libro1.id, "cantidad": 2},
                    {"libro_id": libro2.id, "cantidad": 1},
                ],
            )

            venta = await registrar_venta(uow, data, actual=_actual(vendedor))

        assert venta.id is not None
        assert venta.cliente_id == cliente.id
        assert venta.total == Decimal("40.00")  # 2*10 + 1*20

        async with db_sessionmaker() as session:
            result = await session.execute(
                select(RenglonVenta).where(RenglonVenta.venta_id == venta.id)
            )
            renglones = list(result.scalars().all())
            movimientos = list(
                (
                    await session.execute(
                        select(MovimientoStock).where(
                            MovimientoStock.venta_id == venta.id
                        )
                    )
                ).scalars().all()
            )

        assert len(renglones) == 2
        precios = {r.libro_id: r.precio_unitario for r in renglones}
        assert precios[libro1.id] == Decimal("10.00")
        assert precios[libro2.id] == Decimal("20.00")
        assert len(movimientos) == 2
        for m in movimientos:
            assert m.cantidad < 0
            assert m.motivo == "Venta"
            assert m.usuario_id == vendedor.id
            assert m.venta_id == venta.id

        stock1, suma1 = await _stock_y_suma(db_sessionmaker, libro1.id)
        stock2, suma2 = await _stock_y_suma(db_sessionmaker, libro2.id)
        assert stock1 == 8 and suma1 == Decimal("8")  # +10 inicial -2 venta
        assert stock2 == 4 and suma2 == Decimal("4")  # +5 inicial -1 venta
        assert stock1 == suma1
        assert stock2 == suma2

    async def test_stock_insuficiente_409_sin_escribir(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            vendedor, editorial, cliente = await _crear_base(session)
            libro = await _crear_libro(
                session, editorial, "Libro Stock", Decimal("10.00"), 1, vendedor.id
            )
            libro_id = libro.id

        antes = await _conteos(db_sessionmaker)
        stock_antes, suma_antes = await _stock_y_suma(db_sessionmaker, libro_id)

        async with db_sessionmaker() as session:
            uow = VentasUnitOfWork(session)
            data = VentaCreate(
                cliente_id=cliente.id,
                renglones=[{"libro_id": libro_id, "cantidad": 5}],
            )
            with pytest.raises(HTTPException) as excinfo:
                await registrar_venta(uow, data, actual=_actual(vendedor))

        assert excinfo.value.status_code == 409
        assert "Stock insuficiente" in excinfo.value.detail
        assert await _conteos(db_sessionmaker) == antes
        stock_despues, suma_despues = await _stock_y_suma(db_sessionmaker, libro_id)
        assert stock_despues == stock_antes
        assert suma_despues == suma_antes

    async def test_cliente_inexistente_409_sin_escribir(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            vendedor, editorial, _cliente = await _crear_base(session)
            libro = await _crear_libro(
                session, editorial, "Libro C", Decimal("10.00"), 10, vendedor.id
            )
            libro_id = libro.id

        antes = await _conteos(db_sessionmaker)
        stock_antes, _ = await _stock_y_suma(db_sessionmaker, libro_id)

        async with db_sessionmaker() as session:
            uow = VentasUnitOfWork(session)
            data = VentaCreate(
                cliente_id=999999999,
                renglones=[{"libro_id": libro_id, "cantidad": 1}],
            )
            with pytest.raises(HTTPException) as excinfo:
                await registrar_venta(uow, data, actual=_actual(vendedor))

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == "El cliente indicado no existe"
        assert await _conteos(db_sessionmaker) == antes
        stock_despues, _ = await _stock_y_suma(db_sessionmaker, libro_id)
        assert stock_despues == stock_antes

    async def test_libro_inexistente_409_sin_escribir(self, db_sessionmaker):
        async with db_sessionmaker() as session:
            vendedor, _editorial, cliente = await _crear_base(session)

        antes = await _conteos(db_sessionmaker)

        async with db_sessionmaker() as session:
            uow = VentasUnitOfWork(session)
            data = VentaCreate(
                cliente_id=cliente.id,
                renglones=[{"libro_id": 999999999, "cantidad": 1}],
            )
            with pytest.raises(HTTPException) as excinfo:
                await registrar_venta(uow, data, actual=_actual(vendedor))

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == "Uno o más libros indicados no existen"
        assert await _conteos(db_sessionmaker) == antes

    async def test_duplicado_con_stock_agregado_insuficiente_409_sin_escribir(
        self, db_sessionmaker
    ):
        async with db_sessionmaker() as session:
            vendedor, editorial, cliente = await _crear_base(session)
            libro = await _crear_libro(
                session, editorial, "Libro Duplicado", Decimal("10.00"), 3, vendedor.id
            )
            libro_id = libro.id

        antes = await _conteos(db_sessionmaker)
        stock_antes, _ = await _stock_y_suma(db_sessionmaker, libro_id)

        async with db_sessionmaker() as session:
            uow = VentasUnitOfWork(session)
            data = VentaCreate(
                cliente_id=cliente.id,
                renglones=[
                    {"libro_id": libro_id, "cantidad": 2},
                    {"libro_id": libro_id, "cantidad": 2},
                ],
            )
            with pytest.raises(HTTPException) as excinfo:
                await registrar_venta(uow, data, actual=_actual(vendedor))

        assert excinfo.value.status_code == 409
        assert "Stock insuficiente" in excinfo.value.detail
        assert await _conteos(db_sessionmaker) == antes
        stock_despues, _ = await _stock_y_suma(db_sessionmaker, libro_id)
        assert stock_despues == stock_antes
