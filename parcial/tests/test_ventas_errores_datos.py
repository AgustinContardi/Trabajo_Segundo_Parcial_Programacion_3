"""Traducción de errores de datos en el borde (RN-15, CHECKLIST §8).

Un `DBAPIError` cuyo `orig` es un `DataError` de asyncpg (por ejemplo, un
entero fuera del rango `int64` que llega a la consulta) NO debe terminar en
500 ni filtrar el texto de PostgreSQL: el servicio lo traduce a 422 y el
handler global actúa como defensa en profundidad. Un `DBAPIError` que no es de
datos devuelve 500 genérico sin texto interno.

Pruebas puras con un UoW falso más una comprobación del registro del handler en
`main.app`; no requieren PostgreSQL.
"""

import json

import pytest
from asyncpg.exceptions import DataError as AsyncpgDataError
from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError

from app.core.dependencies import IdentidadActual
from app.modules.usuarios.models import Usuario
from app.modules.ventas import service
from app.modules.ventas.schemas import RenglonCreate, VentaCreate

pytestmark = pytest.mark.asyncio

TEXTOS_PROHIBIDOS = (
    "value out of",
    "int64",
    "int8",
    "bigint",
    "select ",
    "movimiento_stock",
    "_fkey",
    "_key",
    "postgres",
    "asyncpg",
    "sqlalchemy",
    "traceback",
    "violates",
)

MENSAJE_DATOS = "Los datos enviados no son válidos"
MENSAJE_INTERNO = "No se pudo completar la operación"


def _error_de_datos(mensaje: str = "value out of int64 range") -> DBAPIError:
    return DBAPIError("SELECT libro.id FROM libro", {}, AsyncpgDataError(mensaje))


def _error_no_de_datos() -> DBAPIError:
    return DBAPIError("SELECT 1", {}, RuntimeError("conexión caída: detalle interno"))


class _ClienteRepoFalla:
    async def get_by_id(self, id):
        raise _error_de_datos()


class _RepoVacio:
    async def add(self, entity):
        raise AssertionError("no debe escribirse nada")

    async def get_by_id(self, id):
        return None


class _UoWErrorDeDatos:
    def __init__(self):
        self.clientes = _ClienteRepoFalla()
        self.ventas = _RepoVacio()
        self.renglones = _RepoVacio()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commits += 1
        else:
            self.rollbacks += 1
        return False


def _actual() -> IdentidadActual:
    return IdentidadActual(
        usuario=Usuario(
            id=9, email="vendedor@example.com", nombre="V", password_hash="x"
        ),
        roles_db=("VENDEDOR",),
        roles_token=(),
    )


def _dto() -> VentaCreate:
    return VentaCreate(
        cliente_id=1,
        renglones=[RenglonCreate(libro_id=1, cantidad=1)],
    )


def _sin_textos_internos(texto: str) -> None:
    bajo = texto.lower()
    for prohibido in TEXTOS_PROHIBIDOS:
        assert prohibido not in bajo, f"el mensaje filtra {prohibido!r}: {texto!r}"


async def test_servicio_traduce_dbapierror_de_datos_a_422_sin_filtrar_postgres():
    uow = _UoWErrorDeDatos()

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar_venta(uow, _dto(), _actual())

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail == MENSAJE_DATOS
    _sin_textos_internos(str(excinfo.value.detail))
    assert uow.commits == 0
    assert uow.rollbacks == 1


async def test_traducir_error_de_datos_solo_traduce_dataerrors():
    from app.core.errors import es_error_de_datos, traducir_error_de_datos

    error = _error_de_datos()
    assert es_error_de_datos(error) is True
    traducida = traducir_error_de_datos(error)
    assert isinstance(traducida, HTTPException)
    assert traducida.status_code == 422
    assert traducida.detail == MENSAJE_DATOS

    no_datos = _error_no_de_datos()
    assert es_error_de_datos(no_datos) is False
    with pytest.raises(DBAPIError):
        traducir_error_de_datos(no_datos)


async def test_handler_global_traduce_dataerror_a_422_y_el_resto_a_500_generico():
    from app.core.errors import manejador_dbapi_error

    response = await manejador_dbapi_error(None, _error_de_datos())
    assert response.status_code == 422
    cuerpo = json.loads(response.body)
    assert cuerpo == {"detail": MENSAJE_DATOS}
    _sin_textos_internos(response.body.decode())

    response = await manejador_dbapi_error(None, _error_no_de_datos())
    assert response.status_code == 500
    cuerpo = json.loads(response.body)
    assert cuerpo == {"detail": MENSAJE_INTERNO}
    _sin_textos_internos(response.body.decode())


async def test_handler_traduce_tambien_dataerror_de_sqlalchemy_y_conserva_integrity():
    from sqlalchemy.exc import DataError as SqlAlchemyDataError

    from app.core.errors import manejador_dbapi_error

    response = await manejador_dbapi_error(
        None, SqlAlchemyDataError("INSERT", {}, Exception("valor fuera de rango"))
    )
    assert response.status_code == 422
    assert json.loads(response.body) == {"detail": MENSAJE_DATOS}

    from sqlalchemy.exc import IntegrityError

    response = await manejador_dbapi_error(
        None,
        IntegrityError("INSERT", {}, Exception('viola "venta_cliente_id_fkey"')),
    )
    assert response.status_code == 409
    assert json.loads(response.body) == {"detail": "El cliente indicado no existe"}
    _sin_textos_internos(response.body.decode())


async def test_servicio_relanza_dbapierror_no_de_datos_tras_el_rollback():
    class _ClienteRepoFallaNoDatos:
        async def get_by_id(self, id):
            raise _error_no_de_datos()

    uow = _UoWErrorDeDatos()
    uow.clientes = _ClienteRepoFallaNoDatos()

    with pytest.raises(DBAPIError) as excinfo:
        await service.registrar_venta(uow, _dto(), _actual())

    assert isinstance(excinfo.value.orig, RuntimeError)
    assert uow.commits == 0
    assert uow.rollbacks == 1


async def test_main_registra_el_handler_de_dbapierror():
    from main import app

    assert DBAPIError in app.exception_handlers


async def test_integrity_error_conserva_su_traduccion_409_y_422():
    from sqlalchemy.exc import IntegrityError

    from app.core.errors import traducir_integrity_error

    fk = IntegrityError(
        "insert", {}, Exception('viola "venta_cliente_id_fkey"')
    )
    assert traducir_integrity_error(fk).status_code == 409

    check = IntegrityError(
        "insert", {}, Exception('viola "ck_renglon_venta_cantidad_positiva"')
    )
    assert traducir_integrity_error(check).status_code == 422
