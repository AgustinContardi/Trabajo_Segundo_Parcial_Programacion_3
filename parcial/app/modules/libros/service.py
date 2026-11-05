"""Lógica de negocio del módulo `libros` (TP cap. 1-4).

Orden de resolución de errores (CV-08): 404 → 403 → 409 → 422.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.errors import traducir_integrity_error
from app.core.paginacion import paginar
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
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
    # autores
    for a in data.autores:
        la = LibroAutor(libro_id=libro.id, autor_id=a.autor_id, rol=a.rol, orden=a.orden)
        session.add(la)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
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
    page: int = 1,
    size: int = 20,
    titulo: Optional[str] = None,
    genero_id: Optional[int] = None,
):
    stmt = select(Libro).options(joinedload(Libro.editorial), joinedload(Libro.genero))
    if titulo:
        stmt = stmt.where(Libro.titulo.ilike(f"%{titulo}%"))
    if genero_id is not None:
        stmt = stmt.where(Libro.genero_id == genero_id)
    return await paginar(session, stmt, page, size)


async def actualizar(session: AsyncSession, libro_id: int, data: LibroUpdate) -> Libro:
    libro = await session.get(Libro, libro_id)
    if libro is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(libro, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_integrity_error(exc)
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