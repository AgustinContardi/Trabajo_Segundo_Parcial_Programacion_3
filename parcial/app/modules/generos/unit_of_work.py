"""Unit of Work del módulo `generos`."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.generos.repository import GeneroRepository


class GenerosUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.generos = GeneroRepository(session)


async def get_generos_uow(
    session: AsyncSession = Depends(get_session),
) -> GenerosUnitOfWork:
    return GenerosUnitOfWork(session)