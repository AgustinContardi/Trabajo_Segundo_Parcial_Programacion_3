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
from app.modules.libros.repository import LibroRepository
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
    sessionmaker: async_sessionmaker,
    specs: list[tuple[Decimal, int]],
    usuario_id: int,
) -> list[Libro]:
    """Crea libros con el stock sembrado por el punto único (RN-11)."""
    async with sessionmaker() as session:
        editorial = Editorial(nombre=f"Ed {uuid.uuid4().hex}", pais="Argentina")
        genero = Genero(nombre=f"Ge {uuid.uuid4().hex}")
        session.add_all([editorial, genero])
        await session.flush()
        repo = LibroRepository(session)
        libros: list[Libro] = []
        for precio, stock in specs:
            libro = Libro(
                isbn=f"isbn-{uuid.uuid4().hex}",
                titulo=f"Libro {uuid.uuid4().hex}",
                precio=precio,
                stock=0,
                editorial_id=editorial.id,
                genero_id=genero.id,
            )
            session.add(libro)
            await session.flush()
            if stock:
                await repo.aplicar_movimiento(
                    libro, stock, "Stock inicial", usuario_id
                )
            libros.append(libro)
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
    specs: list[tuple[Decimal, int]] | None = None,
) -> tuple[Usuario, Cliente, Libro, Libro]:
    vendedor = await _crear_vendedor(sessionmaker)
    cliente = await _crear_cliente(sessionmaker)
    libro_a, libro_b = await _crear_libros(
        sessionmaker,
        specs or [(Decimal("10.00"), 5), (Decimal("20.00"), 4)],
        vendedor.id,
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
    # Invariante global (RN-11) tras la venta: stock == SUM(movimientos).
    # Libro A: +5 inicial -2 venta = 3; Libro B: +4 inicial -3 venta = 1.
    assert suma_a == Decimal("3")
    assert suma_b == Decimal("1")
    # Conservaci�n (RN-11): variaci�n de stock == variaci�n de la suma de movimientos.
    assert stock_a == suma_a
    assert stock_b == suma_b

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
    vendedor, cliente, libro_a, _libro_b = await _escenario_venta(
        db_sessionmaker, specs=[(Decimal("10.00"), 2), (Decimal("20.00"), 4)]
    )

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


async def _setup_factories(
    usuario_factory, cliente_factory, catalogo_factory, *, stock_a: int = 5
):
    vendedor = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    cliente = await cliente_factory()
    editorial = await catalogo_factory.editorial()
    genero = await catalogo_factory.genero()
    libro_a = await catalogo_factory.libro(
        editorial_id=editorial.id,
        genero_id=genero.id,
        precio=Decimal("10.00"),
        stock=stock_a,
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
        usuario_factory, cliente_factory, catalogo_factory, stock_a=1
    )

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


async def test_duplicado_con_cliente_inexistente_devuelve_409_no_422(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, _cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client,
        999999999,
        [
            {"libro_id": libro_a.id, "cantidad": 1},
            {"libro_id": libro_a.id, "cantidad": 1},
        ],
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "El cliente indicado no existe"
    assert await _conteos(db_sessionmaker) == antes


async def test_duplicado_con_libro_inexistente_devuelve_409_no_422(
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

    response = await _post(
        api_client,
        cliente.id,
        [
            {"libro_id": 999999999, "cantidad": 1},
            {"libro_id": 999999999, "cantidad": 1},
        ],
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Uno o más libros indicados no existen"
    assert await _conteos(db_sessionmaker) == antes


async def test_duplicado_con_stock_agregado_insuficiente_devuelve_409(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, _libro_a, libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    # libro_b tiene stock 4: cada renglón pide 2 (pasa solo), la suma pide 6.
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)
    stock_antes, _ = await _stock_y_movimientos(db_sessionmaker, libro_b.id)

    response = await _post(
        api_client,
        cliente.id,
        [
            {"libro_id": libro_b.id, "cantidad": 2},
            {"libro_id": libro_b.id, "cantidad": 2},
            {"libro_id": libro_b.id, "cantidad": 2},
        ],
    )

    assert response.status_code == 409, response.text
    assert "Stock insuficiente" in response.json()["detail"]
    assert await _conteos(db_sessionmaker) == antes
    stock_despues, _ = await _stock_y_movimientos(db_sessionmaker, libro_b.id)
    assert stock_despues == stock_antes


async def test_post_ventas_sin_barra_final_no_redirige(
    api_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker,
) -> None:
    vendedor, cliente, libro_a, libro_b = await _escenario_venta(db_sessionmaker)
    await _login(api_client, vendedor.email)

    sin_barra = await api_client.post(
        "/ventas",
        json={
            "cliente_id": cliente.id,
            "renglones": [{"libro_id": libro_a.id, "cantidad": 1}],
        },
    )
    con_barra = await api_client.post(
        "/ventas/",
        json={
            "cliente_id": cliente.id,
            "renglones": [{"libro_id": libro_b.id, "cantidad": 1}],
        },
    )

    assert sin_barra.status_code == 201, sin_barra.text
    assert con_barra.status_code == 201, con_barra.text
    assert sin_barra.history == []  # sin 307
    assert con_barra.history == []
    cuerpo_sin = sin_barra.json()
    cuerpo_con = con_barra.json()
    assert set(cuerpo_sin) == set(cuerpo_con)
    assert cuerpo_sin["cliente_id"] == cuerpo_con["cliente_id"] == cliente.id
    assert len(cuerpo_sin["renglones"]) == len(cuerpo_con["renglones"]) == 1


async def test_openapi_documenta_solo_post_ventas_con_barra(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "post" in paths["/ventas/"]
    assert "post" not in paths.get("/ventas", {})


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


TEXTOS_PROHIBIDOS = (
    "postgres",
    "asyncpg",
    "psycopg",
    "traceback",
    "value out of",
    "invalid input",
    "sqlalchemy",
    "bigint",
    "integer out of range",
)


def _assert_422_en_espanol(response: httpx.Response) -> list[dict]:
    """Afirma 422, detalle con `loc`/`type` y mensaje propio en español."""
    assert response.status_code == 422, response.text
    detalle = response.json()["detail"]
    assert isinstance(detalle, list) and detalle
    for item in detalle:
        assert {"loc", "msg", "type"} <= set(item)
        assert isinstance(item["msg"], str) and item["msg"].strip()
    texto = " ".join(item["msg"].lower() for item in detalle)
    for prohibido in TEXTOS_PROHIBIDOS:
        assert prohibido not in texto, f"el mensaje filtra {prohibido!r}: {texto!r}"
    assert "debe" in texto or "falta" in texto or "supera" in texto
    return detalle


@pytest.mark.parametrize("campo", ["cliente_id", "libro_id"])
@pytest.mark.parametrize("valor", [10**30, 2**63])
async def test_id_fuera_de_rango_devuelve_422_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
    campo: str,
    valor: int,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    cuerpo = {
        "cliente_id": cliente.id if campo == "cliente_id" else valor,
        "renglones": [
            {
                "libro_id": libro_a.id if campo == "libro_id" else valor,
                "cantidad": 1,
            }
        ],
    }
    # Si el campo bajo prueba no es el del renglón, el otro debe ser válido.
    if campo == "cliente_id":
        cuerpo["cliente_id"] = valor
        cuerpo["renglones"][0]["libro_id"] = libro_a.id
    response = await api_client.post("/ventas/", json=cuerpo)

    detalle = _assert_422_en_espanol(response)
    assert any("supera el máximo permitido" in item["msg"] for item in detalle)
    assert await _conteos(db_sessionmaker) == antes


@pytest.mark.parametrize("valor", [True, False])
async def test_cantidad_booleana_devuelve_422_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
    valor: bool,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": valor}]
    )

    detalle = _assert_422_en_espanol(response)
    assert any("número entero válido" in item["msg"] for item in detalle)
    assert await _conteos(db_sessionmaker) == antes


@pytest.mark.parametrize("valor", ["1", "2", 1.0, 1.5])
async def test_cantidad_tipo_string_o_float_devuelve_422_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
    valor,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": valor}]
    )

    detalle = _assert_422_en_espanol(response)
    assert any("número entero válido" in item["msg"] for item in detalle)
    assert await _conteos(db_sessionmaker) == antes


@pytest.mark.parametrize("valor", [2**31, 10**20])
async def test_cantidad_fuera_de_rango_devuelve_422_sin_escribir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    catalogo_factory,
    db_sessionmaker: async_sessionmaker,
    valor: int,
) -> None:
    vendedor, cliente, libro_a, _libro_b = await _setup_factories(
        usuario_factory, cliente_factory, catalogo_factory
    )
    await _login(api_client, vendedor.email)
    antes = await _conteos(db_sessionmaker)

    response = await _post(
        api_client, cliente.id, [{"libro_id": libro_a.id, "cantidad": valor}]
    )

    detalle = _assert_422_en_espanol(response)
    assert any("supera el máximo permitido" in item["msg"] for item in detalle)
    assert await _conteos(db_sessionmaker) == antes


async def test_cliente_rol_devuelve_403(api_client: httpx.AsyncClient, usuario_factory) -> None:
    cliente_rol = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    await _login(api_client, cliente_rol.email)

    response = await _post(api_client, 1, [{"libro_id": 1, "cantidad": 1}])
    assert response.status_code == 403


async def test_sin_sesion_devuelve_401(api_client: httpx.AsyncClient) -> None:
    response = await _post(api_client, 1, [{"libro_id": 1, "cantidad": 1}])
    assert response.status_code == 401
