"""Fixtures compartidas de autenticación (C-11).

Las pruebas de integración usan PostgreSQL real (nunca SQLite). Cada usuario
creado por `usuario_factory` lleva un email único y se elimina al terminar la
prueba; los intentos de acceso asociados también se limpian.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import crear_engine, crear_sessionmaker
from app.core.security import hash_password

# Registrar todas las tablas y relaciones igual que `main.py` antes de usar
# cualquier mapper (Usuario se relaciona con Cliente).
import app.modules.autores.models  # noqa: E402,F401
import app.modules.clientes.models  # noqa: E402,F401
import app.modules.editoriales.models  # noqa: E402,F401
import app.modules.generos.models  # noqa: E402,F401
import app.modules.libros.models  # noqa: E402,F401
import app.modules.usuarios.models  # noqa: E402,F401
import app.modules.ventas.models  # noqa: E402,F401
from app.modules.autores.models import Autor
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, LibroAutor
from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario
from app.modules.ventas.models import RenglonVenta, Venta


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuración real del entorno local de pruebas."""
    return get_settings()


@pytest_asyncio.fixture
async def db_sessionmaker(
    settings: Settings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fábrica de sesiones contra PostgreSQL real, liberada al terminar."""
    engine = crear_engine(settings)
    factory = crear_sessionmaker(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def bcrypt_sem(settings: Settings) -> asyncio.Semaphore:
    """Semáforo equivalente al que crea el lifespan."""
    return asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY)


@pytest_asyncio.fixture
async def hash_ficticio(settings: Settings, bcrypt_sem: asyncio.Semaphore) -> str:
    """Hash de costo equivalente al que calcula el lifespan para RN-08."""
    return await hash_password(
        "clave-ficticia-nunca-valida",
        rounds=settings.BCRYPT_ROUNDS,
        semaphore=bcrypt_sem,
    )


def email_unico(prefijo: str = "auth") -> str:
    """Email irrepetible para aislar los datos de cada prueba."""
    return f"{prefijo}-{uuid.uuid4().hex}@example.com"


@pytest_asyncio.fixture
async def email_desconocido_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Callable[[str], str]]:
    """Genera emails sin cuenta y limpia los intentos que produzcan."""
    correos: list[str] = []

    def crear(prefijo: str = "no-existe") -> str:
        correo = email_unico(prefijo)
        correos.append(correo)
        return correo

    yield crear

    if not correos:
        return
    async with db_sessionmaker() as session:
        await session.execute(
            delete(IntentoAcceso).where(IntentoAcceso.email.in_(correos))
        )
        await session.commit()


@pytest_asyncio.fixture
async def usuario_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem: asyncio.Semaphore,
) -> AsyncIterator[Callable[..., Awaitable[Usuario]]]:
    """Crea usuarios con roles y elimina todo lo creado al final de la prueba."""
    emails: list[str] = []

    async def crear(
        *,
        email: str | None = None,
        password: str = "clave-segura-123",
        activo: bool = True,
        roles: tuple[str, ...] = ("CLIENTE",),
        debe_cambiar_password: bool = False,
        password_hash: str | None = None,
    ) -> Usuario:
        correo = email or email_unico()
        emails.append(correo)
        if password_hash is None:
            password_hash = await hash_password(
                password,
                rounds=settings.BCRYPT_ROUNDS,
                semaphore=bcrypt_sem,
            )

        async with db_sessionmaker() as session:
            usuario = Usuario(
                email=correo,
                nombre="Usuario de prueba",
                password_hash=password_hash,
                activo=activo,
                debe_cambiar_password=debe_cambiar_password,
            )
            session.add(usuario)
            await session.flush()
            for rol in roles:
                session.add(
                    AsignacionRol(
                        usuario_id=usuario.id,
                        rol=rol,
                        desde=datetime.now(timezone.utc),
                    )
                )
            await session.commit()
            return usuario

    yield crear

    if not emails:
        return
    async with db_sessionmaker() as session:
        ids = list(
            (
                await session.execute(
                    select(Usuario.id).where(Usuario.email.in_(emails))
                )
            ).scalars()
        )
        if ids:
            await session.execute(
                delete(AsignacionRol).where(
                    or_(
                        AsignacionRol.usuario_id.in_(ids),
                        AsignacionRol.otorgada_por.in_(ids),
                    )
                )
            )
        await session.execute(
            delete(IntentoAcceso).where(IntentoAcceso.email.in_(emails))
        )
        await session.execute(delete(Usuario).where(Usuario.email.in_(emails)))
        await session.commit()


@pytest_asyncio.fixture
async def cliente_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Callable[..., Awaitable[Cliente]]]:
    """Crea clientes con email único y elimina todo lo creado al final."""
    creados: list[int] = []

    async def crear(
        *,
        nombre: str = "Cliente de prueba",
        email: str | None = None,
        usuario_id: int | None = None,
    ) -> Cliente:
        correo = email or email_unico("cliente")
        async with db_sessionmaker() as session:
            obj = Cliente(nombre=nombre, email=correo, usuario_id=usuario_id)
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        creados.append(obj.id)
        return obj

    def registrar(cliente_id: int) -> None:
        creados.append(cliente_id)

    crear.registrar = registrar  # type: ignore[attr-defined]
    yield crear

    if not creados:
        return
    async with db_sessionmaker() as session:
        venta_ids = list(
            (
                await session.execute(
                    select(Venta.id).where(Venta.cliente_id.in_(creados))
                )
            ).scalars()
        )
        if venta_ids:
            await session.execute(
                delete(RenglonVenta).where(RenglonVenta.venta_id.in_(venta_ids))
            )
            await session.execute(delete(Venta).where(Venta.id.in_(venta_ids)))
        await session.execute(
            delete(PerfilCliente).where(PerfilCliente.cliente_id.in_(creados))
        )
        await session.execute(delete(Cliente).where(Cliente.id.in_(creados)))
        await session.commit()


@pytest_asyncio.fixture
async def venta_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    cliente_factory,
) -> AsyncIterator[Callable[..., Awaitable[Venta]]]:
    """Crea ventas para un cliente existente y las elimina al final."""
    creadas: list[int] = []

    async def crear(
        *,
        cliente_id: int,
        total: Decimal = Decimal("10.00"),
    ) -> Venta:
        async with db_sessionmaker() as session:
            obj = Venta(
                cliente_id=cliente_id,
                fecha=datetime.now(timezone.utc),
                total=total,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        creadas.append(obj.id)
        return obj

    yield crear

    if not creadas:
        return
    async with db_sessionmaker() as session:
        await session.execute(
            delete(RenglonVenta).where(RenglonVenta.venta_id.in_(creadas))
        )
        await session.execute(delete(Venta).where(Venta.id.in_(creadas)))
        await session.commit()


@pytest_asyncio.fixture
async def catalogo_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SimpleNamespace]:
    """Crea editorial, género, autor y libro de prueba; limpia al final."""
    editoriales: list[int] = []
    generos: list[int] = []
    autores: list[int] = []
    libros: list[int] = []

    async def editorial(nombre: str | None = None, pais: str = "Argentina") -> Editorial:
        async with db_sessionmaker() as session:
            obj = Editorial(
                nombre=nombre or f"Editorial {uuid.uuid4().hex}",
                pais=pais,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        editoriales.append(obj.id)
        return obj

    async def genero(nombre: str | None = None) -> Genero:
        async with db_sessionmaker() as session:
            obj = Genero(nombre=nombre or f"Genero {uuid.uuid4().hex}")
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        generos.append(obj.id)
        return obj

    async def autor(
        nombre: str | None = None, nacionalidad: str = "Argentina"
    ) -> Autor:
        async with db_sessionmaker() as session:
            obj = Autor(
                nombre=nombre or f"Autor {uuid.uuid4().hex}",
                nacionalidad=nacionalidad,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        autores.append(obj.id)
        return obj

    async def libro(
        *,
        editorial_id: int,
        genero_id: int | None = None,
        isbn: str | None = None,
        titulo: str | None = None,
        precio: Decimal = Decimal("10.00"),
        stock: int = 0,
    ) -> Libro:
        async with db_sessionmaker() as session:
            obj = Libro(
                isbn=isbn or f"isbn-{uuid.uuid4().hex}",
                titulo=titulo or f"Libro {uuid.uuid4().hex}",
                precio=precio,
                stock=stock,
                editorial_id=editorial_id,
                genero_id=genero_id,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        libros.append(obj.id)
        return obj

    yield SimpleNamespace(
        editorial=editorial,
        genero=genero,
        autor=autor,
        libro=libro,
        registrar_libro=libros.append,
        registrar_editorial=editoriales.append,
        registrar_genero=generos.append,
        registrar_autor=autores.append,
    )

    async with db_sessionmaker() as session:
        if libros:
            await session.execute(
                delete(RenglonVenta).where(RenglonVenta.libro_id.in_(libros))
            )
            await session.execute(
                delete(LibroAutor).where(LibroAutor.libro_id.in_(libros))
            )
            await session.execute(delete(Libro).where(Libro.id.in_(libros)))
        if autores:
            await session.execute(delete(Autor).where(Autor.id.in_(autores)))
        if generos:
            await session.execute(delete(Genero).where(Genero.id.in_(generos)))
        if editoriales:
            await session.execute(
                delete(Editorial).where(Editorial.id.in_(editoriales))
            )
        await session.commit()


@pytest_asyncio.fixture
async def api_app():
    """Aplicación FastAPI real (sin arrancar el lifespan todavía)."""
    from main import app

    return app


@pytest_asyncio.fixture
async def api_client(api_app) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente ASGI de la aplicación real, con lifespan y PostgreSQL real."""
    async with api_app.router.lifespan_context(api_app):
        transport = httpx.ASGITransport(app=api_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client


def cabecera_cookie(response: httpx.Response) -> str:
    """Devuelve el `Set-Cookie` de acceso de una respuesta."""
    valores = response.headers.get_list("set-cookie")
    for valor in valores:
        if valor.startswith("access_token="):
            return valor
    raise AssertionError("La respuesta no incluye la cookie access_token")


async def contar_intentos(
    sessionmaker: async_sessionmaker[AsyncSession], email: str
) -> int:
    """Cuenta las filas de intento_acceso de un email."""
    async with sessionmaker() as session:
        result = await session.execute(
            select(IntentoAcceso).where(IntentoAcceso.email == email)
        )
        return len(list(result.scalars().all()))


def token_manual(
    *,
    subject: int | str,
    secret: str,
    exp_offset_seconds: int = 1800,
    roles: list[str] | None = None,
) -> str:
    """Firma un JWT de prueba sin pasar por el helper de emisión."""
    import jwt
    from datetime import timedelta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=exp_offset_seconds),
    }
    if roles is not None:
        payload["roles"] = roles
    return jwt.encode(payload, secret, algorithm="HS256")
