"""Lógica de negocio del módulo `ventas` (TP cap. 1-4)."""

import logging
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.clientes.models import Cliente
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.libros.models import Libro

logger = logging.getLogger("libreria.ventas")


async def crear(session: AsyncSession, cliente_id: int, renglones_data) -> Venta:
    # verificar cliente existe
    cliente = await session.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=409, detail="Cliente inexistente")
    # duplicados
    seen = set()
    for r in renglones_data:
        if r.libro_id in seen:
            raise HTTPException(status_code=422, detail="Libro repetido en la venta")
        seen.add(r.libro_id)

    # cargar libros y validar stock antes de escribir la venta
    libros = {}
    for r in renglones_data:
        libro = await session.get(Libro, r.libro_id)
        if libro is None:
            raise HTTPException(status_code=409, detail="Libro inexistente")
        libros[r.libro_id] = libro

    for r in renglones_data:
        libro = libros[r.libro_id]
        if libro.stock < r.cantidad:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para '{libro.titulo}'",
            )

    venta = Venta(cliente_id=cliente_id, total=Decimal("0"))
    session.add(venta)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la venta")

    total = Decimal("0")
    for r in renglones_data:
        libro = libros[r.libro_id]
        precio = libro.precio
        libro.stock -= r.cantidad
        renglon = RenglonVenta(
            venta_id=venta.id,
            libro_id=r.libro_id,
            cantidad=r.cantidad,
            precio_unitario=precio,
        )
        session.add(renglon)
        total += precio * r.cantidad
    venta.total = total
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la venta")
    await session.refresh(venta)
    return venta


async def obtener(session: AsyncSession, venta_id: int) -> Venta:
    stmt = (
        select(Venta)
        .where(Venta.id == venta_id)
        .options(
            joinedload(Venta.cliente),
            selectinload(Venta.renglones).joinedload(RenglonVenta.libro),
        )
    )
    result = await session.execute(stmt)
    venta = result.unique().scalar_one_or_none()
    if venta is None:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return venta


async def listar(session: AsyncSession, limit: int = 20, offset: int = 0) -> List[Venta]:
    stmt = (
        select(Venta)
        .options(joinedload(Venta.cliente))
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.unique().scalars().all())


async def ventas_de_cliente(session: AsyncSession, cliente_id: int) -> List[Venta]:
    from app.modules.clientes.service import obtener as obtener_cliente
    await obtener_cliente(session, cliente_id)
    stmt = select(Venta).where(Venta.cliente_id == cliente_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())