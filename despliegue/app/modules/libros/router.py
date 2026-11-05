from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.libros import service
from app.modules.libros.schemas import LibroCreate, LibroDetailRead, LibroRead, LibroUpdate

router = APIRouter(prefix="/libros", tags=["libros"])


@router.post("/", response_model=LibroDetailRead, status_code=201)
async def crear_libro(data: LibroCreate, session: AsyncSession = Depends(get_session)):
    libro = await service.crear(session, data)
    await session.commit()
    libro = await service.obtener(session, libro.id)
    return await service.to_detail_read(libro)


@router.get("/", response_model=list[LibroRead])
async def listar_libros(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    titulo: Optional[str] = Query(None),
    genero_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    libros = await service.listar(session, limit, offset, titulo, genero_id)
    return [await service.to_read(l) for l in libros]


@router.get("/{libro_id}", response_model=LibroDetailRead)
async def obtener_libro(libro_id: int, session: AsyncSession = Depends(get_session)):
    libro = await service.obtener(session, libro_id)
    return await service.to_detail_read(libro)


@router.patch("/{libro_id}", response_model=LibroDetailRead)
async def actualizar_libro(
    libro_id: int, data: LibroUpdate, session: AsyncSession = Depends(get_session)
):
    libro = await service.actualizar(session, libro_id, data)
    await session.commit()
    libro = await service.obtener(session, libro.id)
    return await service.to_detail_read(libro)