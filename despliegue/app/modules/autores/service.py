"""Lógica de negocio del módulo `autores` (TP cap. 1-4)."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autores.models import Autor
from app.modules.autores.schemas import AutorCreate, AutorUpdate
from app.modules.libros.models import Libro, LibroAutor


async def crear(session: AsyncSession, data: AutorCreate) -> Autor:
    obj = Autor(nombre=data.nombre, nacionalidad=data.nacionalidad)
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


async def obtener(session: AsyncSession, autor_id: int) -> Autor:
    obj = await session.get(Autor, autor_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    return obj


async def actualizar(session: AsyncSession, autor_id: int, data: AutorUpdate) -> Autor:
    obj = await obtener(session, autor_id)
    if data.nombre is not None:
        obj.nombre = data.nombre
    if data.nacionalidad is not None:
        obj.nacionalidad = data.nacionalidad
    await session.flush()
    await session.refresh(obj)
    return obj


async def libros_de(session: AsyncSession, autor_id: int):
    await obtener(session, autor_id)
    stmt = (
        select(Libro, LibroAutor.rol, LibroAutor.orden)
        .join(LibroAutor, LibroAutor.libro_id == Libro.id)
        .where(LibroAutor.autor_id == autor_id)
    )
    result = await session.execute(stmt)
    return result.all()