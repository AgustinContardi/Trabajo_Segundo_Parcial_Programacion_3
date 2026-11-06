"""Lógica de negocio del módulo `usuarios` — autenticación (C-11).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una sesión
asincrónica ni construye el UoW (CV-01). La única escritura que no comparte la
transacción de la petición es `intento_acceso` (DD-05).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.modules.usuarios.models import IntentoAcceso, Usuario
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork

_CREDENCIALES_INVALIDAS = "Credenciales inválidas"
_DEMASIADOS_INTENTOS = "Demasiados intentos de inicio de sesión"


@dataclass(frozen=True)
class ResultadoLogin:
    """Identidad autenticada y token emitido (nunca se serializa el token)."""

    usuario: Usuario
    token: str
    expira_en_segundos: int


def _hash_de_verificacion(usuario: Usuario | None, hash_ficticio: str | bytes) -> str:
    """Usa el hash real si la cuenta existe o el ficticio si no (RN-08)."""
    if usuario is not None:
        return usuario.password_hash
    if isinstance(hash_ficticio, bytes):
        return hash_ficticio.decode("ascii")
    return hash_ficticio


def _retry_after_ms(
    primer_fallo: datetime | None, ventana_segundos: int
) -> int:
    """Milisegundos hasta que el fallo más antiguo salga de la ventana.

    El contrato del proyecto expresa `Retry-After` como un entero decimal en
    milisegundos, sin convertir a segundos.
    """
    tope = max(1, ventana_segundos * 1000)
    if primer_fallo is None:
        return tope
    restante = (
        primer_fallo + timedelta(seconds=ventana_segundos) - datetime.now(timezone.utc)
    ).total_seconds()
    return max(1, min(tope, math.ceil(restante * 1000)))


async def registrar_intento_acceso(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    ip: str,
    exito: bool,
) -> None:
    """Registra un intento de login en su propia sesión y transacción.

    Qué hace distinto: abre una sesión nueva desde `sessionmaker` y confirma
    por sí misma, sin pasar por el Unit of Work de la petición.

    Por qué no puede compartir la transacción: el fallo que alimenta RN-07 es
    justamente el que la transacción del login revierte al responder 401; si se
    escribiera dentro del UoW, la evidencia desaparecería con el error.

    Costo: deja filas aunque la petición falle o el login reviente después
    (DD-05); se acepta porque esas filas son el insumo del límite de intentos.
    """
    async with sessionmaker() as session:
        # `cuando` se escribe explícitamente: el DEFAULT migrado de la tabla es
        # un literal congelado (defecto heredado) y RN-07 necesita la hora real
        # del intento. No requiere migración en C-11.
        session.add(
            IntentoAcceso(
                email=email,
                ip=ip,
                exito=exito,
                cuando=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def autenticar(
    uow: UsuariosUnitOfWork,
    *,
    email: str,
    password: str,
    ip: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    semaphore,
    hash_ficticio: str | bytes,
) -> ResultadoLogin:
    """Autentica credenciales con el orden límite → hash → intento → respuesta."""
    expira_en_segundos = settings.ACCESS_TOKEN_TTL_MIN * 60
    bloqueado = False
    retry_after_ms = 0
    usuario: Usuario | None = None
    roles: list[str] = []

    # Lectura de login en el UoW de la petición (no incluye la auditoría).
    async with uow:
        resumen = await uow.intentos.resumen_fallos(
            email, ip, settings.LOGIN_VENTANA_SEG
        )
        if resumen.cantidad >= settings.LOGIN_MAX_INTENTOS:
            bloqueado = True
            retry_after_ms = _retry_after_ms(
                resumen.primer_fallo, settings.LOGIN_VENTANA_SEG
            )
        else:
            usuario = await uow.usuarios.get_by_email(email)
            if usuario is not None:
                roles = await uow.usuarios.roles_vigentes(usuario.id)

    if bloqueado:
        # El intento limitado también se registra (AB-03 / flujo 2).
        await registrar_intento_acceso(
            sessionmaker, email=email, ip=ip, exito=False
        )
        raise HTTPException(
            status_code=429,
            detail=_DEMASIADOS_INTENTOS,
            headers={"Retry-After": str(retry_after_ms)},
        )

    hash_verificacion = _hash_de_verificacion(usuario, hash_ficticio)
    exito = False
    token: str | None = None
    try:
        coincide = await verify_password(password, hash_verificacion, semaphore)
        if coincide and usuario is not None and usuario.activo:
            token = create_access_token(
                usuario.id,
                roles,
                secret=settings.JWT_SECRET,
                ttl_seconds=expira_en_segundos,
            )
            exito = True
    finally:
        # Se confirma siempre, incluso si bcrypt o la emisión fallan.
        await registrar_intento_acceso(
            sessionmaker, email=email, ip=ip, exito=exito
        )

    if token is None or usuario is None:
        raise HTTPException(
            status_code=401, detail=_CREDENCIALES_INVALIDAS
        )

    return ResultadoLogin(
        usuario=usuario,
        token=token,
        expira_en_segundos=expira_en_segundos,
    )
