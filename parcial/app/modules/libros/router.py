from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import IdentidadActual, requiere_rol
from app.core.paginacion import Pagina
from app.modules.libros import service
from app.modules.libros.schemas import (
    LibroCreate,
    LibroDetailRead,
    LibroRead,
    LibroUpdate,
    MovimientoStockRead,
    ReponerCreate,
)
from app.modules.libros.unit_of_work import LibrosUnitOfWork, get_libros_uow

router = APIRouter(prefix="/libros", tags=["libros"])

_solo_admin = requiere_rol("ADMIN")


@router.post("/", response_model=LibroDetailRead, status_code=201)
async def crear_libro(
    data: LibroCreate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    libro = await service.crear(uow, data)
    libro = await service.obtener(uow, libro.id)
    return await service.to_detail_read(libro)


@router.get("/", response_model=Pagina[LibroRead])
async def listar_libros(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    titulo: Optional[str] = Query(None),
    genero_id: Optional[int] = Query(None),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    pagina = await service.listar(uow, page, size, titulo, genero_id)
    items = [await service.to_read(l) for l in pagina.items]
    return Pagina(
        items=items,
        total=pagina.total,
        page=pagina.page,
        size=pagina.size,
        pages=pagina.pages,
    )


@router.get("/{libro_id}", response_model=LibroDetailRead)
async def obtener_libro(
    libro_id: int, uow: LibrosUnitOfWork = Depends(get_libros_uow)
):
    libro = await service.obtener(uow, libro_id)
    return await service.to_detail_read(libro)


@router.patch("/{libro_id}", response_model=LibroDetailRead)
async def actualizar_libro(
    libro_id: int,
    data: LibroUpdate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    libro = await service.actualizar(uow, libro_id, data)
    libro = await service.obtener(uow, libro.id)
    return await service.to_detail_read(libro)


@router.delete("/{libro_id}", status_code=204)
async def dar_de_baja_libro(
    libro_id: int,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    await service.dar_de_baja(uow, libro_id)
    return None


@router.post("/{libro_id}/reponer", response_model=LibroDetailRead)
async def reponer_libro(
    libro_id: int,
    data: ReponerCreate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    libro = await service.reponer(uow, libro_id, data.cantidad)
    libro = await service.obtener(uow, libro.id)
    return await service.to_detail_read(libro)


@router.get("/{libro_id}/movimientos", response_model=list[MovimientoStockRead])
async def movimientos_libro(
    libro_id: int,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: LibrosUnitOfWork = Depends(get_libros_uow),
):
    items = await service.movimientos(uow, libro_id)
    return items