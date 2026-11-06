"""Unit of Work del módulo `ventas`."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository
from app.modules.ventas.repository import VentaRepository


class VentasUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.ventas = VentaRepository(session)
        self.clientes = ClienteRepository(session)


async def get_ventas_uow(
    session: AsyncSession = Depends(get_session),
) -> VentasUnitOfWork:
    return VentasUnitOfWork(session)