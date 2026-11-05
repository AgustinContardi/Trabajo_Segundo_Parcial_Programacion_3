"""Lógica de negocio del módulo `generos` (TP cap. 1-4).

Orden de resolución de errores (CV-08): 404 → 403 → 409 → 422.
"""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import traducir_integrity_error
from app.core.paginacion import paginar
from app.modules.generos.models import Genero
from app.modules.generos.schemas import GeneroCreate
from app.modules.libros.models import Libro


async def crear(session: AsyncSession, data: GeneroCreate) -> Genero:
    obj = Genero(nombre=data.nombre)
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, genero_id: int) -> Genero:
    obj = await session.get(Genero, genero_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Género no encontrado")
    return obj


async def listar(session: AsyncSession, page: int = 1, size: int = 20):
    stmt = select(Genero)
    return await paginar(session, stmt, page, size)


async def libros_de(session: AsyncSession, genero_id: int) -> List[Libro]:
    await obtener(session, genero_id)
    stmt = select(Libro).where(Libro.genero_id == genero_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())