"""Acceso a la base: motor, fábrica de sesiones y sesión por petición.

Contrato de este módulo:

- **Nada se crea al importar.** El motor y la fábrica nacen en el `lifespan` de
  `main.py` y se guardan en `app.state`; un recurso creado al importar nace
  antes de que exista el bucle de eventos.
- `get_session` toma la fábrica de `app.state`, entrega **una sesión por
  petición** y la cierra en `finally` (también si la petición falla).
- El esquema **no** se crea desde acá: sólo Alembic (`CV-14`). La aplicación
  nunca crea ni modifica tablas al arrancar.
- Los repositorios harán `flush()`, nunca `commit()` (`CV-02`); el `commit` es
  del `__aexit__` del Unit of Work (`CV-01`).
- Toda precarga (`selectinload`) vive en `repository.py` (`CV-03`).
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def crear_engine(settings: Settings) -> AsyncEngine:
    """Crea el motor asincrónico con el pool y el eco configurados."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.POOL_SIZE,
        echo=settings.SQL_ECHO,
    )


def crear_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Crea la fábrica de sesiones.

    `expire_on_commit=False` es obligatorio: el servicio debe poder leer los
    atributos de los objetos ya cargados después del `commit` del UoW, sin
    reabrir una transacción.
    """
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Entrega una sesión por petición y la cierra al terminar."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    session = factory()
    try:
        yield session
    finally:
        await session.close()
