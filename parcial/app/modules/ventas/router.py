from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.paginacion import Pagina
from app.modules.ventas import service
from app.modules.ventas.schemas import (
    ClienteRef,
    RenglonRead,
    VentaCreate,
    VentaDetailRead,
    VentaRead,
)

router = APIRouter(prefix="/ventas", tags=["ventas"])


@router.post("/", response_model=VentaDetailRead, status_code=201)
async def crear_venta(
    data: VentaCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    venta = await service.crear(session, data.cliente_id, data.renglones)
    await session.commit()
    venta = await service.obtener(session, venta.id)
    background_tasks.add_task(service.aviso_comprobante, venta.id)
    # build response
    cliente = venta.cliente
    renglones = []
    for r in venta.renglones:
        renglones.append(
            RenglonRead(
                id=r.id,
                venta_id=r.venta_id,
                libro_id=r.libro_id,
                cantidad=r.cantidad,
                precio_unitario=r.precio_unitario,
                titulo=r.libro.titulo if r.libro is not None else None,
                subtotal=r.precio_unitario * r.cantidad,
            )
        )
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


@router.get("/", response_model=Pagina[VentaRead])
async def listar_ventas(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    pagina = await service.listar(session, page, size)
    result = []
    for v in pagina.items:
        result.append(
            VentaRead(
                id=v.id,
                cliente_id=v.cliente_id,
                fecha=v.fecha,
                total=v.total,
                cliente=(
                    ClienteRef(id=v.cliente.id, nombre=v.cliente.nombre, email=v.cliente.email)
                    if v.cliente is not None
                    else None
                ),
            )
        )
    return Pagina(items=result, total=pagina.total, page=pagina.page, size=pagina.size, pages=pagina.pages)


@router.get("/{venta_id}", response_model=VentaDetailRead)
async def obtener_venta(venta_id: int, session: AsyncSession = Depends(get_session)):
    venta = await service.obtener(session, venta_id)
    cliente = venta.cliente
    renglones = []
    for r in venta.renglones:
        renglones.append(
            RenglonRead(
                id=r.id,
                venta_id=r.venta_id,
                libro_id=r.libro_id,
                cantidad=r.cantidad,
                precio_unitario=r.precio_unitario,
                titulo=r.libro.titulo if r.libro is not None else None,
                subtotal=r.precio_unitario * r.cantidad,
            )
        )
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