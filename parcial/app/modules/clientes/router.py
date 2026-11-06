from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import IdentidadActual, requiere_rol
from app.core.paginacion import Pagina
from app.modules.clientes import service
from app.modules.clientes.schemas import (
    ClienteCreate,
    ClienteDetailRead,
    ClienteRead,
    ClienteUpdate,
    PerfilCreate,
    PerfilRead,
)
from app.modules.clientes.unit_of_work import ClientesUnitOfWork, get_clientes_uow
from app.modules.ventas.schemas import ClienteRef, VentaRead

router = APIRouter(prefix="/clientes", tags=["clientes"])

# Toda ruta de clientes es de personal (matriz RBAC, C-13).
_solo_personal = requiere_rol("VENDEDOR", "ADMIN")


def _to_cliente_read(obj) -> ClienteRead:
    return ClienteRead(
        id=obj.id,
        nombre=obj.nombre,
        email=obj.email,
        usuario_id=obj.usuario_id,
    )


def _to_detail(obj) -> ClienteDetailRead:
    return ClienteDetailRead(
        id=obj.id,
        nombre=obj.nombre,
        email=obj.email,
        usuario_id=obj.usuario_id,
        perfil=(
            PerfilRead(
                id=obj.perfil.id,
                cliente_id=obj.perfil.cliente_id,
                telefono=obj.perfil.telefono,
                direccion=obj.perfil.direccion,
            )
            if getattr(obj, "perfil", None) is not None
            else None
        ),
    )


@router.post("/", response_model=ClienteRead, status_code=201)
async def crear_cliente(
    data: ClienteCreate,
    _sesion: IdentidadActual = Depends(_solo_personal),
    uow: ClientesUnitOfWork = Depends(get_clientes_uow),
):
    obj = await service.crear(uow, data)
    return _to_cliente_read(obj)


@router.get("/{cliente_id}", response_model=ClienteDetailRead)
async def obtener_cliente(
    cliente_id: int,
    _sesion: IdentidadActual = Depends(_solo_personal),
    uow: ClientesUnitOfWork = Depends(get_clientes_uow),
):
    obj = await service.obtener(uow, cliente_id)
    return _to_detail(obj)


@router.patch("/{cliente_id}", response_model=ClienteDetailRead)
async def actualizar_cliente(
    cliente_id: int,
    data: ClienteUpdate,
    _sesion: IdentidadActual = Depends(_solo_personal),
    uow: ClientesUnitOfWork = Depends(get_clientes_uow),
):
    obj = await service.actualizar(uow, cliente_id, data)
    return _to_detail(obj)


@router.post("/{cliente_id}/perfil", response_model=PerfilRead, status_code=201)
async def crear_perfil(
    cliente_id: int,
    data: PerfilCreate,
    _sesion: IdentidadActual = Depends(_solo_personal),
    uow: ClientesUnitOfWork = Depends(get_clientes_uow),
):
    obj = await service.crear_perfil(uow, cliente_id, data)
    return PerfilRead(
        id=obj.id,
        cliente_id=obj.cliente_id,
        telefono=obj.telefono,
        direccion=obj.direccion,
    )


@router.get("/{cliente_id}/ventas", response_model=Pagina[VentaRead])
async def ventas_de_cliente(
    cliente_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sesion: IdentidadActual = Depends(_solo_personal),
    uow: ClientesUnitOfWork = Depends(get_clientes_uow),
):
    cliente, pagina = await service.ventas_de(
        uow, cliente_id, page, size, actual=sesion
    )
    items = [
        VentaRead(
            id=v.id,
            cliente_id=v.cliente_id,
            fecha=v.fecha,
            total=v.total,
            cliente=ClienteRef(
                id=cliente.id, nombre=cliente.nombre, email=cliente.email
            ),
        )
        for v in pagina.items
    ]
    return Pagina(
        items=items,
        total=pagina.total,
        page=pagina.page,
        size=pagina.size,
        pages=pagina.pages,
    )
