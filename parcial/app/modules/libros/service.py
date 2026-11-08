"""Logica de negocio del modulo libros (seis capas, C-08).

Contrato de errores (CV-08): el orden es **404 → 409 → 422**. `obtener`,
`actualizar`, `dar_de_baja`, `reponer` y `movimientos` empiezan por el 404 del
libro; luego 409 por ISBN duplicado, libro dado de baja o falta de actor que
firme el movimiento; por último 422 en la cantidad. `crear` no tiene 404: sus
409 son el ISBN duplicado y la falta de actor.
"""

from decimal import Decimal
from typing import Any, List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.errors import traducir_integrity_error
from app.core.paginacion import Pagina, paginar
from app.modules.libros.models import Libro
from app.modules.libros.models import MovimientoStock
from app.modules.libros.schemas import (
    EditorialRef,
    GeneroRef,
    LibroAutorRead,
    LibroCreate,
    LibroDetailRead,
    LibroRead,
    LibroUpdate,
    MovimientoStockRead,
)
from app.modules.libros.unit_of_work import LibrosUnitOfWork


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


async def crear(
    uow: LibrosUnitOfWork, data: LibroCreate, usuario_actual: Any = None
) -> Libro:
    libro = Libro(
        isbn=data.isbn,
        titulo=data.titulo,
        precio=data.precio,
        stock=0,
        editorial_id=data.editorial_id,
        genero_id=data.genero_id,
    )
    usuario_id = _usuario_id(usuario_actual)
    try:
        async with uow:
            await uow.libros.add(libro)
            for a in data.autores:
                await uow.libros.add_autoria(
                    libro.id, a.autor_id, a.rol, a.orden
                )
            if data.stock_inicial and data.stock_inicial != 0:
                if usuario_id is None:
                    raise HTTPException(
                        status_code=409,
                        detail="No hay usuario autenticado que firme el movimiento",
                    )
                await uow.libros.aplicar_movimiento(
                    libro, data.stock_inicial, "Stock inicial", usuario_id
                )
    except IntegrityError as exc:
        raise traducir_integrity_error(exc)
    return libro


async def obtener(uow: LibrosUnitOfWork, libro_id: int) -> Libro:
    async with uow:
        obj = await uow.libros.get_by_id(libro_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return obj


async def listar(
    uow: LibrosUnitOfWork,
    page: int = 1,
    size: int = 20,
    titulo: Optional[str] = None,
    genero_id: Optional[int] = None,
) -> Pagina[Libro]:
    async with uow:
        stmt = uow.libros.listado_stmt(titulo, genero_id)
        pagina = await paginar(uow.session, stmt, page, size)
    return pagina


async def actualizar(
    uow: LibrosUnitOfWork, libro_id: int, data: LibroUpdate
) -> Libro:
    async with uow:
        obj = await uow.libros.get_by_id(libro_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        try:
            await uow.libros.update(obj)
        except IntegrityError as exc:
            raise traducir_integrity_error(exc)
    return obj


async def dar_de_baja(uow: LibrosUnitOfWork, libro_id: int) -> None:
    async with uow:
        obj = await uow.libros.get_by_id(libro_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        await uow.libros.soft_delete(obj)


async def reponer(
    uow: LibrosUnitOfWork,
    libro_id: int,
    cantidad: int,
    usuario_actual: Any = None,
) -> Libro:
    if cantidad is None or cantidad <= 0:
        raise HTTPException(status_code=422, detail="La cantidad debe ser mayor que cero")
    usuario_id = _usuario_id(usuario_actual)
    async with uow:
        obj = await uow.libros.get_by_id_including_deleted(libro_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        if getattr(obj, "borrado_en", None) is not None:
            raise HTTPException(status_code=409, detail="El libro está dado de baja")
        if usuario_id is None:
            raise HTTPException(
                status_code=409,
                detail="No hay usuario autenticado que firme el movimiento",
            )
        await uow.libros.aplicar_movimiento(obj, cantidad, "Reposición", usuario_id)
    return await obtener(uow, libro_id)


async def movimientos(
    uow: LibrosUnitOfWork, libro_id: int
) -> List[MovimientoStockRead]:
    async with uow:
        obj = await uow.libros.get_by_id(libro_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        items = await uow.libros.movimientos(libro_id)
    return [to_movimiento_read(m) for m in items]


def to_movimiento_read(movimiento: MovimientoStock) -> MovimientoStockRead:
    return MovimientoStockRead(
        id=movimiento.id,
        libro_id=movimiento.libro_id,
        venta_id=movimiento.venta_id,
        usuario_id=movimiento.usuario_id,
        cantidad=movimiento.cantidad,
        motivo=movimiento.motivo,
        cuando=movimiento.cuando,
    )


async def to_detail_read(libro: Libro) -> LibroDetailRead:
    autores = []
    for a in getattr(libro, "autorias", []) or []:
        autores.append(
            LibroAutorRead(
                autor_id=a.autor_id,
                rol=a.rol,
                orden=a.orden,
                autor_nombre=a.autor.nombre if getattr(a, "autor", None) is not None else None,
            )
        )
    editorial = None
    if getattr(libro, "editorial", None) is not None:
        editorial = EditorialRef(
            id=libro.editorial.id,
            nombre=libro.editorial.nombre,
            pais=libro.editorial.pais,
        )
    genero = None
    if getattr(libro, "genero", None) is not None:
        genero = GeneroRef(id=libro.genero.id, nombre=libro.genero.nombre)
    return LibroDetailRead(
        id=libro.id,
        isbn=libro.isbn,
        titulo=libro.titulo,
        precio=libro.precio,
        stock=libro.stock,
        editorial_id=libro.editorial_id,
        genero_id=libro.genero_id,
        editorial=editorial,
        genero=genero,
        autores=autores,
    )


async def to_read(libro: Libro) -> LibroRead:
    editorial = None
    if getattr(libro, "editorial", None) is not None:
        editorial = EditorialRef(
            id=libro.editorial.id,
            nombre=libro.editorial.nombre,
            pais=libro.editorial.pais,
        )
    genero = None
    if getattr(libro, "genero", None) is not None:
        genero = GeneroRef(id=libro.genero.id, nombre=libro.genero.nombre)
    return LibroRead(
        id=libro.id,
        isbn=libro.isbn,
        titulo=libro.titulo,
        precio=libro.precio,
        stock=libro.stock,
        editorial_id=libro.editorial_id,
        genero_id=libro.genero_id,
        editorial=editorial,
        genero=genero,
    )