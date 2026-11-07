from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.repository import SoftDeleteRepository
from app.modules.libros.models import Libro, LibroAutor, MovimientoStock


class LibroRepository(SoftDeleteRepository[Libro]):
    def __init__(self, session: Any) -> None:
        super().__init__(session, Libro)

    async def get_by_id(self, id: Any) -> Libro | None:
        stmt = (
            select(Libro)
            .where(Libro.id == id, Libro.borrado_en.is_(None))
            .options(
                selectinload(Libro.editorial),
                selectinload(Libro.genero),
                selectinload(Libro.autorias).selectinload(LibroAutor.autor),
            )
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    def listado_stmt(
        self,
        titulo: Optional[str] = None,
        genero_id: Optional[int] = None,
    ):
        stmt = (
            select(Libro)
            .where(Libro.borrado_en.is_(None))
            .options(
                selectinload(Libro.editorial),
                selectinload(Libro.genero),
            )
        )
        if titulo:
            stmt = stmt.where(Libro.titulo.ilike(f"%{titulo}%"))
        if genero_id is not None:
            stmt = stmt.where(Libro.genero_id == genero_id)
        return stmt

    async def buscar_por_titulo(self, titulo: str) -> List[Libro]:
        stmt = (
            select(Libro)
            .where(Libro.borrado_en.is_(None), Libro.titulo.ilike(f"%{titulo}%"))
            .options(
                selectinload(Libro.editorial),
                selectinload(Libro.genero),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_ids(self, ids: list[int]) -> list[Libro]:
        """Obtiene varios libros de un golpe para evitar N consultas.

        No filtra por `borrado_en`: el servicio decide si un libro dado de baja
        es aceptable o no. Devuelve sólo los libros que existen (los ids
        repetidos se colapsan porque la consulta es por `IN`).
        """
        if not ids:
            return []
        stmt = select(Libro).where(Libro.id.in_(ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_autoria(
        self, libro_id: int, autor_id: int, rol: str, orden: int
    ) -> LibroAutor:
        autoria = LibroAutor(libro_id=libro_id, autor_id=autor_id, rol=rol, orden=orden)
        self._session.add(autoria)
        await self._session.flush()
        return autoria

    async def aplicar_movimiento(
        self,
        libro: Libro,
        cantidad: int,
        motivo: str,
        usuario_id: int,
        venta_id: Optional[int] = None,
    ) -> MovimientoStock:
        libro.stock += cantidad
        movimiento = MovimientoStock(
            libro_id=libro.id,
            venta_id=venta_id,
            usuario_id=usuario_id,
            cantidad=cantidad,
            motivo=motivo,
        )
        self._session.add(movimiento)
        await self._session.flush()
        return movimiento

    async def movimientos(self, libro_id: int) -> List[MovimientoStock]:
        stmt = (
            select(MovimientoStock)
            .where(MovimientoStock.libro_id == libro_id)
            .order_by(MovimientoStock.cuando, MovimientoStock.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())