from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.autores import service
from app.modules.autores.schemas import AutorCreate, AutorRead, AutorUpdate

router = APIRouter(prefix="/autores", tags=["autores"])


@router.post("/", response_model=AutorRead, status_code=201)
async def crear_autor(data: AutorCreate, session: AsyncSession = Depends(get_session)):
    obj = await service.crear(session, data)
    await session.commit()
    return obj


@router.get("/{autor_id}", response_model=AutorRead)
async def obtener_autor(autor_id: int, session: AsyncSession = Depends(get_session)):
    return await service.obtener(session, autor_id)


@router.patch("/{autor_id}", response_model=AutorRead)
async def actualizar_autor(
    autor_id: int, data: AutorUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await service.actualizar(session, autor_id, data)
    await session.commit()
    return obj


@router.get("/{autor_id}/libros")
async def libros_de_autor(autor_id: int, session: AsyncSession = Depends(get_session)):
    rows = await service.libros_de(session, autor_id)
    return [{"libro_id": r[0].id, "titulo": r[0].titulo, "rol": r[1], "orden": r[2]} for r in rows]