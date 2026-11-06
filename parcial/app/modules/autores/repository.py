"""Repositorio del módulo `autores`."""

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.repository import BaseRepository
from app.modules.autores.models import Autor
from app.modules.libros.models import Libro, LibroAutor


class AutorRepository(BaseRepository[Autor]):
    def __init__(self, session) -> None:
        super().__init__(session, Autor)

    async def libros_de(self, autor_id: int) -> List[Libro]:
        stmt = (
            select(Libro)
            .join(LibroAutor, LibroAutor.libro_id == Libro.id)
            .where(LibroAutor.autor_id == autor_id, Libro.borrado_en.is_(None))
            .options(joinedload(Libro.editorial), joinedload(Libro.genero))
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())