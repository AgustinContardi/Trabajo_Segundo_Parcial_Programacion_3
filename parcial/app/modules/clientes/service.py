"""Lógica de negocio del módulo `clientes` (seis capas, C-07).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una
sesión asincrónica ni construye el UoW (CV-01). Orden de errores (CV-08):
404 → 403 → 409 → 422.
"""

from typing import Any, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.errors import traducir_integrity_error
from app.core.paginacion import Pagina
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.clientes.schemas import ClienteCreate, ClienteUpdate, PerfilCreate
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from app.modules.ventas.models import Venta


def _roles_de(actual: Any) -> Optional[list[Any]]:
    """Extrae la lista de roles de `actual` soportando varias formas."""
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


def _es_cliente_solo(actual: Any) -> bool:
    """True si `actual` tiene únicamente el rol CLIENTE."""
    roles = _roles_de(actual)
    if not roles:
        return False
    normalizados = {str(r).upper() for r in roles}
    return normalizados == {"CLIENTE"}


async def crear(uow: ClientesUnitOfWork, data: ClienteCreate) -> Cliente:
    obj = Cliente(nombre=data.nombre, email=data.email, usuario_id=None)
    try:
        async with uow:
            await uow.clientes.add(obj)
    except IntegrityError as exc:
        raise traducir_integrity_error(exc)
    return obj


async def obtener(uow: ClientesUnitOfWork, cliente_id: int) -> Cliente:
    async with uow:
        obj = await uow.clientes.get_by_id(cliente_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return obj


async def actualizar(
    uow: ClientesUnitOfWork, cliente_id: int, data: ClienteUpdate
) -> Cliente:
    async with uow:
        obj = await uow.clientes.get_by_id(cliente_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        try:
            await uow.clientes.update(obj)
        except IntegrityError as exc:
            raise traducir_integrity_error(exc)
    return obj


async def crear_perfil(
    uow: ClientesUnitOfWork, cliente_id: int, data: PerfilCreate
) -> PerfilCliente:
    async with uow:
        cliente = await uow.clientes.get_by_id(cliente_id)
        if cliente is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        if cliente.perfil is not None:
            raise HTTPException(status_code=409, detail="El cliente ya tiene perfil")
        perfil = PerfilCliente(
            cliente_id=cliente_id, telefono=data.telefono, direccion=data.direccion
        )
        try:
            await uow.clientes.add_perfil(perfil)
        except IntegrityError as exc:
            raise traducir_integrity_error(exc)
    return perfil


async def ventas_de(
    uow: ClientesUnitOfWork,
    cliente_id: int,
    page: int = 1,
    size: int = 20,
    actual: Any = None,
) -> Tuple[Cliente, Pagina[Venta]]:
    async with uow:
        cliente = await uow.clientes.get_by_id(cliente_id)
        if cliente is None:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        # Punto de decisión de autorización (cableado completo en C-13).
        if _es_cliente_solo(actual):
            raise HTTPException(status_code=403, detail="No autorizado")
        pagina = await uow.clientes.ventas_de(cliente_id, page, size)
    return cliente, pagina
