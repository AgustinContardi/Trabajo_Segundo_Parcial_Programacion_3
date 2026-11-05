"""Lógica de negocio del módulo `editoriales` (TP cap. 1-4)."""

from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.editoriales.models import Editorial
from app.modules.editoriales.schemas import EditorialCreate, EditorialRead, EditorialUpdate
from app.modules.libros.models import Libro


async def crear(session: AsyncSession, data: EditorialCreate) -> Editorial:
    obj = Editorial(nombre=data.nombre, pais=data.pais)
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una editorial con ese nombre")
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, editorial_id: int) -> Editorial:
    obj = await session.get(Editorial, editorial_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Editorial no encontrada")
    return obj


async def listar(session: AsyncSession, limit: int = 20, offset: int = 0) -> List[Editorial]:
    stmt = select(Editorial).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def actualizar(session: AsyncSession, editorial_id: int, data: EditorialUpdate) -> Editorial:
    obj = await obtener(session, editorial_id)
    if data.nombre is not None:
        obj.nombre = data.nombre
    if data.pais is not None:
        obj.pais = data.pais
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una editorial con ese nombre")
    await session.refresh(obj)
    return obj


async def libros_de(session: AsyncSession, editorial_id: int) -> List[Libro]:
    await obtener(session, editorial_id)  # 404 si no existe
    stmt = select(Libro).where(Libro.editorial_id == editorial_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())