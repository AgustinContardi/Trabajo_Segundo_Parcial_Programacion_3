"""Dependencias de identidad y autorización de la petición (C-11 y C-13).

- `get_usuario_actual` autentica, no autoriza: lee exclusivamente la cookie
  `access_token`, valida firma y `exp` y resuelve un usuario existente y activo.
  No consulta `asignacion_rol`, no emite 403 y no acepta el encabezado Bearer.
- `get_sesion_actual` parte de la misma autenticación y agrega los roles
  vigentes leídos de la base en esta petición, además del claim informativo del
  token (`RN-04`).
- `requiere_rol(*roles)` compara únicamente contra los roles de la base y
  responde 403 genérico cuando no hay intersección.
"""

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_access_token
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import UsuarioRepository

_NO_AUTENTICADO = "No autenticado"
_NO_AUTORIZADO = "No autorizado"


@dataclass(frozen=True)
class IdentidadActual:
    """Identidad autenticada con roles de base (autorizan) y de token (informan)."""

    usuario: Usuario
    roles_db: tuple[str, ...]
    roles_token: tuple[str, ...]


def _no_autenticado() -> HTTPException:
    """401 genérico, sin detalles criptográficos ni datos de la cuenta."""
    return HTTPException(status_code=401, detail=_NO_AUTENTICADO)


def _normalizar_roles(roles: Any) -> tuple[str, ...]:
    """Normaliza a mayúsculas, sin duplicados y con orden estable.

    Un claim `roles` malformado es informativo y no debe romper la petición:
    si no es una lista de strings se ignora, porque nunca autoriza (`RN-04`).
    """
    if roles is None:
        return ()
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, (list, tuple, set, frozenset)):
        return ()
    return tuple(
        sorted({str(rol).strip().upper() for rol in roles if str(rol).strip()})
    )


async def _autenticar(
    request: Request, session: AsyncSession
) -> tuple[Usuario, tuple[str, ...]]:
    """Valida la cookie y devuelve el usuario activo más el claim `roles`.

    Es el único lugar que decodifica el JWT en una petición: `get_usuario_actual`
    y `get_sesion_actual` comparten este helper, así que un endpoint no debe
    depender de ambas a la vez.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise _no_autenticado()

    settings = request.app.state.settings
    try:
        payload = decode_access_token(token, secret=settings.JWT_SECRET)
        usuario_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise _no_autenticado() from None

    usuario = await UsuarioRepository(session).get_by_id(usuario_id)
    if usuario is None or not usuario.activo:
        raise _no_autenticado()

    return usuario, _normalizar_roles(payload.get("roles"))


async def get_usuario_actual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    """Resuelve la identidad activa a partir de la cookie de acceso."""
    usuario, _ = await _autenticar(request, session)
    return usuario


async def get_sesion_actual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> IdentidadActual:
    """Resuelve la identidad activa y los roles vigentes de la base."""
    usuario, roles_token = await _autenticar(request, session)
    roles_db = tuple(await UsuarioRepository(session).roles_vigentes(usuario.id))
    return IdentidadActual(
        usuario=usuario,
        roles_db=roles_db,
        roles_token=roles_token,
    )


def requiere_rol(*roles: str):
    """Fábrica de dependencia que exige alguno de los roles vigentes.

    Los roles se normalizan a mayúsculas al construir la ruta. Una lista vacía
    falla en construcción para que un error de cableado no deje la ruta abierta.
    La decisión usa exclusivamente `roles_db`; el claim `roles` del token nunca
    autoriza (`RN-04`).
    """
    exigidos = frozenset(_normalizar_roles(roles))
    if not exigidos:
        raise ValueError("requiere_rol necesita al menos un rol")

    async def dependencia(
        sesion: IdentidadActual = Depends(get_sesion_actual),
    ) -> IdentidadActual:
        vigentes = {str(rol).strip().upper() for rol in sesion.roles_db}
        if not (exigidos & vigentes):
            raise HTTPException(status_code=403, detail=_NO_AUTORIZADO)
        return sesion

    return dependencia


async def control_cambio_password(
    usuario: Usuario = Depends(get_usuario_actual),
) -> Usuario:
    """Puerta de cambio obligatorio: si `debe_cambiar_password = true` responde
    403; si es false, devuelve el usuario para que el router lo use.

    Se monta **una sola vez** a nivel del router protegido. El orden de
    resolución es: 401 (get_usuario_actual) → 403 (cambio pendiente) → 403
    (requiere_rol) → negocio.
    """
    if usuario.debe_cambiar_password:
        raise HTTPException(status_code=403, detail=_NO_AUTORIZADO)
    return usuario
