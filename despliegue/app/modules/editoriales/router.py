from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.editoriales import service
from app.modules.editoriales.schemas import EditorialCreate, EditorialRead, EditorialUpdate
from app.modules.libros.schemas import LibroRead
from app.modules.libros import service as libros_service

router = APIRouter(prefix="/editoriales", tags=["editoriales"])


@router.post("/", response_model=EditorialRead, status_code=201)
async def crear_editorial(data: EditorialCreate, session: AsyncSession = Depends(get_session)):
    obj = await service.crear(session, data)
    await session.commit()
    return obj


@router.get("/", response_model=list[EditorialRead])
async def listar_editoriales(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    items = await service.listar(session, limit, offset)
    return items


@router.get("/{editorial_id}", response_model=EditorialRead)
async def obtener_editorial(editorial_id: int, session: AsyncSession = Depends(get_session)):
    return await service.obtener(session, editorial_id)


@router.patch("/{editorial_id}", response_model=EditorialRead)
async def actualizar_editorial(
    editorial_id: int, data: EditorialUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await service.actualizar(session, editorial_id, data)
    await session.commit()
    return obj


@router.get("/{editorial_id}/libros", response_model=list[LibroRead])
async def libros_de_editorial(editorial_id: int, session: AsyncSession = Depends(get_session)):
    libros = await service.libros_de(session, editorial_id)
    return [await libros_service.to_read(l) for l in libros]