"""Punto de entrada de la API — «la librería» (parcial capítulos 1 a 6).

Contrato de este módulo:

- `lifespan` es el **único** lugar que construye recursos: `Settings`, motor,
  fábrica de sesiones, semáforo de bcrypt y `hash_ficticio`. Todo queda en
  `app.state` y el motor se libera con `dispose()` en el `finally`.
- Importar este módulo **no** abre conexiones ni exige un entorno completo.
- El esquema **no** se crea acá: sólo Alembic (`CV-14`); la aplicación nunca
  crea ni modifica tablas al arrancar. Ninguna migración autogenerada se aplica
  sin leerla antes (regla 9).
- `hash_ficticio` se calcula **una sola vez**, con `asyncio.to_thread`, para que
  el login tarde lo mismo exista o no el correo (`RN-08`) sin bloquear el bucle.
- Reglas que heredan los módulos de dominio: el router construye el UoW
  (`CV-01`), el servicio lo abre, los repositorios sólo hacen `flush()`
  (`CV-02`), `selectinload` vive en `repository.py` (`CV-03`), las FK nuevas
  llevan índice, el dinero es `NUMERIC`/`Decimal` y las fechas nuevas
  `timestamptz`. El token viaja sólo en la cookie `access_token` (`C-11`).

En este change sólo se monta el grupo **abierto** con `health`; el grupo
protegido necesita autenticación y llega con `C-11`.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import bcrypt
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import crear_engine, crear_sessionmaker
from app.modules.health.router import router as health_router

# Importar los modelos de dominio para que SQLModel registre las tablas y
# resuelva las relaciones (back_populates) al arrancar y al autogenerar.
import app.modules.editoriales.models  # noqa: F401
import app.modules.generos.models  # noqa: F401
import app.modules.autores.models  # noqa: F401
import app.modules.libros.models  # noqa: F401
import app.modules.clientes.models  # noqa: F401
import app.modules.ventas.models  # noqa: F401

logger = logging.getLogger("libreria")

# Contraseña ficticia sobre la que se calcula el hash de comparación del login.
# No es un secreto: nunca se valida contra ella.
HASH_DUMMY = b"hash-ficticio-para-tiempo-constante"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado de los recursos de la aplicación."""
    settings = get_settings()

    engine = crear_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = crear_sessionmaker(engine)
    app.state.bcrypt_sem = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY)

    try:
        # bcrypt fuera del bucle de eventos y una sola vez por proceso (RN-08).
        async with app.state.bcrypt_sem:
            app.state.hash_ficticio = await asyncio.to_thread(
                bcrypt.hashpw,
                HASH_DUMMY,
                bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS),
            )
        logger.info("Aplicación iniciada")
        yield
    finally:
        await engine.dispose()
        logger.info("Aplicación detenida; pool de conexiones liberado")


app = FastAPI(title="la librería", version="0.1.0", lifespan=lifespan)

# Grupo abierto: salud + catálogo + clientes + ventas (TP cap. 1-4).
app.include_router(health_router)
from app.modules.editoriales.router import router as editoriales_router
from app.modules.generos.router import router as generos_router
from app.modules.autores.router import router as autores_router
from app.modules.libros.router import router as libros_router
from app.modules.clientes.router import router as clientes_router
from app.modules.ventas.router import router as ventas_router

app.include_router(editoriales_router)
app.include_router(generos_router)
app.include_router(autores_router)
app.include_router(libros_router)
app.include_router(clientes_router)
app.include_router(ventas_router)
