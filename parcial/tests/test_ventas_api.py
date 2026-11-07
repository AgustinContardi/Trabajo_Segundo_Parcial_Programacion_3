"""Integración de POST /ventas contra PostgreSQL real (CHECKLIST §7, §8, §10).

Cada prueba crea sus propios datos y verifica deltas dentro de la prueba
(`antes` vs `despues`), nunca conteos absolutos, porque `movimiento_stock` es
de s�lo agregado (RN-12: trigger bloquea UPDATE/DELETE) y las FK de
`libro`/`venta`/`usuario` son `NO ACTION`, por lo que una venta confirmada
pincha sus filas y no se pueden borrar en el teardown.

Las pruebas 201 insertan usuario/cliente/libro directamente (sin factories,
sin teardown que intente borrarlas); las que no escriben (409/422/403/401)
usan las factories de forma segura.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.clientes.models import Cliente
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.libros.models import Libro, MovimientoStock
from app.modules.usuarios.models import AsignacionRol, Usuario
from app.modules.ventas.models import RenglonVenta, Venta

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


def _email(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex}@example.com"


async def _login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> None:
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _crear_vendedor(sessionmaker: async_sessionmaker) -> Usuario:
    settings = get_settings()
    hash_ = await hash_password(
        PASSWORD, rounds=settings.BCRYPT_ROUNDS, semaphore=asyncio.Semaphore(4)
    )
    async with sessionmaker() as session:
        usuario = Usuario(
            email=_email("vendedor"),
            nombre="Vendedor",
            password_hash=hash_,
            activo=True,
        )
        session.add(usuario)
        await session.flush()
        session.add(
            AsignacionRol(
                usuario_id=usuario.id,
                rol="VENDEDOR",
                desde=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        await session.refresh(usuario)
        return usuario


async def _crear_cliente(sessionmaker: async_sessionmaker) -> Cliente:
    async with sessionmaker() as session:
        cliente = Cliente(nombre="Cliente", email=_email("cliente"))
        session.add(cliente)
        await session.commit()
        await session.refresh(cliente)
        return cliente


async def _crear_libros(
    sessionmaker: async_sessionmaker, specs: list[tuple[Decimal, int]]
) -> list[Libro]:
    async with sessionmaker() as session:
        editorial = Editorial(nombre=f"Ed {uuid.uuid4().hex}", pais="Argentina")
        genero = Genero(nombre=f"Ge {uuid.uuid4().hex}")
        session.add_all([editorial, genero])
        await session.flush()
        libros: list[Libro] = []
        for precio, stock in specs:
            libros.append(
                Libro(
                    isbn=f"isbn-{uuid.uuid4().hex}",
                    titulo=f"Libro {uuid.uuid4().hex}",
                    precio=precio,
                    stock=stock,
                    editorial_id=editorial.id,
                    genero_id=genero.id,
                )
            )
            session.add(libros[-1])
        await session.commit()
        for libro in libros:
            await session.refresh(libro)
        return libros


async def _conteos(sessionmaker: async_sessionmaker) -> tuple[int, int, int]:
    async with sessionmaker() as session:
        ventas = (
            await session.execute(select(func.count()).select_from(Venta))
        ).scalar_one()
        renglones = (
            await session.execute(select(func.count()).select_from(RenglonVenta))
        ).scalar_one()
        movimientos = (
            await session.execute(select(func.count()).select_from(MovimientoStock))
        ).scalar_one()
        return int(ventas), int(renglones), int(movimientos)


async def _stock_y_movimientos(
    sessionmaker: async_sessionmaker, libro_id: int
) -> tuple[int, Decimal]:
    async with sessionmaker() as session:
        stock = (
            await session.execute(select(Libro.stock).where(Libro.id == libro_id))
        ).scalar_one()
        suma = (
            await session.execute(
                select(func.coalesce(func.sum(MovimientoStock.cantidad), 0)).where(
                    MovimientoStock.libro_id == libro_id
                )
            )
        ).scalar_one()
        return int(stock), Decimal(suma or 0)


async def _post(
    client: httpx.AsyncClient,
    cliente_id: int,
    renglones: list[dict],
    extra: dict | None = None,
) -> httpx.Response:
    cuerpo: dict = {"cliente_id": cliente_id, "renglones": renglones}
    if extra:
        cuerpo.update(extra)
    return await client.post("/ventas/", json=cuerpo)


async def _escenario_venta(
    sessionmaker: async_sessionmaker,
) -> tuple[Usuario, Cliente, Libro, Libro]:
    vendedor = await _crear_vendedor(sessionmaker)
    cliente = await _crear_cliente(sessionmaker)
    libro_a, libro_b = await _crear_libros(
        sessionmaker, [(Decimal("10.00"), 5), (Decimal("20.00"), 4)]
    )
    return vendedor, cliente, libro_a, libro_b


async def test_alta_valida_dos_renglones(
    api_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, libro_b = await _escenario_venta(db_sessionmaker)
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client,
        cliente.id,
        [
            {"libro_id": libro_a.id, "cantidad": 2},
            {"libro_id": libro_b.id, "cantidad": 3},
        ],
    )

    assert response.status_code == 201, response.text
    cuerpo = response.json()
    assert cuerpo["cliente_id"] == cliente.id
    assert Decimal(str(cuerpo["total"])) == Decimal("80.00")  # 2*10 + 3*20
    assert len(cuerpo["renglones"]) == 2
    r1, r2 = cuerpo["renglones"]
    assert Decimal(str(r1["precio_unitario"])) == Decimal("10.00")
    assert Decimal(str(r2["precio_unitario"])) == Decimal("20.00")
    assert r1["cantidad"] == 2 and r2["cantidad"] == 3

    despues = await _conteos(db_sessionmaker)
    assert despues[0] == antes[0] + 1
    assert despues[1] == antes[1] + 2
    assert despues[2] == antes[2] + 2

    venta_id = cuerpo["id"]
    stock_a, suma_a = await _stock_y_movimientos(db_sessionmaker, libro_a.id)
    stock_b, suma_b = await _stock_y_movimientos(db_sessionmaker, libro_b.id)
    assert stock_a == 3  # 5 - 2
    assert stock_b == 1  # 4 - 3
    assert suma_a == Decimal("-2")
    assert suma_b == Decimal("-3")
    # Conservaci�n (RN-11): variaci�n de stock == variaci�n de la suma de movimientos.
    assert stock_a - 5 == suma_a  # -2 == -2
    assert stock_b - 4 == suma_b  # -3 == -3

    # Un movimiento por rengl�n: cantidad < 0, motivo Venta, usuario vendedor.
    async with db_sessionmaker() as session:
        movs = (
            await session.execute(
                select(MovimientoStock).where(MovimientoStock.venta_id == venta_id)
            )
        ).scalars().all()
    assert len(movs) == 2
    for mov in movs:
        assert mov.cantidad < 0
        assert mov.motivo == "Venta"
        assert mov.usuario_id == vendedor.id


async def test_stock_justo_es_valido(
    api_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _escenario_venta(db_sessionmaker)
    async with db_sessionmaker() as session:
        await session.execute(
            update(Libro).where(Libro.id == libro_a.id).values(stock=2)
        )
        await session.commit()

    await _login(api_client, vendedor.email)
    response = await _post(
        api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": 2}]
    )

    assert response.status_code == 201, response.text
    assert Decimal(str(response.json()["total"])) == Decimal("20.00")

    async with db_sessionmaker() as session:
        stock = (
            await session.execute(
                select(Libro.stock).where(Libro.id == libro_a.id)
            )
        ).scalar_one()
    assert stock == 0


async def test_aviso_comprobante_deja_log_visible(
    api_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker,
    caplog,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _escenario_venta(db_sessionmaker)
    await _login(api_client, vendedor.email)

    with caplog.at_level("WARNING", logger="libreria.avisos"):
        response = await _post(api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": 1}])

    assert response.status_code == 201
    venta_id = response.json()["id"]
    assert any("Comprobante de la venta" in record.getMessage() for record in caplog.records)
    assert any(str(venta_id) in record.getMessage() for record in caplog.records)


# --- Pruebas que NO escriben: factories seguras (nada queda pinchado) ---


async def _setup_factories(usuario_factory, cliente_factory, catalogo_factory):
    vendedor = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    cliente = await cliente_factory()
    editorial = await catalogo_factory.editorial()
    genero = await catalogo_factory.genero()
    libro_a = await catalogo_factory.libro(
        editorial_id=editorial.id,
        genero_id=genero.id,
        precio=Decimal("10.00"),
        stock=5,
    )
    libro_b = await catalogo_factory.libro(
        editorial_id=editorial.id,
        genero_id=genero.id,
        precio=Decimal("20.00"),
        stock=4,
    )
    return vendedor, cliente, libro_a, libro_b


async def test_stock_insuficiente_devuelve_409_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    async with db_sessionmaker() as session:
        await session.execute(
            update(Libro).where(Libro.id == libro_a.id).values(stock=1)
        )
        await session.commit()

    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)
    stock_antes, _ = await _stock_y_movimientos(db_sessionmaker, libro_a.id)

    response = await _post(api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": 2}])

    assert response.status_code == 409, response.text
    assert await _conteos(db_sessionmaker) == antes  # nada creci�
    stock_despues, _ = await _stock_y_movimientos(db_sessionmaker, libro_a.id)
    assert stock_despues == stock_antes  # stock intacto


async def test_cliente_inexistente_devuelve_409_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(api_client, 999999999, [{"libro_id": libro_a.id, "cantidad": 1}])

    assert response.status_code == 409
    assert await _conteos(db_sessionmaker) == antes


async def test_libro_inexistente_devuelve_409_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, _libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(api_client, cliente.id, [{"libro_id": 999999999, "cantidad": 1}])

    assert response.status_code == 409
    assert await _conteos(db_sessionmaker) == antes


async def test_libro_dado_de_baja_devuelve_409_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    async with db_sessionmaker() as session:
        await session.execute(
            update(Libro).where(Libro.id == libro_a.id)
            .values(borrado_en=datetime.now(timezone.utc))
        )
        await session.commit()

    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": 1}])

    assert response.status_code == 409
    assert await _conteos(db_sessionmaker) == antes


@pytest.mark.parametrize("campo_extra", ["precio", "total", "fecha"])
async def test_campo_extra_devuelve_422_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
    campo_extra: str,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client,
        cliente.id,
        [{"libro_id": libro_a.id, "cantidad": 1}],
        extra={campo_extra: 1},
    )

    assert response.status_code == 422
    assert await _conteos(db_sessionmaker) == antes


async def test_cero_renglones_devuelve_422(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, _libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(api_client, cliente.id, [])

    assert response.status_code == 422
    assert await _conteos(db_sessionmaker) == antes


async def test_libro_id_repetido_devuelve_422(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client,
        cliente.id,
        [{"libro_id": libro_a.id, "cantidad": 1}, {"libro_id": libro_a.id, "cantidad": 2}],
    )

    assert response.status_code == 422
    assert await _conteos(db_sessionmaker) == antes


async def test_cantidad_cero_devuelve_422(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": 0}])

    assert response.status_code == 422
    assert await _conteos(db_sessionmaker) == antes


async def test_cliente_rol_devuelve_403(api_client: httpx.AsyncClient, usuario_factory) -> None:
    cliente_rol = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    await _login(api_client, cliente_rol.email)

    response = await _post(api_client, 1, [{"libro_id": 1, "cantidad": 1}])
    assert response.status_code == 403


async def test_sin_sesion_devuelve_401(api_client: httpx.AsyncClient) -> None:
    response = await _post(api_client, 1, [{"libro_id": 1, "cantidad": 1}])
    assert response.status_code == 401
