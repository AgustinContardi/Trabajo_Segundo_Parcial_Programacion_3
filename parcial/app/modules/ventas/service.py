"""Lógica de negocio del módulo `ventas` (seis capas, C-10).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una
sesión asincrónica ni construye el UoW (CV-01). Orden de errores (CV-08):
401 → 403 → 409 → 422; el `404` pertenece a las lecturas de detalle.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.dependencies import IdentidadActual
from app.core.errors import (
    es_error_de_datos,
    traducir_error_de_datos,
    traducir_integrity_error,
)
from app.core.paginacion import Pagina
from app.modules.clientes.models import Cliente
from app.modules.libros.models import Libro
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.schemas import VentaCreate
from app.modules.ventas.unit_of_work import VentasUnitOfWork

logger = logging.getLogger("libreria.avisos")


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


async def registrar_venta(
    uow: VentasUnitOfWork, dto: VentaCreate, actual: IdentidadActual
) -> Venta:
    """Registra una venta atómicamente (RN-10).

    Un solo `async with uow` con el orden de errores 401 → 403 → 409 → 422
    (`CV-08`): cliente → libros existentes → libros vigentes → stock agregado
    por libro → renglón repetido → escritura. El `except` vive **fuera** del
    bloque para que `__aexit__` revierta las escrituras parciales antes de
    traducir el error (CV-02).
    """
    ids = [renglon.libro_id for renglon in dto.renglones]
    # Los ids repetidos se colapsan sólo para consultar y sumar stock; la
    # detección del duplicado ocurre después de los 409 (CV-08).
    ids_unicos = list(dict.fromkeys(ids))

    try:
        async with uow:
            # 1. Cliente existente.
            cliente = await uow.clientes.get_by_id(dto.cliente_id)
            if cliente is None:
                raise HTTPException(
                    status_code=409, detail="El cliente indicado no existe"
                )

            # 2. Libros existentes (todos los ids solicitados).
            libros = await uow.libros.get_by_ids(ids_unicos)
            por_id = {libro.id: libro for libro in libros}
            if len(por_id) != len(ids_unicos):
                raise HTTPException(
                    status_code=409,
                    detail="Uno o más libros indicados no existen",
                )

            # 3. Libros vigentes (no dados de baja).
            for libro in libros:
                if libro.borrado_en is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"El libro '{libro.titulo}' está dado de baja",
                    )

            # 4. Stock suficiente con cantidades agregadas por libro: un
            # duplicado no puede pasar dos chequeos individuales que en
            # conjunto exceden el stock.
            cantidades: dict[int, int] = {}
            for renglon in dto.renglones:
                cantidades[renglon.libro_id] = (
                    cantidades.get(renglon.libro_id, 0) + renglon.cantidad
                )
            for libro_id, cantidad in cantidades.items():
                libro = por_id[libro_id]
                if libro.stock < cantidad:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Stock insuficiente para '{libro.titulo}'",
                    )

            # 5. Recién ahora el contrato de renglones: libro repetido → 422.
            if len(set(ids)) != len(ids):
                raise HTTPException(
                    status_code=422,
                    detail="No se puede incluir el mismo libro dos veces en una venta",
                )

            # 6. Venta: total calculado por el servidor.
            total = sum(
                renglon.cantidad * por_id[renglon.libro_id].precio
                for renglon in dto.renglones
            )
            venta = await uow.ventas.add(
                Venta(
                    cliente_id=dto.cliente_id,
                    total=total,
                    fecha=datetime.now(timezone.utc),
                )
            )

            # 7. Renglones: precio_unitario copiado del libro.
            for renglon in dto.renglones:
                libro = por_id[renglon.libro_id]
                await uow.renglones.add(
                    RenglonVenta(
                        venta_id=venta.id,
                        libro_id=renglon.libro_id,
                        cantidad=renglon.cantidad,
                        precio_unitario=libro.precio,
                    )
                )

            # 8. Descuento de stock + movimiento por renglón (punto único C-08).
            for renglon in dto.renglones:
                libro = por_id[renglon.libro_id]
                await uow.libros.aplicar_movimiento(
                    libro,
                    -renglon.cantidad,
                    "Venta",
                    actual.usuario.id,
                    venta_id=venta.id,
                )

            # Venta ya cargada con cliente y renglones para el detalle de respuesta.
            venta = await uow.ventas.get_by_id(venta.id)
            return venta
    except IntegrityError as exc:
        # `IntegrityError` es subclase de `DBAPIError`: se evalúa primero para
        # conservar la traducción específica de FK/CHECK a 409/422.
        raise traducir_integrity_error(exc) from exc
    except DBAPIError as exc:
        # Sólo los errores de datos se traducen a 422; el resto se re-lanza
        # para que el handler global responda 500 sin texto interno (RN-15).
        if es_error_de_datos(exc):
            raise traducir_error_de_datos(exc) from exc
        raise


async def avisar_comprobante(venta_id: int) -> None:
    """Aviso de fondo tras el commit: duerme 0.5 s y deja un log visible."""
    await asyncio.sleep(0.5)
    logger.warning("Comprobante de la venta %s enviado al cliente", venta_id)