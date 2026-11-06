"""Lógica de negocio del módulo `ventas` (seis capas, C-10).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una
sesión asincrónica ni construye el UoW (CV-01). Orden de errores (CV-08):
404 → 403 → 409 → 422.
"""

from typing import Any, Optional

from fastapi import HTTPException

from app.core.paginacion import Pagina
from app.modules.clientes.models import Cliente
from app.modules.ventas.models import Venta
from app.modules.ventas.unit_of_work import VentasUnitOfWork


def _usuario_id(actual: Any) -> Optional[int]:
    if actual is None:
        return None
    if isinstance(actual, int):
        return actual
    if isinstance(actual, dict):
        for key in ("id", "usuario_id", "sub"):
            if key in actual and actual[key] is not None:
                return int(actual[key])
        return None
    for attr in ("id", "usuario_id", "sub"):
        if hasattr(actual, attr):
            val = getattr(actual, attr)
            if val is not None:
                return int(val)
    return None


def _roles_de(actual: Any) -> Optional[list[Any]]:
    if actual is None:
        return None
    if isinstance(actual, (list, set, tuple)):
        return list(actual)
    if isinstance(actual, dict):
        for key in ("roles", "rol", "role", "roles_activos"):
            if key in actual:
                val = actual[key]
                return [val] if isinstance(val, str) else list(val)
        return None
    for attr in ("roles", "rol", "role", "roles_activos"):
        if hasattr(actual, attr):
            val = getattr(actual, attr)
            if isinstance(val, str):
                return [val]
            try:
                return list(val)
            except TypeError:
                return [val]
    return None


def _es_personal(actual: Any) -> bool:
    roles = _roles_de(actual)
    if not roles:
        return False
    normalizados = {str(r).upper() for r in roles}
    return bool(normalizados & {"VENDEDOR", "ADMIN"})


async def listar(uow: VentasUnitOfWork, page: int = 1, size: int = 20) -> Pagina[Venta]:
    async with uow:
        pagina = await uow.ventas.listar(page, size)
    return pagina


async def obtener(
    uow: VentasUnitOfWork, venta_id: int, actual: Any = None
) -> Venta:
    async with uow:
        venta = await uow.ventas.get_by_id(venta_id)
        if venta is None:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        es_personal = _es_personal(actual)
        es_dueno = False
        if not es_personal:
            uid = _usuario_id(actual)
            if uid is not None:
                cliente = await uow.clientes.get_by_usuario_id(uid)
                if cliente is not None and cliente.id == venta.cliente_id:
                    es_dueno = True
        # Mientras no esté cableada la autenticación (C-13), `actual is None`
        # no bloquea la lectura; la decisión real de 403 aplica cuando se
        # recibe un usuario concreto que no es personal ni dueño.
        if actual is not None and not (es_personal or es_dueno):
            raise HTTPException(status_code=403, detail="No autorizado")
    return venta


async def mis_ventas(
    uow: VentasUnitOfWork, usuario: Any = None, page: int = 1, size: int = 20
) -> Pagina[Venta]:
    uid = _usuario_id(usuario)
    async with uow:
        cliente = None
        if uid is not None:
            cliente = await uow.clientes.get_by_usuario_id(uid)
        if cliente is None:
            if page < 1:
                raise HTTPException(status_code=422, detail=f"La página {page} no existe: hay 1")
            if page > 1:
                raise HTTPException(status_code=422, detail=f"La página {page} no existe: hay 1")
            return Pagina(items=[], total=0, page=page, size=size, pages=1)
        pagina = await uow.ventas.ventas_de_cliente(cliente.id, page, size)
    return pagina