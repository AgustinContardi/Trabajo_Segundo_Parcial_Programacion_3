from fastapi import APIRouter, Depends, Query

from app.core.dependencies import IdentidadActual, requiere_rol
from app.core.paginacion import Pagina
from app.modules.autores import service
from app.modules.autores.schemas import AutorCreate, AutorRead, AutorUpdate
from app.modules.autores.unit_of_work import AutoresUnitOfWork, get_autores_uow
from app.modules.libros import service as libros_service
from app.modules.libros.schemas import LibroRead

router = APIRouter(prefix="/autores", tags=["autores"])

_solo_admin = requiere_rol("ADMIN")


@router.post("/", response_model=AutorRead, status_code=201)
async def crear_autor(
    data: AutorCreate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AutoresUnitOfWork = Depends(get_autores_uow),
):
    return await service.crear(uow, data)


@router.get("/", response_model=Pagina[AutorRead])
async def listar_autores(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    uow: AutoresUnitOfWork = Depends(get_autores_uow),
):
    return await service.listar(uow, page, size)


@router.get("/{autor_id}", response_model=AutorRead)
async def obtener_autor(
    autor_id: int, uow: AutoresUnitOfWork = Depends(get_autores_uow)
):
    return await service.obtener(uow, autor_id)


@router.patch("/{autor_id}", response_model=AutorRead)
async def actualizar_autor(
    autor_id: int,
    data: AutorUpdate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AutoresUnitOfWork = Depends(get_autores_uow),
):
    return await service.actualizar(uow, autor_id, data)


@router.get("/{autor_id}/libros", response_model=list[LibroRead])
async def libros_de_autor(
    autor_id: int, uow: AutoresUnitOfWork = Depends(get_autores_uow)
):
    libros = await service.libros_de(uow, autor_id)
    return [await libros_service.to_read(l) for l in libros]