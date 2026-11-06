from fastapi import APIRouter, Depends, Query

from app.core.dependencies import IdentidadActual, requiere_rol
from app.core.paginacion import Pagina
from app.modules.generos import service
from app.modules.generos.schemas import GeneroCreate, GeneroRead
from app.modules.generos.unit_of_work import GenerosUnitOfWork, get_generos_uow
from app.modules.libros import service as libros_service
from app.modules.libros.schemas import LibroRead

router = APIRouter(prefix="/generos", tags=["generos"])

_solo_admin = requiere_rol("ADMIN")


@router.post("/", response_model=GeneroRead, status_code=201)
async def crear_genero(
    data: GeneroCreate,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: GenerosUnitOfWork = Depends(get_generos_uow),
):
    return await service.crear(uow, data)


@router.get("/", response_model=Pagina[GeneroRead])
async def listar_generos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    uow: GenerosUnitOfWork = Depends(get_generos_uow),
):
    return await service.listar(uow, page, size)


@router.get("/{genero_id}/libros", response_model=list[LibroRead])
async def libros_de_genero(
    genero_id: int, uow: GenerosUnitOfWork = Depends(get_generos_uow)
):
    libros = await service.libros_de(uow, genero_id)
    return [await libros_service.to_read(l) for l in libros]