"""Unit of Work del módulo `editoriales`."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.editoriales.repository import EditorialRepository


class EditorialesUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.editoriales = EditorialRepository(session)


async def get_editoriales_uow(
    session: AsyncSession = Depends(get_session),
) -> EditorialesUnitOfWork:
    return EditorialesUnitOfWork(session)