"""Unit of Work del módulo `autores`."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.autores.repository import AutorRepository


class AutoresUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.autores = AutorRepository(session)


async def get_autores_uow(
    session: AsyncSession = Depends(get_session),
) -> AutoresUnitOfWork:
    return AutoresUnitOfWork(session)