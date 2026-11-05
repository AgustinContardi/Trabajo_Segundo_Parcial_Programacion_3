from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.generos import service
from app.modules.generos.schemas import GeneroCreate, GeneroRead
from app.modules.libros.schemas import LibroRead
from app.modules.libros import service as libros_service

router = APIRouter(prefix="/generos", tags=["generos"])


@router.post("/", response_model=GeneroRead, status_code=201)
async def crear_genero(data: GeneroCreate, session: AsyncSession = Depends(get_session)):
    obj = await service.crear(session, data)
    await session.commit()
    return obj


@router.get("/", response_model=list[GeneroRead])
async def listar_generos(session: AsyncSession = Depends(get_session)):
    return await service.listar(session)


@router.get("/{genero_id}/libros", response_model=list[LibroRead])
async def libros_de_genero(genero_id: int, session: AsyncSession = Depends(get_session)):
    libros = await service.libros_de(session, genero_id)
    return [await libros_service.to_read(l) for l in libros]