"""Repositorio del módulo `ventas`.

Toda precarga (`selectinload`/`joinedload`) vive acá (CV-03); ni el servicio ni
el router precargan. Sólo `flush()` a través de `BaseRepository`.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.paginacion import Pagina, paginar
from app.core.repository import BaseRepository
from app.modules.ventas.models import RenglonVenta, Venta


class RenglonVentaRepository(BaseRepository[RenglonVenta]):
    def __init__(self, session: Any) -> None:
        super().__init__(session, RenglonVenta)


class VentaRepository(BaseRepository[Venta]):
    def __init__(self, session: Any) -> None:
        super().__init__(session, Venta)

    async def get_by_id(self, id: Any) -> Venta | None:
        """Obtiene una venta por id precargando cliente, renglones y el libro
        de cada renglón (incluidos los dados de baja).

        La precarga se declara adentro de este método (CV-03); número de
        consultas fijo (3 `SELECT`), independiente de la cantidad de renglones.
        """
        stmt = (
            select(Venta)
            .where(Venta.id == id)
            .options(
                selectinload(Venta.cliente),
                selectinload(Venta.renglones).selectinload(RenglonVenta.libro),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def listar(self, page: int = 1, size: int = 20) -> Pagina[Venta]:
        """Listado paginado de ventas con precarga de cliente, orden estable."""
        stmt = (
            select(Venta)
            .options(selectinload(Venta.cliente))
            .order_by(Venta.id.desc())
        )
        return await paginar(self._session, stmt, page, size)

    async def ventas_de_cliente(
        self, cliente_id: int, page: int = 1, size: int = 20
    ) -> Pagina[Venta]:
        """Ventas de un cliente, paginadas, con precarga de cliente."""
        stmt = (
            select(Venta)
            .where(Venta.cliente_id == cliente_id)
            .options(selectinload(Venta.cliente))
            .order_by(Venta.id.desc())
        )
        return await paginar(self._session, stmt, page, size)