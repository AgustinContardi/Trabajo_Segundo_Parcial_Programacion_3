"""Punto de entrada de la API — «la librería» (capítulos 1 a 4).

Contrato de este módulo:

- `lifespan` es el **único** lugar que construye recursos: `Settings`, motor,
  fábrica de sesiones. Todo queda en `app.state` y el motor se libera con
  `dispose()` en el `finally`.
- Importar este módulo **no** abre conexiones ni exige un entorno completo.
- El esquema **no** se crea acá: sólo Alembic (`CV-14`); la aplicación nunca
  crea ni modifica tablas al arrancar. Ninguna migración autogenerada se aplica
  sin leerla antes (regla 9).
- Reglas que heredan los módulos de dominio: el router construye el UoW
  (`CV-01`), el servicio lo abre, los repositorios sólo hacen `flush()`
  (`CV-02`), `selectinload` vive en `repository.py` (`CV-03`), las FK nuevas
  llevan índice, el dinero es `NUMERIC`/`Decimal` y las fechas nuevas
  `timestamptz`.

Aquí se montan los routers de catálogo, clientes, ventas y salud
(TP cap. 1-4). No hay autenticación ni autorización.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado de los recursos de la aplicación."""
    settings = get_settings()

    engine = crear_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = crear_sessionmaker(engine)

    try:
        logger.info("Aplicación iniciada")
        yield
    finally:
        await engine.dispose()
        logger.info("Aplicación detenida; pool de conexiones liberado")


app = FastAPI(title="la librería", version="0.1.0", lifespan=lifespan)

# CORS para desarrollo local: la web puede servirse desde otro origen (por
# ejemplo http://127.0.0.1:8080) y consumir /api. En producción Nginx publica
# frontend y API bajo el mismo origen, así que este middleware no interviene.
# Este backend no usa cookies ni cabeceras de autorización, por eso se permite
# cualquier origen sin credenciales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
