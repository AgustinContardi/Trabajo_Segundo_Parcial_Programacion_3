"""Traducción de errores y validación transversal (C-05).

Contrato de este módulo:
- `CONSTRAINTS`: diccionario `nombre de constraint -> (status_code, mensaje)` con
  las unicidades, FKs y CHECKs existentes. Se extiende en cada change posterior.
- `traducir_integrity_error(exc)`: convierte un `IntegrityError` en una
  `HTTPException` con código y mensaje propio. Si el constraint es desconocido,
  devuelve 409 genérico **sin** texto de PostgreSQL (RN-15).
- `es_error_de_datos(exc)` / `traducir_error_de_datos(exc)`: reconocen un
  `DataError` de SQLAlchemy o de asyncpg y lo traducen a 422 genérico en
  español; cualquier otro error se re-lanza (RN-15).
- `manejador_dbapi_error`: handler global de `DBAPIError`; `IntegrityError`
  conserva su traducción a 409/422, un error de datos responde 422 y el resto
  500 genérico sin texto interno.
- `manejador_request_validation_error`: handler de `RequestValidationError` que
  responde 422 con cuerpo estable, `loc`/`type` y mensaje propio en español.
- `SinNulMixin`: rechaza strings con carácter NUL en cualquier schema.

Convención de mensajes (RD-03): español, segunda persona, sin jerga de base.
Ningún mensaje contiene nombres de tablas, columnas ni constraints.
"""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import model_validator
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError

try:  # asyncpg es el driver real; el import defensivo no cambia el contrato.
    from asyncpg.exceptions import DataError as AsyncpgDataError
except ImportError:  # pragma: no cover - asyncpg siempre está instalado

    class AsyncpgDataError(Exception):  # type: ignore[no-redef]
        """Centinela para entornos sin asyncpg."""


# (status_code, mensaje propio). El texto nunca es el de PostgreSQL (RN-15).
CONSTRAINTS: dict[str, tuple[int, str]] = {
    # --- unicidades ---
    "uq_cliente_email": (409, "Ya existe un cliente con ese email"),
    "uq_cliente_usuario_id": (409, "Ese usuario ya está vinculado a un cliente"),
    "uq_perfil_cliente_cliente_id": (409, "El cliente ya tiene perfil"),
    "uq_usuario_email": (409, "Ya existe un usuario con ese email"),
    "uq_asignacion_rol_abierta": (409, "El usuario ya tiene una asignación abierta de ese rol"),
    "editorial_nombre_key": (409, "Ya existe una editorial con ese nombre"),
    "genero_nombre_key": (409, "Ya existe un género con ese nombre"),
    "uq_libro_isbn_vigente": (409, "Ya existe un libro con ese ISBN"),
    # PK compuesta de libro_autor
    "libro_autor_pkey": (409, "El autor ya está asignado a este libro"),
    # --- claves foráneas ---
    "libro_editorial_id_fkey": (409, "La editorial indicada no existe"),
    "libro_genero_id_fkey": (409, "El género indicado no existe"),
    "fk_libro_genero": (409, "El género indicado no existe"),
    "venta_cliente_id_fkey": (409, "El cliente indicado no existe"),
    "renglon_venta_venta_id_fkey": (409, "La venta indicada no existe"),
    "renglon_venta_libro_id_fkey": (409, "El libro indicado no existe"),
    "libro_autor_libro_id_fkey": (409, "El libro indicado no existe"),
    "libro_autor_autor_id_fkey": (409, "El autor indicado no existe"),
    "movimiento_stock_libro_id_fkey": (409, "El libro indicado no existe"),
    "movimiento_stock_usuario_id_fkey": (409, "El usuario indicado no existe"),
    "movimiento_stock_venta_id_fkey": (409, "La venta indicada no existe"),
    "asignacion_rol_usuario_id_fkey": (409, "El usuario indicado no existe"),
    "asignacion_rol_otorgada_por_fkey": (409, "El usuario que otorga no existe"),
    "cliente_usuario_id_fkey": (409, "El usuario indicado no existe"),
    "perfil_cliente_cliente_id_fkey": (409, "El cliente indicado no existe"),
    # --- CHECKs ---
    "ck_libro_precio_positivo": (422, "El precio debe ser mayor que cero"),
    "ck_libro_stock_no_negativo": (422, "El stock no puede ser negativo"),
    "ck_libro_autor_rol": (422, "El rol del autor no es válido"),
    "ck_libro_autor_orden": (422, "El orden debe ser mayor o igual a 1"),
    "ck_movimiento_stock_cantidad_no_cero": (422, "La cantidad no puede ser cero"),
    "ck_venta_total_no_negativo": (422, "El total no puede ser negativo"),
    "ck_renglon_venta_cantidad_positiva": (422, "La cantidad debe ser mayor que cero"),
    "ck_renglon_venta_precio_unitario_positivo": (422, "El precio unitario debe ser mayor que cero"),
    "ck_asignacion_rol_rol": (422, "El rol no es válido"),
}


def _nombre_constraint(exc: IntegrityError) -> str | None:
    """Extrae el nombre del constraint del error de base, sin exponer su texto."""
    # Recorrer la cadena de wrappers (SQLAlchemy -> dbapi -> asyncpg).
    current: Any = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = getattr(current, "constraint_name", None)
        if name:
            return str(name)
        diag = getattr(current, "diag", None)
        if diag is not None:
            name = getattr(diag, "constraint_name", None)
            if name:
                return str(name)
        # asyncpg guarda el nombre en el mensaje; no lo parseamos al cliente,
        # pero sí podemos extraer el identificador entre comillas para mapearlo.
        current = getattr(current, "orig", None)
    # Último recurso: extraer el identificador entre comillas del mensaje,
    # que es el nombre del constraint (no texto de datos).
    for arg in getattr(exc, "args", ()) or ():
        if isinstance(arg, str):
            # buscar un token entre comillas simples que parezca nombre de constraint
            import re

            for match in re.findall(r"«([^»]+)»|'([^']+)'|\"([^\"]+)\"", arg):
                candidate = next((g for g in match if g), None)
                if candidate and candidate in CONSTRAINTS:
                    return candidate
    return None


MENSAJE_DATOS_INVALIDOS = "Los datos enviados no son válidos"
MENSAJE_ERROR_INTERNO = "No se pudo completar la operación"


def es_error_de_datos(exc: BaseException) -> bool:
    """`True` si el error viene de un dato inválido (no de un bug del servidor).

    Cubre `DataError` de SQLAlchemy y el `DataError` de asyncpg que SQLAlchemy
    envuelve como `orig`; ambos indican que el dato no cabe o no es convertible
    en PostgreSQL, no una falla interna (RN-15).
    """
    if isinstance(exc, (DataError, AsyncpgDataError)):
        return True
    orig = getattr(exc, "orig", None)
    return isinstance(orig, (DataError, AsyncpgDataError))


def traducir_error_de_datos(exc: BaseException) -> HTTPException:
    """Traduce un error de datos a 422 genérico en español, sin texto de base.

    Si el error no es de datos, se re-lanza para que el handler global responda
    500 genérico; nunca se filtra al cliente el texto de PostgreSQL (RN-15).
    """
    if not es_error_de_datos(exc):
        raise exc
    return HTTPException(status_code=422, detail=MENSAJE_DATOS_INVALIDOS)


def traducir_integrity_error(exc: IntegrityError) -> HTTPException:
    """Traduce un `IntegrityError` a `HTTPException` con código y mensaje propios.

    Si el constraint es desconocido (o no se pudo extraer), devuelve 409 genérico
    sin texto de PostgreSQL (RN-15).
    """
    name = _nombre_constraint(exc)
    if name is not None and name in CONSTRAINTS:
        status_code, mensaje = CONSTRAINTS[name]
        return HTTPException(status_code=status_code, detail=mensaje)
    return HTTPException(
        status_code=409,
        detail="No se pudo completar la operación por un conflicto de datos",
    )


# Mensajes propios por tipo de error de Pydantic (RD-03, RN-15). Ninguno
# repite el texto de Pydantic ni el de PostgreSQL.
MENSAJE_VALIDACION_GENERICO = "Los datos enviados no son válidos"
MENSAJES_POR_TIPO: dict[str, str] = {
    "missing": "Falta un campo obligatorio",
    "extra_forbidden": "El campo no está permitido",
    "int_parsing": "Debe ser un número entero válido",
    "int_type": "Debe ser un número entero válido",
    "int_from_float": "Debe ser un número entero válido",
    "bool_type": "Debe ser un valor booleano válido",
    "float_type": "Debe ser un número válido",
    "decimal_parsing": "Debe ser un número válido",
    "greater_than": "El valor debe ser mayor que el mínimo permitido",
    "greater_than_equal": "El valor debe ser mayor que el mínimo permitido",
    "less_than_equal": "El valor supera el máximo permitido",
    "too_short": "La lista no puede estar vacía",
}


def mensaje_validacion(tipo: str | None) -> str:
    """Devuelve el mensaje propio en español para un tipo de error de Pydantic."""
    return MENSAJES_POR_TIPO.get(str(tipo), MENSAJE_VALIDACION_GENERICO)


async def manejador_dbapi_error(request: Request, exc: DBAPIError) -> JSONResponse:
    """Handler global de `DBAPIError`: traduce datos inválidos, oculta el resto.

    `IntegrityError` es subclase de `DBAPIError`; se evalúa primero para
    conservar su traducción a 409/422. Un `DataError` (SQLAlchemy o asyncpg)
    responde 422 con mensaje propio; cualquier otro error de base responde 500
    genérico sin texto de PostgreSQL (RN-15).
    """
    if isinstance(exc, IntegrityError):
        http = traducir_integrity_error(exc)
        return JSONResponse(
            status_code=http.status_code, content={"detail": http.detail}
        )
    if es_error_de_datos(exc):
        return JSONResponse(
            status_code=422, content={"detail": MENSAJE_DATOS_INVALIDOS}
        )
    return JSONResponse(
        status_code=500, content={"detail": MENSAJE_ERROR_INTERNO}
    )


async def manejador_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler global de `RequestValidationError`: 422 estable, nunca propaga.

    Conserva `loc` y `type` (contrato usado por los tests) y reemplaza `msg`
    por un mensaje propio en español (RD-03).
    """
    detail: list[dict[str, Any]] = []
    for err in exc.errors():
        tipo = err.get("type")
        detail.append(
            {
                "loc": list(err.get("loc", ())),
                "msg": mensaje_validacion(tipo),
                "type": tipo,
            }
        )
    return JSONResponse(status_code=422, content={"detail": detail})


class SinNulMixin:
    """Mixin que rechaza strings con carácter NUL en cualquier schema."""

    @model_validator(mode="before")
    @classmethod
    def _rechazar_nul(cls, data: Any) -> Any:
        def _check(obj: Any) -> None:
            if isinstance(obj, str):
                if "\x00" in obj:
                    raise ValueError("El texto no puede contener el carácter nulo")
            elif isinstance(obj, dict):
                for value in obj.values():
                    _check(value)
            elif isinstance(obj, list):
                for value in obj:
                    _check(value)
            elif isinstance(obj, tuple):
                for value in obj:
                    _check(value)

        _check(data)
        return data


def validar_password_bytes(value: str | None) -> str | None:
    """Valida que la contraseña no supere los 72 bytes (límite de bcrypt)."""
    if value is not None and len(value.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar los 72 bytes")
    return value
