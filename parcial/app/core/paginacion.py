"""Paginación canónica: envoltorio ``{items, total, page, size, pages}``.

Contrato de este módulo (CV-01):
- Quién construye: el router (vía dependencia) instancia el Unit of Work, que
  a su vez instancia los repositorios; la paginación se invoca con la sesión
  y la consulta armada.
- Quién abre: el servicio abre el Unit of Work con ``async with``.
- Quién confirma: sólo ``__aexit__`` del Unit of Work.
- Quién cierra: ``get_session``.

Valida ``page`` y ``size``, cuenta con los mismos filtros y pagina.
"""

import math
from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    """Envoltorio canónico de paginación."""

    model_config = {"from_attributes": True}

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


async def paginar(
    session: AsyncSession,
    stmt: Any,
    page: int = 1,
    size: int = 20,
) -> Pagina[Any]:
    """Pagina una consulta ``SELECT`` ya filtrada.

    Valida ``size`` (1..100) y ``page`` (>= 1 y dentro de rango), cuenta el
    total con los mismos filtros y devuelve el envoltorio canónico.
    """
    if size < 1 or size > 100:
        raise HTTPException(
            status_code=422,
            detail=f"El tamaño de página debe estar entre 1 y 100 (recibido {size})",
        )

    total_stmt = select(func.count()).select_from(stmt.subquery())
    result = await session.execute(total_stmt)
    total = int(result.scalar_one())

    pages = max(1, math.ceil(total / size))

    if page < 1 or page > pages:
        raise HTTPException(
            status_code=422,
            detail=f"La página {page} no existe: hay {pages}",
        )

    rows = await session.execute(stmt.offset((page - 1) * size).limit(size))
    items = list(rows.scalars().all())

    return Pagina(items=items, total=total, page=page, size=size, pages=pages)