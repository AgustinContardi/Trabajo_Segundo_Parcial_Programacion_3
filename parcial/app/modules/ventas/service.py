"""Lógica de negocio del módulo `ventas` (TP cap. 1-4).

Orden de resolución de errores (CV-08): 404 → 403 → 409 → 422.
"""

import asyncio
import logging
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import traducir_integrity_error
from app.core.paginacion import paginar
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

    venta = Venta(cliente_id=cliente_id, total=Decimal("0"))
    session.add(venta)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)

    total = Decimal("0")
    for r in renglones_data:
        libro = await session.get(Libro, r.libro_id)
        if libro is None:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Libro inexistente")
        precio = libro.precio
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
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
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


async def listar(session: AsyncSession, page: int = 1, size: int = 20):
    stmt = select(Venta).options(joinedload(Venta.cliente))
    return await paginar(session, stmt, page, size)


async def ventas_de_cliente(session: AsyncSession, cliente_id: int) -> List[Venta]:
    from app.modules.clientes.service import obtener as obtener_cliente
    await obtener_cliente(session, cliente_id)
    stmt = select(Venta).where(Venta.cliente_id == cliente_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def aviso_comprobante(venta_id: int) -> None:
    await asyncio.sleep(0.5)
    logger.info("Comprobante de venta %s enviado al cliente", venta_id)