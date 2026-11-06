"""Lógica de negocio del módulo `editoriales`.

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una
sesion asincrona ni construye el UoW (CV-01). Orden de errores (CV-08):
404 → 403 → 409 → 422.
"""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import traducir_integrity_error
from app.core.paginacion import Pagina, paginar
from app.modules.editoriales.models import Editorial
from app.modules.editoriales.schemas import EditorialCreate, EditorialUpdate
from app.modules.editoriales.unit_of_work import EditorialesUnitOfWork
from app.modules.libros.models import Libro


async def crear(uow: EditorialesUnitOfWork, data: EditorialCreate) -> Editorial:
    obj = Editorial(nombre=data.nombre, pais=data.pais)
    try:
        async with uow:
            await uow.editoriales.add(obj)
    except IntegrityError as exc:
        raise traducir_integrity_error(exc)
    return obj


async def obtener(uow: EditorialesUnitOfWork, editorial_id: int) -> Editorial:
    async with uow:
        obj = await uow.editoriales.get_by_id(editorial_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Editorial no encontrada")
    return obj


async def listar(
    uow: EditorialesUnitOfWork, page: int = 1, size: int = 20
) -> Pagina[Editorial]:
    async with uow:
        stmt = select(Editorial)
        pagina = await paginar(uow.session, stmt, page, size)
    return pagina


async def actualizar(
    uow: EditorialesUnitOfWork, editorial_id: int, data: EditorialUpdate
) -> Editorial:
    async with uow:
        obj = await uow.editoriales.get_by_id(editorial_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Editorial no encontrada")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        try:
            await uow.editoriales.update(obj)
        except IntegrityError as exc:
            raise traducir_integrity_error(exc)
    return obj


async def libros_de(uow: EditorialesUnitOfWork, editorial_id: int) -> List[Libro]:
    async with uow:
        obj = await uow.editoriales.get_by_id(editorial_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Editorial no encontrada")
        libros = await uow.editoriales.libros_de(editorial_id)
    return libros