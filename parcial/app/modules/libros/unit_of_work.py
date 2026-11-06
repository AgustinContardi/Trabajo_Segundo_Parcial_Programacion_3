"""Unit of Work del modulo libros."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.libros.repository import LibroRepository


class LibrosUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.libros = LibroRepository(session)


async def get_libros_uow(
    session: AsyncSession = Depends(get_session),
) -> LibrosUnitOfWork:
    return LibrosUnitOfWork(session)