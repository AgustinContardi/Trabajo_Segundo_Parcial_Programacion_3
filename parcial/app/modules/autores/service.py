"""Lógica de negocio del módulo `autores`."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import traducir_integrity_error
from app.core.paginacion import Pagina, paginar
from app.modules.autores.models import Autor
from app.modules.autores.schemas import AutorCreate, AutorUpdate
from app.modules.autores.unit_of_work import AutoresUnitOfWork
from app.modules.libros.models import Libro


async def crear(uow: AutoresUnitOfWork, data: AutorCreate) -> Autor:
    obj = Autor(nombre=data.nombre, nacionalidad=data.nacionalidad)
    try:
        async with uow:
            await uow.autores.add(obj)
    except IntegrityError as exc:
        raise traducir_integrity_error(exc)
    return obj


async def obtener(uow: AutoresUnitOfWork, autor_id: int) -> Autor:
    async with uow:
        obj = await uow.autores.get_by_id(autor_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    return obj


async def listar(
    uow: AutoresUnitOfWork, page: int = 1, size: int = 20
) -> Pagina[Autor]:
    async with uow:
        stmt = select(Autor)
        pagina = await paginar(uow.session, stmt, page, size)
    return pagina


async def actualizar(
    uow: AutoresUnitOfWork, autor_id: int, data: AutorUpdate
) -> Autor:
    async with uow:
        obj = await uow.autores.get_by_id(autor_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Autor no encontrado")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        try:
            await uow.autores.update(obj)
        except IntegrityError as exc:
            raise traducir_integrity_error(exc)
    return obj


async def libros_de(uow: AutoresUnitOfWork, autor_id: int) -> List[Libro]:
    async with uow:
        obj = await uow.autores.get_by_id(autor_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Autor no encontrado")
        libros = await uow.autores.libros_de(autor_id)
    return libros