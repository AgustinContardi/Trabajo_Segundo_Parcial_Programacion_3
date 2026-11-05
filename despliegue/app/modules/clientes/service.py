"""Lógica de negocio del módulo `clientes` (TP cap. 1-4)."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.ventas.models import Venta


async def crear(session: AsyncSession, nombre: str, email: str) -> Cliente:
    obj = Cliente(nombre=nombre, email=email)
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un cliente con ese email")
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, cliente_id: int) -> Cliente:
    stmt = select(Cliente).where(Cliente.id == cliente_id).options(selectinload(Cliente.perfil))
    result = await session.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return obj


async def actualizar(session: AsyncSession, cliente_id: int, nombre=None, email=None) -> Cliente:
    obj = await obtener(session, cliente_id)
    if nombre is not None:
        obj.nombre = nombre
    if email is not None:
        obj.email = email
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un cliente con ese email")
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
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="El cliente ya tiene perfil")
    await session.refresh(perfil)
    return perfil


async def ventas_de(session: AsyncSession, cliente_id: int) -> List[Venta]:
    await obtener(session, cliente_id)
    stmt = select(Venta).where(Venta.cliente_id == cliente_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())