"""Repositorio del módulo `editoriales`.

Toda precarga (`selectinload`/`joinedload`) vive acá (CV-02); ni el servicio ni
el router precargan. Sólo `flush()` a través de `BaseRepository`.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.repository import BaseRepository
from app.modules.editoriales.models import Editorial
from app.modules.libros.models import Libro


class EditorialRepository(BaseRepository[Editorial]):
    def __init__(self, session) -> None:
        super().__init__(session, Editorial)

    async def libros_de(self, editorial_id: int) -> List[Libro]:
        """Libros vigentes de la editorial (excluye dados de baja)."""
        stmt = (
            select(Libro)
            .where(Libro.editorial_id == editorial_id, Libro.borrado_en.is_(None))
            .options(joinedload(Libro.editorial), joinedload(Libro.genero))
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())