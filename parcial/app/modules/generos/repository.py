"""Repositorio del módulo `generos`."""

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.repository import BaseRepository
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro


class GeneroRepository(BaseRepository[Genero]):
    def __init__(self, session) -> None:
        super().__init__(session, Genero)

    async def libros_de(self, genero_id: int) -> List[Libro]:
        stmt = (
            select(Libro)
            .where(Libro.genero_id == genero_id, Libro.borrado_en.is_(None))
            .options(joinedload(Libro.editorial), joinedload(Libro.genero))
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())