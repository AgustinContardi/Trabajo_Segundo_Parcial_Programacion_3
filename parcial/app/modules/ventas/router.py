from fastapi import APIRouter, Depends, Query

from app.core.paginacion import Pagina
from app.modules.ventas import service
from app.modules.ventas.schemas import (
    ClienteRef,
    RenglonRead,
    VentaDetailRead,
    VentaRead,
)
from app.modules.ventas.unit_of_work import VentasUnitOfWork, get_ventas_uow

router = APIRouter(prefix="/ventas", tags=["ventas"])


def _to_venta_read(v) -> VentaRead:
    cliente = v.cliente
    return VentaRead(
        id=v.id,
        cliente_id=v.cliente_id,
        fecha=v.fecha,
        total=v.total,
        cliente=(
            ClienteRef(id=cliente.id, nombre=cliente.nombre, email=cliente.email)
            if cliente is not None
            else None
        ),
    )


def _to_detail(venta) -> VentaDetailRead:
    cliente = venta.cliente
    renglones = [
        RenglonRead(
            id=r.id,
            venta_id=r.venta_id,
            libro_id=r.libro_id,
            cantidad=r.cantidad,
            precio_unitario=r.precio_unitario,
            titulo=r.libro.titulo if getattr(r, "libro", None) is not None else None,
            subtotal=r.precio_unitario * r.cantidad,
        )
        for r in getattr(venta, "renglones", []) or []
    ]
    return VentaDetailRead(
        id=venta.id,
        cliente_id=venta.cliente_id,
        fecha=venta.fecha,
        total=venta.total,
        cliente=(
            ClienteRef(id=cliente.id, nombre=cliente.nombre, email=cliente.email)
            if cliente is not None
            else None
        ),
        renglones=renglones,
    )


@router.get("/mis-ventas", response_model=Pagina[VentaRead])
async def mis_ventas(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
):
    pagina = await service.mis_ventas(uow, None, page, size)
    items = [_to_venta_read(v) for v in pagina.items]
    return Pagina(
        items=items,
        total=pagina.total,
        page=pagina.page,
        size=pagina.size,
        pages=pagina.pages,
    )


@router.get("/", response_model=Pagina[VentaRead])
async def listar_ventas(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
):
    pagina = await service.listar(uow, page, size)
    items = [_to_venta_read(v) for v in pagina.items]
    return Pagina(
        items=items,
        total=pagina.total,
        page=pagina.page,
        size=pagina.size,
        pages=pagina.pages,
    )


@router.get("/{venta_id}", response_model=VentaDetailRead)
async def obtener_venta(
    venta_id: int, uow: VentasUnitOfWork = Depends(get_ventas_uow)
):
    venta = await service.obtener(uow, venta_id)
    return _to_detail(venta)