from typing import Optional

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.paginacion import Pagina
from app.modules.libros import service
from app.modules.libros.schemas import LibroCreate, LibroDetailRead, LibroRead, LibroUpdate

router = APIRouter(prefix="/libros", tags=["libros"])


@router.post("/", response_model=LibroDetailRead, status_code=201)
async def crear_libro(data: LibroCreate, session: AsyncSession = Depends(get_session)):
    libro = await service.crear(session, data)
    await session.commit()
    libro = await service.obtener(session, libro.id)
    return await service.to_detail_read(libro)


@router.get("/", response_model=Pagina[LibroRead])
async def listar_libros(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    titulo: Optional[str] = Query(None),
    genero_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    pagina = await service.listar(session, page, size, titulo, genero_id)
    items = [await service.to_read(l) for l in pagina.items]
    return Pagina(items=items, total=pagina.total, page=pagina.page, size=pagina.size, pages=pagina.pages)


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