"""Servicio de autenticación: orden, anti-enumeración y token (C-11, 3.1/3.2)."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import decode_access_token
from app.modules.usuarios import service
from app.modules.usuarios.unit_of_work import UsuariosUnitOfWork
from tests.conftest import contar_intentos

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
IP = "203.0.113.60"


async def _autenticar(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    semaphore,
    hash_ficticio: str,
    *,
    email: str,
    password: str = PASSWORD,
    ip: str = IP,
):
    async with db_sessionmaker() as session:
        uow = UsuariosUnitOfWork(session)
        return await service.autenticar(
            uow,
            email=email,
            password=password,
            ip=ip,
            sessionmaker=db_sessionmaker,
            settings=settings,
            semaphore=semaphore,
            hash_ficticio=hash_ficticio,
        )


async def test_login_exitoso_emite_token_con_roles_vigentes_y_registra_exito(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(
        password=PASSWORD,
        roles=("VENDEDOR", "ADMIN"),
        debe_cambiar_password=True,
    )

    resultado = await _autenticar(
        db_sessionmaker,
        settings,
        bcrypt_sem,
        hash_ficticio,
        email=usuario.email,
    )

    payload = decode_access_token(resultado.token, secret=settings.JWT_SECRET)
    assert payload["sub"] == str(usuario.id)
    assert payload["roles"] == ["ADMIN", "VENDEDOR"]
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()
    assert resultado.expira_en_segundos == settings.ACCESS_TOKEN_TTL_MIN * 60
    assert resultado.usuario.debe_cambiar_password is True
    assert await contar_intentos(db_sessionmaker, usuario.email) == 1


async def test_email_inexistente_verifica_contra_el_hash_ficticio(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    email_desconocido_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vistos: list[str] = []
    original = service.verify_password

    async def espia(password: str, password_hash: str, semaphore) -> bool:
        vistos.append(password_hash)
        return await original(password, password_hash, semaphore)

    monkeypatch.setattr(service, "verify_password", espia)
    desconocido = email_desconocido_factory()

    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=desconocido,
        )

    assert excinfo.value.status_code == 401
    assert vistos == [hash_ficticio]


async def test_password_incorrecta_verifica_contra_el_hash_real_y_da_401(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    monkeypatch: pytest.MonkeyPatch,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(password=PASSWORD)
    vistos: list[str] = []
    original = service.verify_password

    async def espia(password: str, password_hash: str, semaphore) -> bool:
        vistos.append(password_hash)
        return await original(password, password_hash, semaphore)

    monkeypatch.setattr(service, "verify_password", espia)

    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=usuario.email,
            password="otra-clave",
        )

    assert excinfo.value.status_code == 401
    assert vistos == [usuario.password_hash]


async def test_usuario_inactivo_da_401_sin_emitir_token(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(password=PASSWORD, activo=False)

    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=usuario.email,
        )

    assert excinfo.value.status_code == 401
    assert "access_token" not in str(excinfo.value.detail)


async def test_cuerpo_401_es_identico_para_las_tres_causas(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    email_desconocido_factory,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(password=PASSWORD)
    inactivo = await usuario_factory(password=PASSWORD, activo=False)
    desconocido = email_desconocido_factory()

    detalles: list[str] = []
    for email, password in (
        (usuario.email, "clave-mala"),
        (desconocido, PASSWORD),
        (inactivo.email, PASSWORD),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await _autenticar(
                db_sessionmaker,
                settings,
                bcrypt_sem,
                hash_ficticio,
                email=email,
                password=password,
            )
        assert excinfo.value.status_code == 401
        detalles.append(str(excinfo.value.detail))

    assert len(set(detalles)) == 1


async def test_sexto_intento_responde_429_antes_de_bcrypt_y_queda_registrado(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    monkeypatch: pytest.MonkeyPatch,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(password=PASSWORD)

    for _ in range(5):
        with pytest.raises(HTTPException) as excinfo:
            await _autenticar(
                db_sessionmaker,
                settings,
                bcrypt_sem,
                hash_ficticio,
                email=usuario.email,
                password="clave-mala",
            )
        assert excinfo.value.status_code == 401

    llamadas = 0

    async def prohibida(*args, **kwargs) -> bool:
        nonlocal llamadas
        llamadas += 1
        raise AssertionError("bcrypt no debe ejecutarse cuando ya hay 429")

    monkeypatch.setattr(service, "verify_password", prohibida)

    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=usuario.email,
            password=PASSWORD,
        )

    assert excinfo.value.status_code == 429
    retry_after = excinfo.value.headers["Retry-After"]
    assert retry_after.isdigit()
    assert int(retry_after) > 0
    assert llamadas == 0
    assert await contar_intentos(db_sessionmaker, usuario.email) == 6


async def test_login_exitoso_reinicia_el_conteo_de_fallos(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    bcrypt_sem,
    hash_ficticio: str,
    usuario_factory,
) -> None:
    usuario = await usuario_factory(password=PASSWORD)

    for _ in range(4):
        with pytest.raises(HTTPException):
            await _autenticar(
                db_sessionmaker,
                settings,
                bcrypt_sem,
                hash_ficticio,
                email=usuario.email,
                password="clave-mala",
            )

    await _autenticar(
        db_sessionmaker, settings, bcrypt_sem, hash_ficticio, email=usuario.email
    )

    for _ in range(4):
        with pytest.raises(HTTPException) as excinfo:
            await _autenticar(
                db_sessionmaker,
                settings,
                bcrypt_sem,
                hash_ficticio,
                email=usuario.email,
                password="clave-mala",
            )
        assert excinfo.value.status_code == 401

    # Quinto fallo posterior al éxito: todavía se procesa (401), no 429.
    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=usuario.email,
            password="clave-mala",
        )
    assert excinfo.value.status_code == 401

    # El siguiente ya alcanzó el umbral.
    with pytest.raises(HTTPException) as excinfo:
        await _autenticar(
            db_sessionmaker,
            settings,
            bcrypt_sem,
            hash_ficticio,
            email=usuario.email,
            password="clave-mala",
        )
    assert excinfo.value.status_code == 429

    assert await contar_intentos(db_sessionmaker, usuario.email) == 11
