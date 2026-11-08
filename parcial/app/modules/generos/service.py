"""Lógica de negocio del módulo `generos`.

Contrato de errores (CV-08): el orden es **404 → 409 → 422**. `obtener` y
`libros_de` sólo producen 404; `crear` traduce el nombre duplicado
(`genero_nombre_key`) a 409 y la validación del schema a 422.
"""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import traducir_integrity_error
from app.core.paginacion import Pagina, paginar
from app.modules.generos.models import Genero
from app.modules.generos.schemas import GeneroCreate
from app.modules.generos.unit_of_work import GenerosUnitOfWork
from app.modules.libros.models import Libro


async def crear(uow: GenerosUnitOfWork, data: GeneroCreate) -> Genero:
    obj = Genero(nombre=data.nombre)
    try:
        async with uow:
            await uow.generos.add(obj)
    except IntegrityError as exc:
        raise traducir_integrity_error(exc)
    return obj


async def obtener(uow: GenerosUnitOfWork, genero_id: int) -> Genero:
    async with uow:
        obj = await uow.generos.get_by_id(genero_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Género no encontrado")
    return obj


async def listar(
    uow: GenerosUnitOfWork, page: int = 1, size: int = 20
) -> Pagina[Genero]:
    async with uow:
        stmt = select(Genero)
        pagina = await paginar(uow.session, stmt, page, size)
    return pagina


async def libros_de(uow: GenerosUnitOfWork, genero_id: int) -> List[Libro]:
    async with uow:
        obj = await uow.generos.get_by_id(genero_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Género no encontrado")
        libros = await uow.generos.libros_de(genero_id)
    return libros