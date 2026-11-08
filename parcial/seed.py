"""Carga de los datos iniciales del parcial «la librería» (change C-17).

Puesta en marcha
================
Este script se corre **después** de ``alembic upgrade head``, desde ``parcial/``:

    python seed.py

El esquema lo crea únicamente Alembic (``CV-14``): el seed nunca crea ni
modifica tablas al arrancar.

¡Atención: el script vacía la base!
===================================
Al empezar, ``TRUNCATE`` borra las 14 tablas de dominio de la base apuntada por
``Settings`` (``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_DB``). En pantalla
se imprime host, puerto y nombre de la base, **nunca la contraseña**. No se toca
``alembic_version``. Por eso el seed es idempotente: dos corridas dejan el mismo
estado y los mismos identificadores (``venta.id = 1``, libros ``1…5``).

Contraseñas ficticias (para los casos ``.http`` de C-18)
=======================================================
Las cinco cuentas tienen contraseñas de mentira, definidas sólo acá y hasheadas
con bcrypt al ejecutar el script (nunca se versiona un hash precalculado):

- ``admin@example.com``     → ``admin-ficticia-2024``
- ``admin2@example.com``    → ``admin2-ficticia-2024``
- ``vendedor@example.com``  → ``vendedor-ficticia-2024``
- ``ana@example.com``       → ``ana-ficticia-2024``
- ``nuevo@example.com``     → ``nuevo-ficticia-2024``

Ninguna de estas credenciales es real ni aparece en ``env.example`` ni en la
configuración de la aplicación (``CV-09``).

Reglas que respeta el script
============================
- Todo el stock nace del punto único ``LibroRepository.aplicar_movimiento``
  (``RN-11``); los libros se crean con ``stock = 0`` y el valor final es la suma
  de los movimientos (``RN-12``).
- Los repositorios sólo hacen ``flush()``; confirma el ``__aexit__`` del
  ``SeedUnitOfWork`` (``CV-01``, ``CV-02``).
- La transacción es única: o se cargan todos los datos o no se carga ninguno.
- La tabla ``venta`` heredada no tiene columna de vendedor (``SU-07``): quién
  registró la venta 1 queda en ``movimiento_stock.usuario_id``.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from asyncpg.exceptions import UndefinedTableError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.config import get_settings
from app.core.database import crear_engine, crear_sessionmaker
from app.core.security import hash_password
from app.core.unit_of_work import UnitOfWork
from app.modules.autores.models import Autor
from app.modules.autores.repository import AutorRepository
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.clientes.repository import ClienteRepository
from app.modules.editoriales.models import Editorial
from app.modules.editoriales.repository import EditorialRepository
from app.modules.generos.models import Genero
from app.modules.generos.repository import GeneroRepository
from app.modules.libros.models import Libro
from app.modules.libros.repository import LibroRepository
from app.modules.usuarios.models import EventoSeguridad, Usuario
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    UsuarioRepository,
)
from app.modules.ventas.models import RenglonVenta, Venta
from app.modules.ventas.repository import RenglonVentaRepository, VentaRepository

# Registra todas las tablas y relaciones igual que `main.py` antes de usar
# cualquier mapper (Usuario se relaciona con Cliente y con MovimientoStock).
import app.modules.autores.models  # noqa: E402,F401
import app.modules.clientes.models  # noqa: E402,F401
import app.modules.editoriales.models  # noqa: E402,F401
import app.modules.generos.models  # noqa: E402,F401
import app.modules.libros.models  # noqa: E402,F401
import app.modules.usuarios.models  # noqa: E402,F401
import app.modules.ventas.models  # noqa: E402,F401

# --- Contraseñas ficticias (C-18 las usa para el login) ---------------------

PASSWORDS: dict[str, str] = {
    "admin@example.com": "admin-ficticia-2024",
    "admin2@example.com": "admin2-ficticia-2024",
    "vendedor@example.com": "vendedor-ficticia-2024",
    "ana@example.com": "ana-ficticia-2024",
    "nuevo@example.com": "nuevo-ficticia-2024",
}

# --- Datos del seed (contrato de `tests/test_seed_datos.py`) ----------------

# Orden = orden de ids 1..5 de `usuario`.
USUARIOS: tuple[dict[str, Any], ...] = (
    {
        "email": "admin@example.com",
        "nombre": "Administrador",
        "rol": "ADMIN",
        "debe_cambiar_password": False,
    },
    {
        "email": "admin2@example.com",
        "nombre": "Segundo administrador",
        "rol": "ADMIN",
        "debe_cambiar_password": False,
    },
    {
        "email": "vendedor@example.com",
        "nombre": "Vendedor",
        "rol": "VENDEDOR",
        "debe_cambiar_password": False,
    },
    {
        "email": "ana@example.com",
        "nombre": "Ana Paz",
        "rol": "CLIENTE",
        "debe_cambiar_password": False,
    },
    {
        "email": "nuevo@example.com",
        "nombre": "Vendedor nuevo",
        "rol": "VENDEDOR",
        "debe_cambiar_password": True,
    },
)

# Orden = orden de ids 1..3 de `editorial`.
EDITORIALES: tuple[dict[str, str], ...] = (
    {"nombre": "Sudamericana", "pais": "Argentina"},
    {"nombre": "Emecé", "pais": "Argentina"},
    {"nombre": "Losada", "pais": "Argentina"},
)

# Orden = orden de ids 1..3 de `genero`.
GENEROS: tuple[dict[str, str], ...] = (
    {"nombre": "Novela"},
    {"nombre": "Cuentos"},
    {"nombre": "Poesía"},
)

# Orden = orden de ids 1..6 de `autor`.
AUTORES: tuple[dict[str, str], ...] = (
    {"nombre": "Julio Cortázar", "nacionalidad": "Argentina"},
    {"nombre": "Jorge Luis Borges", "nacionalidad": "Argentina"},
    {"nombre": "Adolfo Bioy Casares", "nacionalidad": "Argentina"},
    {"nombre": "Silvina Ocampo", "nacionalidad": "Argentina"},
    {"nombre": "Ricardo Piglia", "nacionalidad": "Argentina"},
    {"nombre": "César Aira", "nacionalidad": "Argentina"},
)

# Orden = orden de ids 1..5 de `libro`. `stock_inicial` es el movimiento
# «Stock inicial» (+); el stock final sale de restarle la venta 1 (RN-11):
# Rayuela 11-1=10, Antología 5, Ficciones 10-2=8, Respiración 3, Bestiario 1.
LIBROS: tuple[dict[str, Any], ...] = (
    {
        "titulo": "Rayuela",
        "isbn": "978-950-00-0001-1",
        "precio": Decimal("25000.00"),
        "editorial": "Sudamericana",
        "genero": "Novela",
        "stock_inicial": 11,
    },
    {
        "titulo": "Antología de la literatura fantástica",
        "isbn": "978-950-00-0002-2",
        "precio": Decimal("30000.00"),
        "editorial": "Emecé",
        "genero": "Cuentos",
        "stock_inicial": 5,
    },
    {
        "titulo": "Ficciones",
        "isbn": "978-950-00-0003-3",
        "precio": Decimal("22000.00"),
        "editorial": "Emecé",
        "genero": "Novela",
        "stock_inicial": 10,
    },
    {
        "titulo": "Respiración artificial",
        "isbn": "978-950-00-0004-4",
        "precio": Decimal("27000.00"),
        "editorial": "Losada",
        "genero": "Novela",
        "stock_inicial": 3,
    },
    {
        "titulo": "Bestiario",
        "isbn": "978-950-00-0005-5",
        "precio": Decimal("18000.00"),
        "editorial": "Sudamericana",
        "genero": "Cuentos",
        "stock_inicial": 1,
    },
)

# Autorías idénticas al seed heredado del TP cap. 1-4.
AUTORIAS: tuple[dict[str, Any], ...] = (
    {"libro": "Rayuela", "autor": "Julio Cortázar", "rol": "autor", "orden": 1},
    {
        "libro": "Antología de la literatura fantástica",
        "autor": "Jorge Luis Borges",
        "rol": "autor",
        "orden": 1,
    },
    {
        "libro": "Antología de la literatura fantástica",
        "autor": "Adolfo Bioy Casares",
        "rol": "coautor",
        "orden": 2,
    },
    {
        "libro": "Antología de la literatura fantástica",
        "autor": "Silvina Ocampo",
        "rol": "coautor",
        "orden": 3,
    },
    {"libro": "Ficciones", "autor": "Jorge Luis Borges", "rol": "autor", "orden": 1},
    {
        "libro": "Respiración artificial",
        "autor": "Ricardo Piglia",
        "rol": "autor",
        "orden": 1,
    },
    {"libro": "Bestiario", "autor": "Julio Cortázar", "rol": "autor", "orden": 1},
)

# Orden = orden de ids 1..3 de `cliente`. `perfil` nulo = sin perfil;
# `usuario_email` nulo = ficha sin cuenta web.
CLIENTES: tuple[dict[str, Any], ...] = (
    {
        "nombre": "Lucía Fernández",
        "email": "lucia@example.com",
        "usuario_email": None,
        "perfil": {"telefono": "111", "direccion": "Calle 1"},
    },
    {
        "nombre": "Tomás Ríos",
        "email": "tomas@example.com",
        "usuario_email": None,
        "perfil": None,
    },
    {
        "nombre": "Ana Paz",
        "email": "ana@example.com",
        "usuario_email": "ana@example.com",
        "perfil": None,
    },
)

# Venta 1 de Lucía: el `precio_unitario` se copia del libro al cargar, así el
# total nunca se despega del catálogo. Sin vendedor: ver `SU-07` en `cargar`.
RENGLONES_VENTA: tuple[dict[str, Any], ...] = (
    {"libro": "Rayuela", "cantidad": 1},
    {"libro": "Ficciones", "cantidad": 2},
)

ACCION_SEED = "Carga de los datos iniciales"

MOTIVO_STOCK_INICIAL = "Stock inicial"
MOTIVO_VENTA = "Venta"

# Las 14 tablas de dominio; `alembic_version` no se toca (CV-14, CV-11).
TABLAS_DOMINIO: tuple[str, ...] = (
    "usuario",
    "asignacion_rol",
    "intento_acceso",
    "evento_seguridad",
    "editorial",
    "genero",
    "autor",
    "libro",
    "libro_autor",
    "cliente",
    "perfil_cliente",
    "venta",
    "renglon_venta",
    "movimiento_stock",
)

CONTEOS_ESPERADOS: dict[str, int] = {
    "usuario": 5,
    "asignacion_rol": 5,
    "editorial": 3,
    "genero": 3,
    "autor": 6,
    "libro": 5,
    "cliente": 3,
    "perfil_cliente": 1,
    "venta": 1,
    "renglon_venta": 2,
    "movimiento_stock": 7,
    "evento_seguridad": 1,
}

# Invariante central (RN-11): stock = suma de movimientos, libro por libro.
SQL_INVARIANTE = (
    "SELECT l.id, l.stock, COALESCE(SUM(m.cantidad), 0) "
    "FROM libro l LEFT JOIN movimiento_stock m ON m.libro_id = l.id "
    "GROUP BY l.id, l.stock "
    "HAVING l.stock <> COALESCE(SUM(m.cantidad), 0)"
)

SQL_VENTA = "SELECT id, total FROM venta ORDER BY id"


# --- Helpers puros (sin base, sin entorno) ----------------------------------


def _libro_por_titulo(titulo: str) -> dict[str, Any]:
    for libro in LIBROS:
        if libro["titulo"] == titulo:
            return libro
    raise KeyError(f"El seed no define el libro {titulo!r}")


def total_venta() -> Decimal:
    """Total de la venta 1: Σ cantidad × precio del catálogo, nunca hardcodeado."""
    total = Decimal("0.00")
    for renglon in RENGLONES_VENTA:
        total += renglon["cantidad"] * _libro_por_titulo(renglon["libro"])["precio"]
    return total


def stock_final(libro: dict[str, Any]) -> int:
    """Stock final = stock inicial − unidades vendidas de ese libro en la venta 1."""
    vendidas = sum(
        renglon["cantidad"]
        for renglon in RENGLONES_VENTA
        if renglon["libro"] == libro["titulo"]
    )
    return int(libro["stock_inicial"]) - vendidas


def sentencia_truncate() -> str:
    """`TRUNCATE` de las 14 tablas de dominio, con identidades reiniciadas.

    No menciona `alembic_version` y no usa `DELETE` (el disparador de RN-12
    rechaza `DELETE` sobre `movimiento_stock`).
    """
    tablas = ", ".join(TABLAS_DOMINIO)
    return f"TRUNCATE TABLE {tablas} RESTART IDENTITY CASCADE"


async def vaciar(session: Any) -> None:
    """Vacía las 14 tablas de dominio con un solo `TRUNCATE`.

    `RESTART IDENTITY` mantiene estables los ids (venta 1, libros 1…5) y
    `CASCADE` sólo evita que las claves foráneas bloqueen la limpieza. No se
    usa `DELETE` (el disparador de RN-12 lo rechaza sobre `movimiento_stock`)
    ni se toca `alembic_version`.
    """
    await session.execute(text(sentencia_truncate()))


class SeedUnitOfWork(UnitOfWork):
    """Transacción única del seed, con los diez repositorios sobre una sesión.

    Contrato (CV-01, CV-02): este script es el *composition root* —igual que el
    router con `Depends`— y lo abre como gestor de contexto asíncrono. Sólo el
    ``__aexit__`` confirma la transacción; ningún repositorio hace commit().
    """

    def __init__(self, session: Any) -> None:
        super().__init__(session)
        self.usuarios = UsuarioRepository(session)
        self.roles = AsignacionRolRepository(session)
        self.eventos = EventoSeguridadRepository(session)
        self.editoriales = EditorialRepository(session)
        self.generos = GeneroRepository(session)
        self.autores = AutorRepository(session)
        self.libros = LibroRepository(session)
        self.clientes = ClienteRepository(session)
        self.ventas = VentaRepository(session)
        self.renglones = RenglonVentaRepository(session)


async def cargar(uow: Any, hashes: Mapping[str, str]) -> None:
    """Carga usuarios, catálogo, clientes, venta 1 y auditoría, en ese orden.

    No hashea: recibe ``hashes`` ya calculados por email (bcrypt corre fuera
    del bucle de eventos y antes de abrir la transacción, ``RN-08``).

    Limitación ``SU-07``: la tabla ``venta`` heredada del TP cap. 1-4 no tiene
    columna de vendedor. «Registrada por ``vendedor@example.com``» se cumple
    donde el modelo lo permite: las dos salidas de la venta 1 llevan su
    ``movimiento_stock.usuario_id``; los «Stock inicial» llevan el del admin
    (la columna es NOT NULL y el cargador es el administrador).

    Nunca se asigna ``libro.stock``: el alta va con ``stock = 0`` y todo el
    stock entra por ``aplicar_movimiento`` (``RN-11``, ``RN-12``).
    """
    # 1. Usuarios y sus roles abiertos, en el orden de USUARIOS (ids 1..5).
    ids_usuarios: dict[str, int] = {}
    creados: list[tuple[Usuario, str]] = []
    for datos in USUARIOS:
        usuario = await uow.usuarios.add(
            Usuario(
                email=datos["email"],
                nombre=datos["nombre"],
                password_hash=hashes[datos["email"]],
                activo=True,
                debe_cambiar_password=datos["debe_cambiar_password"],
            )
        )
        ids_usuarios[datos["email"]] = int(usuario.id)
        creados.append((usuario, datos["rol"]))

    admin_id = ids_usuarios["admin@example.com"]
    for usuario, rol in creados:
        await uow.roles.abrir(
            int(usuario.id),
            rol,
            vence_en=None,
            otorgada_por=None if usuario.email == "admin@example.com" else admin_id,
        )

    # 2. Catálogo: editoriales, géneros y autores (ids estables 1..3 / 1..6).
    ids_editoriales: dict[str, int] = {}
    for datos in EDITORIALES:
        editorial = await uow.editoriales.add(
            Editorial(nombre=datos["nombre"], pais=datos["pais"])
        )
        ids_editoriales[datos["nombre"]] = int(editorial.id)

    ids_generos: dict[str, int] = {}
    for datos in GENEROS:
        genero = await uow.generos.add(Genero(nombre=datos["nombre"]))
        ids_generos[datos["nombre"]] = int(genero.id)

    ids_autores: dict[str, int] = {}
    for datos in AUTORES:
        autor = await uow.autores.add(
            Autor(nombre=datos["nombre"], nacionalidad=datos["nacionalidad"])
        )
        ids_autores[datos["nombre"]] = int(autor.id)

    # 3. Libros con stock = 0, sus autorías y el «Stock inicial» por el punto
    #    único de escritura de stock (RN-11).
    libros: dict[str, Libro] = {}
    for datos in LIBROS:
        libro = await uow.libros.add(
            Libro(
                isbn=datos["isbn"],
                titulo=datos["titulo"],
                precio=datos["precio"],
                stock=0,
                editorial_id=ids_editoriales[datos["editorial"]],
                genero_id=ids_generos[datos["genero"]],
            )
        )
        libros[datos["titulo"]] = libro

    for datos in AUTORIAS:
        await uow.libros.add_autoria(
            int(libros[datos["libro"]].id),
            ids_autores[datos["autor"]],
            datos["rol"],
            datos["orden"],
        )

    for datos in LIBROS:
        await uow.libros.aplicar_movimiento(
            libros[datos["titulo"]],
            int(datos["stock_inicial"]),
            MOTIVO_STOCK_INICIAL,
            admin_id,
        )

    # 4. Clientes: Lucía con perfil y sin usuario; Tomás sin perfil ni usuario;
    #    Ana ligada a la cuenta ana@example.com.
    clientes: dict[str, Cliente] = {}
    for datos in CLIENTES:
        usuario_email = datos["usuario_email"]
        cliente = await uow.clientes.add(
            Cliente(
                nombre=datos["nombre"],
                email=datos["email"],
                usuario_id=ids_usuarios[usuario_email] if usuario_email else None,
            )
        )
        clientes[datos["email"]] = cliente
        perfil = datos["perfil"]
        if perfil is not None:
            await uow.clientes.add_perfil(
                PerfilCliente(
                    cliente_id=int(cliente.id),
                    telefono=perfil["telefono"],
                    direccion=perfil["direccion"],
                )
            )

    # 5. Venta 1 de Lucía: total calculado del catálogo, renglones con el
    #    precio del libro y una salida de stock por renglón.
    venta = await uow.ventas.add(
        Venta(cliente_id=int(clientes["lucia@example.com"].id), total=total_venta())
    )
    venta_id = int(venta.id)
    vendedor_id = ids_usuarios["vendedor@example.com"]
    for datos in RENGLONES_VENTA:
        libro = libros[datos["libro"]]
        cantidad = int(datos["cantidad"])
        await uow.renglones.add(
            RenglonVenta(
                venta_id=venta_id,
                libro_id=int(libro.id),
                cantidad=cantidad,
                precio_unitario=libro.precio,
            )
        )
        await uow.libros.aplicar_movimiento(
            libro,
            -cantidad,
            MOTIVO_VENTA,
            vendedor_id,
            venta_id=venta_id,
        )

    # 6. Una sola línea de auditoría del sistema (RN-16).
    await uow.eventos.add(EventoSeguridad(actor="SISTEMA", accion=ACCION_SEED))


async def verificar(session: Any) -> list[str]:
    """Verifica el resultado del seed y devuelve la lista de problemas.

    Corre, sobre la misma sesión y ya confirmada la transacción: (a) la query
    del invariante de stock de §4 —debe dar 0 filas—; (b) una consulta por
    tabla para comparar con ``CONTEOS_ESPERADOS``; (c) que exista la venta 1
    con total ``total_venta()`` (``Decimal``, nunca ``float``).

    Una lista vacía significa que el seed quedó completo y consistente. Cada
    problema se describe en español, con el libro o la tabla y las cantidades.
    """
    problemas: list[str] = []

    filas = (await session.execute(text(SQL_INVARIANTE))).all()
    for fila in filas:
        libro_id, stock, suma = fila[0], fila[1], fila[2]
        problemas.append(
            f"El libro {libro_id} tiene stock {stock} y sus movimientos suman {suma}"
        )

    for tabla, esperado in CONTEOS_ESPERADOS.items():
        resultado = await session.execute(text(f"SELECT count(*) FROM {tabla}"))
        obtenido = int(resultado.scalar_one())
        if obtenido != esperado:
            problemas.append(
                f"La tabla {tabla} tiene {obtenido} filas y se esperaban {esperado}"
            )

    fila_venta = (await session.execute(text(SQL_VENTA))).first()
    if fila_venta is None:
        problemas.append("No existe la venta con id = 1")
    else:
        venta_id = int(fila_venta[0])
        total = Decimal(str(fila_venta[1]))
        if venta_id != 1:
            problemas.append(
                f"La venta encontrada tiene id {venta_id} y se esperaba id 1"
            )
        if total != total_venta():
            problemas.append(
                f"La venta 1 tiene total {total} y se esperaba {total_venta()}"
            )

    return problemas


# --- Ejecución del seed -----------------------------------------------------


async def _hashear_passwords(settings: Any) -> dict[str, str]:
    """Hashea las cinco contraseñas ficticias fuera del bucle de eventos.

    Un solo semáforo para toda la tanda (``BCRYPT_MAX_CONCURRENCY``), igual que
    el arranque de la aplicación: bcrypt corre en ``to_thread`` y nunca dentro
    del bucle de eventos ni dentro de la transacción (``RN-08``).
    """
    semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY)
    hashes: dict[str, str] = {}
    for datos in USUARIOS:
        email = datos["email"]
        hashes[email] = await hash_password(
            PASSWORDS[email],
            rounds=settings.BCRYPT_ROUNDS,
            semaphore=semaforo,
        )
    return hashes


def _mensaje_configuracion_faltante() -> None:
    """Traduce el fallo de ``Settings`` a un mensaje propio, sin secretos."""
    print(
        "Falta configuración: definí POSTGRES_USER, POSTGRES_PASSWORD, "
        "POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT y JWT_SECRET en el .env "
        "de parcial/ antes de correr el seed.",
        file=sys.stderr,
    )


def _mensaje_tablas_faltantes() -> None:
    """Traduce el esquema sin migrar al mensaje de puesta en marcha."""
    print(
        "Faltan las tablas: aplicá `alembic upgrade head` antes de correr el seed.",
        file=sys.stderr,
    )


async def main() -> None:
    """Punto de entrada: configuración, hashes, carga atómica y verificación."""
    try:
        settings = get_settings()
    except ValidationError:
        _mensaje_configuracion_faltante()
        raise SystemExit(1)

    engine = crear_engine(settings)
    session = crear_sessionmaker(engine)()
    try:
        # Sólo host, puerto y nombre de la base: la contraseña nunca se imprime.
        print(
            f"Seed sobre {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
            f"{settings.POSTGRES_DB} — la base se vacía antes de cargar."
        )

        hashes = await _hashear_passwords(settings)

        async with SeedUnitOfWork(session) as uow:
            await vaciar(session)
            await cargar(uow, hashes)

        problemas = await verificar(session)
        if problemas:
            print(
                "La verificación del seed encontró problemas:", file=sys.stderr
            )
            for problema in problemas:
                print(f"  - {problema}", file=sys.stderr)
            raise SystemExit(1)
    except (ProgrammingError, UndefinedTableError):
        _mensaje_tablas_faltantes()
        raise SystemExit(1)
    finally:
        await session.close()
        await engine.dispose()

    print("Seed OK. Conteos verificados:")
    for tabla, esperado in CONTEOS_ESPERADOS.items():
        print(f"  {tabla}: {esperado}")
    print(f"  venta 1: total {total_venta()}")


if __name__ == "__main__":
    asyncio.run(main())
