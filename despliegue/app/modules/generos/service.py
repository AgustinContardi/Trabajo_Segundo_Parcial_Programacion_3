"""Lógica de negocio del módulo `generos` (TP cap. 1-4)."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.generos.models import Genero
from app.modules.generos.schemas import GeneroCreate
from app.modules.libros.models import Libro


async def crear(session: AsyncSession, data: GeneroCreate) -> Genero:
    obj = Genero(nombre=data.nombre)
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un género con ese nombre")
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, genero_id: int) -> Genero:
    obj = await session.get(Genero, genero_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Género no encontrado")
    return obj


async def listar(session: AsyncSession) -> List[Genero]:
    stmt = select(Genero)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def libros_de(session: AsyncSession, genero_id: int) -> List[Libro]:
    await obtener(session, genero_id)
    stmt = select(Libro).where(Libro.genero_id == genero_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())