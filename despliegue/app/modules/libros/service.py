"""Lógica de negocio del módulo `libros` (TP cap. 1-4)."""

from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.libros.models import Libro, LibroAutor
from app.modules.libros.schemas import (
    EditorialRef,
    GeneroRef,
    LibroAutorRead,
    LibroCreate,
    LibroDetailRead,
    LibroRead,
    LibroUpdate,
)
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.autores.models import Autor


async def crear(session: AsyncSession, data: LibroCreate) -> Libro:
    libro = Libro(
        isbn=data.isbn,
        titulo=data.titulo,
        precio=data.precio,
        stock=data.stock,
        editorial_id=data.editorial_id,
        genero_id=data.genero_id,
    )
    session.add(libro)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el libro (datos inválidos)")
    # autores
    for a in data.autores:
        la = LibroAutor(libro_id=libro.id, autor_id=a.autor_id, rol=a.rol, orden=a.orden)
        session.add(la)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el libro (datos inválidos)")
    await session.refresh(libro)
    return libro


async def obtener(session: AsyncSession, libro_id: int) -> Libro:
    stmt = (
        select(Libro)
        .where(Libro.id == libro_id)
        .options(
            joinedload(Libro.editorial),
            joinedload(Libro.genero),
            selectinload(Libro.autorias).joinedload(LibroAutor.autor),
        )
    )
    result = await session.execute(stmt)
    libro = result.unique().scalar_one_or_none()
    if libro is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return libro


async def listar(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    titulo: Optional[str] = None,
    genero_id: Optional[int] = None,
) -> List[Libro]:
    stmt = select(Libro).options(joinedload(Libro.editorial), joinedload(Libro.genero))
    if titulo:
        stmt = stmt.where(Libro.titulo.ilike(f"%{titulo}%"))
    if genero_id is not None:
        stmt = stmt.where(Libro.genero_id == genero_id)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.unique().scalars().all())


async def actualizar(session: AsyncSession, libro_id: int, data: LibroUpdate) -> Libro:
    libro = await session.get(Libro, libro_id)
    if libro is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if data.titulo is not None:
        libro.titulo = data.titulo
    if data.precio is not None:
        libro.precio = data.precio
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el libro")
    # recargar con relaciones
    return await obtener(session, libro_id)


async def to_detail_read(libro: Libro) -> LibroDetailRead:
    autores = []
    for a in libro.autorias:
        autores.append(
            LibroAutorRead(
                autor_id=a.autor_id,
                rol=a.rol,
                orden=a.orden,
                autor_nombre=a.autor.nombre if a.autor is not None else None,
            )
        )
    return LibroDetailRead(
        id=libro.id,
        isbn=libro.isbn,
        titulo=libro.titulo,
        precio=libro.precio,
        stock=libro.stock,
        editorial_id=libro.editorial_id,
        genero_id=libro.genero_id,
        editorial=(
            EditorialRef(id=libro.editorial.id, nombre=libro.editorial.nombre, pais=libro.editorial.pais)
            if libro.editorial is not None
            else None
        ),
        genero=(
            GeneroRef(id=libro.genero.id, nombre=libro.genero.nombre)
            if libro.genero is not None
            else None
        ),
        autores=autores,
    )


async def to_read(libro: Libro) -> LibroRead:
    return LibroRead(
        id=libro.id,
        isbn=libro.isbn,
        titulo=libro.titulo,
        precio=libro.precio,
        stock=libro.stock,
        editorial_id=libro.editorial_id,
        genero_id=libro.genero_id,
        editorial=(
            EditorialRef(id=libro.editorial.id, nombre=libro.editorial.nombre, pais=libro.editorial.pais)
            if libro.editorial is not None
            else None
        ),
        genero=(
            GeneroRef(id=libro.genero.id, nombre=libro.genero.nombre)
            if libro.genero is not None
            else None
        ),
    )