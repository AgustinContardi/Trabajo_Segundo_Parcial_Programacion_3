from fastapi import APIRouter, Depends, Query

from app.core.paginacion import Pagina
from app.modules.editoriales import service
from app.modules.editoriales.schemas import EditorialCreate, EditorialRead, EditorialUpdate
from app.modules.editoriales.unit_of_work import EditorialesUnitOfWork, get_editoriales_uow
from app.modules.libros import service as libros_service
from app.modules.libros.schemas import LibroRead

router = APIRouter(prefix="/editoriales", tags=["editoriales"])


@router.post("/", response_model=EditorialRead, status_code=201)
async def crear_editorial(
    data: EditorialCreate, uow: EditorialesUnitOfWork = Depends(get_editoriales_uow)
):
    return await service.crear(uow, data)


@router.get("/", response_model=Pagina[EditorialRead])
async def listar_editoriales(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    uow: EditorialesUnitOfWork = Depends(get_editoriales_uow),
):
    return await service.listar(uow, page, size)


@router.get("/{editorial_id}", response_model=EditorialRead)
async def obtener_editorial(
    editorial_id: int, uow: EditorialesUnitOfWork = Depends(get_editoriales_uow)
):
    return await service.obtener(uow, editorial_id)


@router.patch("/{editorial_id}", response_model=EditorialRead)
async def actualizar_editorial(
    editorial_id: int,
    data: EditorialUpdate,
    uow: EditorialesUnitOfWork = Depends(get_editoriales_uow),
):
    return await service.actualizar(uow, editorial_id, data)


@router.get("/{editorial_id}/libros", response_model=list[LibroRead])
async def libros_de_editorial(
    editorial_id: int, uow: EditorialesUnitOfWork = Depends(get_editoriales_uow)
):
    libros = await service.libros_de(uow, editorial_id)
    return [await libros_service.to_read(l) for l in libros]