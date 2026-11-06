"""Servicio cambiar_password con UoW falso — sin PostgreSQL (C-14)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.usuarios import service
from app.modules.usuarios.models import EventoSeguridad, Usuario

pytestmark = pytest.mark.asyncio

PASSWORD_ACTUAL = "clave-actual-123"
PASSWORD_NUEVA = "clave-nueva-abc"
EMAIL = "usuario@example.com"


class _FakeUsuarioRepo:
    def __init__(self, usuario: Usuario | None) -> None:
        self.usuario = usuario

    async def get_by_email(self, email: str) -> Usuario | None:
        return self.usuario


class _FakeEventoRepo:
    def __init__(self) -> None:
        self.added: EventoSeguridad | None = None

    async def add(self, evento: EventoSeguridad) -> None:
        self.added = evento


class _FakeUoW:
    def __init__(self, usuario: Usuario | None) -> None:
        self.usuarios = _FakeUsuarioRepo(usuario)
        self.eventos = _FakeEventoRepo()
        self.enter_count = 0
        self.committed_count = 0

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed_count += 1
        return False


async def _usuario() -> Usuario:
    return Usuario(
        id=1,
        email=EMAIL,
        nombre="Usuario de prueba",
        password_hash="hash-viejo",
        activo=True,
        debe_cambiar_password=True,
    )


async def test_cambio_exitoso_escribe_tres_cosas_en_un_solo_uow(monkeypatch: pytest.MonkeyPatch):
    """Éxito: verifica actual, hashea nueva fuera del UoW, escribe 3 filas en una transacción."""
    usuario = await _usuario()
    uow = _FakeUoW(usuario)

    async def fake_verify(password: str, password_hash: str, semaphore) -> bool:
        assert password == PASSWORD_ACTUAL
        assert password_hash == "hash-viejo"
        return True

    async def fake_hash(
        password: str, *, rounds: int, semaphore
    ) -> str:
        assert password == PASSWORD_NUEVA
        return "hash-nuevo-falso"

    monkeypatch.setattr(service, "verify_password", fake_verify)
    monkeypatch.setattr(service, "hash_password", fake_hash)

    await service.cambiar_password(
        uow,
        email=EMAIL,
        password_actual=PASSWORD_ACTUAL,
        password_nueva=PASSWORD_NUEVA,
        settings=SimpleNamespace(BCRYPT_ROUNDS=12),
        semaphore=SimpleNamespace(),
    )

    # Dos aperturas de UoW: lectura + escritura, ambas confirmadas.
    assert uow.enter_count == 2
    assert uow.committed_count == 2

    # El hash nuevo y la bandera se escribieron en el usuario.
    assert usuario.password_hash == "hash-nuevo-falso"
    assert usuario.debe_cambiar_password is False

    # Evento de seguridad con actor = email, en la misma transacción.
    assert uow.eventos.added is not None
    assert uow.eventos.added.actor == EMAIL
    assert uow.eventos.added.accion == "Cambio de contraseña"


async def test_clave_actual_incorrecta_da_401_sin_escribir_nada(
    monkeypatch: pytest.MonkeyPatch,
):
    """Contraseña actual incorrecta -> 401, no escribe intento_acceso ni evento."""
    usuario = await _usuario()
    uow = _FakeUoW(usuario)

    async def fake_verify(password: str, password_hash: str, semaphore) -> bool:
        return False

    monkeypatch.setattr(service, "verify_password", fake_verify)
    # hash_password no debe llamarse si la actual es incorrecta.
    hash_llamado = False

    async def fake_hash(password: str, *, rounds: int, semaphore) -> str:
        nonlocal hash_llamado
        hash_llamado = True
        return "hash-nunca-deberia-usarse"

    monkeypatch.setattr(service, "hash_password", fake_hash)

    with pytest.raises(HTTPException) as excinfo:
        await service.cambiar_password(
            uow,
            email=EMAIL,
            password_actual="clave-mala",
            password_nueva=PASSWORD_NUEVA,
            settings=SimpleNamespace(BCRYPT_ROUNDS=12),
            semaphore=SimpleNamespace(),
        )

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Credenciales inválidas"

    # Solo se abrió el UoW de lectura; nunca se entró al de escritura.
    assert uow.enter_count == 1
    assert uow.committed_count == 1
    assert uow.eventos.added is None
    assert not hash_llamado


async def test_usuario_inexistente_da_401(monkeypatch: pytest.MonkeyPatch):
    """Email sin usuario -> 401 sin tocar bcrypt."""
    uow = _FakeUoW(usuario=None)

    verify_llamado = False

    async def fake_verify(password: str, password_hash: str, semaphore) -> bool:
        nonlocal verify_llamado
        verify_llamado = True
        return True

    monkeypatch.setattr(service, "verify_password", fake_verify)

    with pytest.raises(HTTPException) as excinfo:
        await service.cambiar_password(
            uow,
            email=EMAIL,
            password_actual=PASSWORD_ACTUAL,
            password_nueva=PASSWORD_NUEVA,
            settings=SimpleNamespace(BCRYPT_ROUNDS=12),
            semaphore=SimpleNamespace(),
        )

    assert excinfo.value.status_code == 401
    assert not verify_llamado
    assert uow.enter_count == 1
    assert uow.committed_count == 1
