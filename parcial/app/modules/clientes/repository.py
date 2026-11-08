"""Repositorio del módulo `clientes`.

Toda precarga (`selectinload`/`joinedload`) vive acá (CV-02); ni el servicio ni
el router precargan. Sólo `flush()` a través de `BaseRepository`.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.paginacion import Pagina, paginar
from app.core.repository import BaseRepository
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.ventas.models import Venta


class ClienteRepository(BaseRepository[Cliente]):
    def __init__(self, session: Any) -> None:
        super().__init__(session, Cliente)

    async def get_by_id(self, id: Any) -> Cliente | None:
        """Obtiene un cliente por id precargando `perfil` y `usuario`.

        La precarga se declara adentro de este método (CV-02); otros métodos
        (como `ventas_de`) no la necesitan y no la cargan.
        """
        stmt = (
            select(Cliente)
            .where(Cliente.id == id)
            .options(
                selectinload(Cliente.perfil),
                selectinload(Cliente.usuario),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_usuario_id(self, usuario_id: int) -> Cliente | None:
        """Resuelve la ficha de cliente ligada a un usuario (usuario_id)."""
        stmt = select(Cliente).where(Cliente.usuario_id == usuario_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def add_perfil(self, perfil: PerfilCliente) -> PerfilCliente:
        """Agrega un perfil y hace `flush()` para obtener su id."""
        self._session.add(perfil)
        await self._session.flush()
        return perfil

    @staticmethod
    def ventas_de_stmt(cliente_id: int):
        """Statement de ventas del cliente con orden determinista por id.

        `Venta.id` es único y ya es el desempate del listado general, así que
        la paginación no repite ni omite filas (C-07).
        """
        return (
            select(Venta)
            .where(Venta.cliente_id == cliente_id)
            .order_by(Venta.id)
        )

    async def ventas_de(
        self, cliente_id: int, page: int = 1, size: int = 20
    ) -> Pagina[Venta]:
        """Ventas del cliente, paginadas, consultando sobre `venta`."""
        return await paginar(
            self._session, self.ventas_de_stmt(cliente_id), page, size
        )
