"""Repositorio del módulo `clientes`.

Toda precarga (`selectinload`/`joinedload`) vive acá (CV-03); ni el servicio ni
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

        La precarga se declara adentro de este método (CV-03); otros métodos
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

    async def ventas_de(
        self, cliente_id: int, page: int = 1, size: int = 20
    ) -> Pagina[Venta]:
        """Ventas del cliente, paginadas, consultando sobre `venta`."""
        stmt = select(Venta).where(Venta.cliente_id == cliente_id)
        return await paginar(self._session, stmt, page, size)
