"""Entorno de migraciones de Alembic — plantilla asincrónica.

La URL **no** se hardcodea ni se lee de la configuración de Alembic: se toma de
`Settings`, la misma fuente que usa la aplicación. El motor de migraciones usa
`NullPool` porque es un proceso de vida corta que no debe retener conexiones.

Regla 9 (obligatoria): toda migración autogenerada se **lee** antes de
aplicarse y se corrige a mano si Alembic infiere mal un tipo, un `CHECK` o un
índice. El comentario se deja también en cada migración nueva.

`target_metadata` es `SQLModel.metadata`, vacío hasta que `C-03` cree los
modelos: `C-03`/`C-04` **deben importar los modelos de dominio en este archivo
antes de autogenerar** o la comparación no verá las tablas nuevas.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from app.core.config import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar los modelos de dominio para que autogenerate los vea.
import app.modules.editoriales.models  # noqa: F401
import app.modules.generos.models  # noqa: F401
import app.modules.autores.models  # noqa: F401
import app.modules.libros.models  # noqa: F401
import app.modules.clientes.models  # noqa: F401
import app.modules.ventas.models  # noqa: F401

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Ejecuta las migraciones en modo «offline» (sin conexión)."""
    settings = Settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Ejecuta las migraciones con un motor asincrónico y `NullPool`."""
    settings = Settings()
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
