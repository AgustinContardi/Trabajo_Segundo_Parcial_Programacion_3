"""Primitivas de autenticación que no bloquean el event loop."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import bcrypt
import jwt
from fastapi import Response
from pydantic import SecretStr

from app.core.errors import validar_password_bytes

JWT_ALGORITHM = "HS256"


def _secret_value(secret: str | SecretStr) -> str:
    return secret.get_secret_value() if isinstance(secret, SecretStr) else secret


def _hash_password_sync(password: bytes, rounds: int) -> bytes:
    return bcrypt.hashpw(password, bcrypt.gensalt(rounds=rounds))


def _verify_password_sync(password: bytes, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password, password_hash)
    except ValueError:
        # Un hash almacenado malformado no autentica y no debe filtrar detalles.
        return False


async def hash_password(
    password: str,
    *,
    rounds: int,
    semaphore: asyncio.Semaphore,
) -> str:
    """Calcula un hash bcrypt en un worker, bajo el semáforo compartido."""
    validar_password_bytes(password)
    password_bytes = password.encode("utf-8")
    async with semaphore:
        result = await asyncio.to_thread(_hash_password_sync, password_bytes, rounds)
    return result.decode("ascii")


async def verify_password(
    password: str,
    password_hash: str,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Verifica bcrypt fuera del event loop y bajo el semáforo compartido."""
    validar_password_bytes(password)
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("ascii")
    async with semaphore:
        return await asyncio.to_thread(
            _verify_password_sync, password_bytes, hash_bytes
        )


def create_access_token(
    subject: int | str,
    roles: Sequence[str],
    *,
    secret: str | SecretStr,
    ttl_seconds: int,
) -> str:
    """Firma un JWT con identidad, expiración y roles sólo informativos."""
    if ttl_seconds <= 0:
        raise ValueError("El TTL del token debe ser positivo")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "exp": now + timedelta(seconds=ttl_seconds),
        "roles": list(roles),
    }
    return jwt.encode(payload, _secret_value(secret), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str | SecretStr) -> dict[str, Any]:
    """Valida firma y expiración; `sub` y `exp` son claims obligatorios."""
    payload = jwt.decode(
        token,
        _secret_value(secret),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "exp"]},
    )
    return payload


def set_access_token_cookie(
    response: Response,
    token: str,
    *,
    max_age: int,
    secure: bool,
) -> None:
    """Transporta el JWT exclusivamente en la cookie HttpOnly de acceso."""
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def clear_access_token_cookie(response: Response, *, secure: bool) -> None:
    """Indica al cliente que elimine la cookie de acceso."""
    response.set_cookie(
        key="access_token",
        value="",
        max_age=0,
        expires=0,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
