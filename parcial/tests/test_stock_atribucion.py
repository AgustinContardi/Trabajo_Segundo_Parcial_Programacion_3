"""C-08/C-09: el movimiento de stock se atribuye al usuario autenticado.

La prueba de API crea dos administradores y usa el **segundo**; el `usuario_id`
de «Stock inicial» y «Reposición» debe ser el del actor, nunca el primer
usuario de la base (el fallback que la auditoría señaló).
"""

import uuid

import httpx
import pytest
from fastapi import HTTPException

from app.modules.libros import service
from app.modules.libros.schemas import LibroCreate

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura" + "-123"


async def _login(client: httpx.AsyncClient, usuario, password: str = PASSWORD) -> None:
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": usuario.email, "password": password}
    )
    assert response.status_code == 200, response.text


# --- API: atribución real contra PostgreSQL ---


async def test_stock_inicial_y_reposicion_firman_con_el_actor(
    api_client: httpx.AsyncClient,
    api_app,
    settings,
    usuario_factory,
    catalogo_factory,
) -> None:
    """Crea el libro y repone dentro de una transacción que se revierte.

    `movimiento_stock` es append-only y su FK pincha al usuario: sin revertir,
    el teardown de `usuario_factory` no podría borrar a los administradores.
    """
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.database import crear_engine, get_session

    primero = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    segundo = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    editorial = await catalogo_factory.editorial()

    engine = crear_engine(settings)
    conexion = await engine.connect()
    transaccion = await conexion.begin()
    fabrica = async_sessionmaker(
        bind=conexion,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    sesion = fabrica()

    async def sesion_compartida(request: Request):
        yield sesion

    api_app.dependency_overrides[get_session] = sesion_compartida
    try:
        await _login(api_client, segundo)
        creado = await api_client.post(
            "/libros/",
            json={
                "isbn": f"isbn-atribucion-{uuid.uuid4().hex}",
                "titulo": "Atribución de stock",
                "precio": "10.00",
                "stock_inicial": 3,
                "editorial_id": editorial.id,
                "autores": [],
            },
        )
        assert creado.status_code == 201, creado.text
        libro_id = creado.json()["id"]

        repuesto = await api_client.post(
            f"/libros/{libro_id}/reponer", json={"cantidad": 2}
        )
        assert repuesto.status_code == 200, repuesto.text
        assert repuesto.json()["stock"] == 5

        movimientos = await api_client.get(f"/libros/{libro_id}/movimientos")
        assert movimientos.status_code == 200, movimientos.text
        por_motivo = {m["motivo"]: m for m in movimientos.json()}

        assert set(por_motivo) == {"Stock inicial", "Reposición"}
        for movimiento in por_motivo.values():
            assert movimiento["usuario_id"] == segundo.id
            assert movimiento["usuario_id"] != primero.id
    finally:
        api_app.dependency_overrides.pop(get_session, None)
        await sesion.close()
        await transaccion.rollback()
        await conexion.close()
        await engine.dispose()


# --- Servicio: sin actor no se escribe un movimiento ---


class _LibrosFalso:
    """Repositorio de libros mínimo: registra movimientos y presta un libro."""

    def __init__(self) -> None:
        self.movimientos: list[tuple[str, int]] = []
        self.libro = None

    async def add(self, libro) -> None:
        libro.id = 101

    async def add_autoria(self, libro_id, autor_id, rol, orden) -> None:
        return None

    async def aplicar_movimiento(
        self, libro, cantidad, motivo, usuario_id, venta_id=None
    ):
        self.movimientos.append((motivo, usuario_id))
        libro.stock += cantidad
        return None

    async def get_by_id_including_deleted(self, libro_id):
        return self.libro

    async def get_by_id(self, libro_id):
        return self.libro


class _UoWFalso:
    def __init__(self, libros: _LibrosFalso) -> None:
        self.libros = libros
        self.session = None

    async def __aenter__(self) -> "_UoWFalso":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _datos(stock_inicial: int) -> LibroCreate:
    return LibroCreate(
        isbn="isbn-sin-actor",
        titulo="Sin actor",
        precio="10.00",
        stock_inicial=stock_inicial,
        editorial_id=1,
        autores=[],
    )


async def test_crear_con_stock_sin_actor_da_409_y_no_escribe_movimiento() -> None:
    libros = _LibrosFalso()
    uow = _UoWFalso(libros)

    with pytest.raises(HTTPException) as excinfo:
        await service.crear(uow, _datos(stock_inicial=3))

    assert excinfo.value.status_code == 409
    assert libros.movimientos == []


async def test_reponer_sin_actor_da_409_y_no_escribe_movimiento() -> None:
    from app.modules.libros.models import Libro

    libros = _LibrosFalso()
    libros.libro = Libro(
        id=101,
        isbn="isbn-sin-actor",
        titulo="Sin actor",
        precio="10.00",
        stock=0,
        editorial_id=1,
    )
    uow = _UoWFalso(libros)

    with pytest.raises(HTTPException) as excinfo:
        await service.reponer(uow, 101, cantidad=2)

    assert excinfo.value.status_code == 409
    assert libros.movimientos == []
