from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.core.dependencies import (
    IdentidadActual,
    get_sesion_actual,
    requiere_rol,
)
from app.core.paginacion import Pagina
from app.modules.ventas import service
from app.modules.ventas.schemas import (
    ClienteRef,
    RenglonRead,
    VentaCreate,
    VentaDetailRead,
    VentaRead,
)
from app.modules.ventas.unit_of_work import VentasUnitOfWork, get_ventas_uow

router = APIRouter(prefix="/ventas", tags=["ventas"])

# Sólo el listado completo es de personal; el detalle y «mis ventas» dependen
# de la propiedad que decide el servicio (RN-14).
_solo_personal = requiere_rol("VENDEDOR", "ADMIN")


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
    sesion: IdentidadActual = Depends(get_sesion_actual),
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
):
    pagina = await service.mis_ventas(uow, sesion, page, size)
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
    _sesion: IdentidadActual = Depends(_solo_personal),
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
    venta_id: int,
    sesion: IdentidadActual = Depends(get_sesion_actual),
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
):
    venta = await service.obtener(uow, venta_id, actual=sesion)
    return _to_detail(venta)


@router.post("", response_model=VentaDetailRead, status_code=201, include_in_schema=False)
@router.post("/", response_model=VentaDetailRead, status_code=201)
async def crear_venta(
    dto: VentaCreate,
    background_tasks: BackgroundTasks,
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
    actual: IdentidadActual = Depends(requiere_rol("VENDEDOR", "ADMIN")),
):
    """Registra una venta nueva de forma atómica.

    El router sólo construye el UoW (vía dependencia), delega la autorización
    a `requiere_rol` y la escritura al servicio. No hay lógica de negocio aquí
    ni se abre ninguna transacción (CV-01, CV-05). Tras el commit se agenda
    el aviso del comprobante como tarea de fondo.
    """
    venta = await service.registrar_venta(uow, dto, actual)
    background_tasks.add_task(service.avisar_comprobante, venta.id)
    return _to_detail(venta)
