"""Traducción de errores y validación transversal (C-05).

Contrato de este módulo:
- `CONSTRAINTS`: diccionario `nombre de constraint -> (status_code, mensaje)` con
  las unicidades, FKs y CHECKs existentes. Se extiende en cada change posterior.
- `traducir_integrity_error(exc)`: convierte un `IntegrityError` en una
  `HTTPException` con código y mensaje propio. Si el constraint es desconocido,
  devuelve 409 genérico **sin** texto de PostgreSQL (RN-15).
- `manejador_request_validation_error`: handler de `RequestValidationError` que
  responde 422 con cuerpo estable y nunca propaga la excepción.
- `SinNulMixin`: rechaza strings con carácter NUL en cualquier schema.

Convención de mensajes (RD-03): español, segunda persona, sin jerga de base.
Ningún mensaje contiene nombres de tablas, columnas ni constraints.
"""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import model_validator
from sqlalchemy.exc import IntegrityError


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


async def manejador_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler global de `RequestValidationError`: 422 estable, nunca propaga."""
    detail: list[dict[str, Any]] = []
    for err in exc.errors():
        detail.append(
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg"),
                "type": err.get("type"),
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
