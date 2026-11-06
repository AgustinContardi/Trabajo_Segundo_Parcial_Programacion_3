"""Lógica de negocio del módulo `ventas` (seis capas, C-10).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una
sesión asincrónica ni construye el UoW (CV-01). Orden de errores (CV-08):
404 → 403 → 409 → 422.
"""

from fastapi import HTTPException

from app.core.dependencies import IdentidadActual
from app.core.paginacion import Pagina
from app.modules.clientes.models import Cliente
from app.modules.ventas.models import Venta
from app.modules.ventas.unit_of_work import VentasUnitOfWork


def _usuario_id(actual: IdentidadActual) -> int:
    return actual.usuario.id


def _es_personal(actual: IdentidadActual) -> bool:
    roles = {str(rol).strip().upper() for rol in actual.roles_db}
    return bool(roles & {"VENDEDOR", "ADMIN"})


async def listar(uow: VentasUnitOfWork, page: int = 1, size: int = 20) -> Pagina[Venta]:
    async with uow:
        pagina = await uow.ventas.listar(page, size)
    return pagina


async def obtener(
    uow: VentasUnitOfWork, venta_id: int, *, actual: IdentidadActual
) -> Venta:
    """Lee una venta y decide personal o dueño; el 404 precede al 403 (CV-08)."""
    async with uow:
        venta = await uow.ventas.get_by_id(venta_id)
        if venta is None:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        es_personal = _es_personal(actual)
        es_dueno = False
        if not es_personal:
            cliente = await uow.clientes.get_by_usuario_id(_usuario_id(actual))
            if cliente is not None and cliente.id == venta.cliente_id:
                es_dueno = True
        if not (es_personal or es_dueno):
            raise HTTPException(status_code=403, detail="No autorizado")
    return venta


async def mis_ventas(
    uow: VentasUnitOfWork,
    actual: IdentidadActual,
    page: int = 1,
    size: int = 20,
) -> Pagina[Venta]:
    uid = _usuario_id(actual)
    async with uow:
        cliente = await uow.clientes.get_by_usuario_id(uid)
        if cliente is None:
            if page < 1:
                raise HTTPException(status_code=422, detail=f"La página {page} no existe: hay 1")
            if page > 1:
                raise HTTPException(status_code=422, detail=f"La página {page} no existe: hay 1")
            return Pagina(items=[], total=0, page=page, size=size, pages=1)
        pagina = await uow.ventas.ventas_de_cliente(cliente.id, page, size)
    return pagina