"""Repositorios genéricos y especializados para borrado lógico.

Contrato de este módulo (CV-01):
- Quién construye: el router (vía dependencia) instancia el Unit of Work, que
  a su vez instancia los repositorios con la sesión recibida.
- Quién abre: el servicio abre el Unit of Work con ``async with``.
- Quién confirma: sólo ``__aexit__`` del Unit of Work.
- Quién cierra: ``get_session`` (la sesión no la crea el repositorio).

Reglas (CV-02): ningún método invoca confirmación ni reversión sobre la
sesión; sólo ``flush()``. Toda precarga (``selectinload``) se declara adentro
del método que la necesita (CV-03); este módulo base no precarga nada.
"""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Repositorio genérico para una entidad.

    Los genéricos se borran en tiempo de ejecución; el modelo se pasa por
    constructor, lo que permite reutilizar la misma clase para todas las
    entidades sin duplicar código.
    """

    def __init__(self, session: AsyncSession, model_class: type[T]) -> None:
        self._session = session
        self._model_class = model_class

    async def get_by_id(self, id: Any) -> T | None:
        """Obtiene una entidad por su clave primaria, o ``None`` si no existe."""
        return await self._session.get(self._model_class, id)

    async def get_all(self) -> list[T]:
        """Devuelve todas las filas del modelo."""
        result = await self._session.execute(select(self._model_class))
        return list(result.scalars().all())

    async def count(self) -> int:
        """Cuenta las filas del modelo."""
        stmt = select(func.count()).select_from(self._model_class)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def add(self, entity: T) -> T:
        """Agrega una entidad nueva y hace ``flush()`` para obtener su id."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: T) -> T:
        """Actualiza una entidad existente y hace ``flush()``."""
        await self._session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        """Elimina una entidad y hace ``flush()``."""
        await self._session.delete(entity)
        await self._session.flush()


class SoftDeleteRepository(BaseRepository[T]):
    """Repositorio con borrado lógico.

    Asume que el modelo tiene la columna ``borrado_en`` (``timestamptz``,
    nulo = vigente). Sólo se usa para ``Libro``. Filtra los dados de baja en
    ``get_by_id``, ``get_all`` y ``count``; agrega ``get_by_id_including_deleted``
    y ``soft_delete``, que la clase base no declara.
    """

    async def get_by_id(self, id: Any) -> T | None:
        """Obtiene una entidad vigente por id (excluye dados de baja)."""
        stmt = select(self._model_class).where(
            self._model_class.id == id,
            self._model_class.borrado_en.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_all(self) -> list[T]:
        """Devuelve sólo las entidades vigentes (``borrado_en IS NULL``)."""
        stmt = select(self._model_class).where(
            self._model_class.borrado_en.is_(None)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Cuenta sólo las entidades vigentes."""
        stmt = (
            select(func.count())
            .select_from(self._model_class)
            .where(self._model_class.borrado_en.is_(None))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_id_including_deleted(self, id: Any) -> T | None:
        """Obtiene una entidad por id sin filtrar el borrado lógico."""
        return await self._session.get(self._model_class, id)

    async def soft_delete(self, entity: T) -> None:
        """Escribe ``borrado_en = now()`` en lugar de borrar la fila."""
        entity.borrado_en = datetime.now(timezone.utc)
        await self._session.flush()