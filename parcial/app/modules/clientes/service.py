"""Lógica de negocio del módulo `clientes` (TP cap. 1-4).

Orden de resolución de errores (CV-08): 404 → 403 → 409 → 422.
"""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import traducir_integrity_error
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.ventas.models import Venta


async def crear(session: AsyncSession, nombre: str, email: str) -> Cliente:
    obj = Cliente(nombre=nombre, email=email)
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, cliente_id: int) -> Cliente:
    stmt = select(Cliente).where(Cliente.id == cliente_id).options(selectinload(Cliente.perfil))
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return obj


async def actualizar(session: AsyncSession, cliente_id: int, data) -> Cliente:
    obj = await obtener(session, cliente_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
    await session.refresh(obj)
    return obj


async def crear_perfil(session: AsyncSession, cliente_id: int, telefono=None, direccion=None) -> PerfilCliente:
    await obtener(session, cliente_id)  # 404 si no existe
    # verificar existente
    existing = await session.execute(
        select(PerfilCliente).where(PerfilCliente.cliente_id == cliente_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="El cliente ya tiene perfil")
    perfil = PerfilCliente(cliente_id=cliente_id, telefono=telefono, direccion=direccion)
    session.add(perfil)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
    await session.refresh(perfil)
    return perfil


async def ventas_de(session: AsyncSession, cliente_id: int) -> List[Venta]:
    await obtener(session, cliente_id)
    stmt = select(Venta).where(Venta.cliente_id == cliente_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())