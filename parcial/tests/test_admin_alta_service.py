"""Servicio de alta de personal (C-15, tarea 4).

UoW y repositorios falsos en memoria. Verifica el orden (hash bcrypt **antes**
de abrir el UoW, luego una sola transacción con usuario → rol → evento), la
atomicidad y la traducción de `IntegrityError` a 409.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.usuarios import service
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario
from app.modules.usuarios.schemas import PersonalCreate

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


def error_de_unicidad(constraint: str) -> IntegrityError:
    original = Exception(f'duplicate key value violates unique constraint "{constraint}"')
    return IntegrityError("INSERT INTO tabla VALUES (...)", {}, original)


def _data(**campos) -> PersonalCreate:
    base = {
        "email": "Ana.Paz@Example.COM ",
        "nombre": "Ana Paz",
        "password": PASSWORD,
        "rol": "ADMIN",
    }
    base.update(campos)
    return PersonalCreate(**base)


def _admin(usuario_id: int = 1, email: str = "admin@example.com") -> SimpleNamespace:
    return SimpleNamespace(id=usuario_id, email=email, nombre="Admin")


def _settings(rounds: int = 4) -> SimpleNamespace:
    return SimpleNamespace(BCRYPT_ROUNDS=rounds)


def _semaphore() -> SimpleNamespace:
    return SimpleNamespace(nombre="semaforo-compartido")


class MundoFalso:
    def __init__(self) -> None:
        self.usuarios: list[Usuario] = []
        self.asignaciones: list[AsignacionRol] = []
        self.eventos: list = []
        self._siguiente_id = 100
        self._snapshot: tuple | None = None
        self.fallar_roles: str | None = None
        self.fallar_eventos: str | None = None

    def siguiente_id(self) -> int:
        self._siguiente_id += 1
        return self._siguiente_id

    def abrir_transaccion(self) -> None:
        self._snapshot = (
            list(self.usuarios),
            list(self.asignaciones),
            list(self.eventos),
        )

    def revertir(self) -> None:
        assert self._snapshot is not None
        self.usuarios = list(self._snapshot[0])
        self.asignaciones = list(self._snapshot[1])
        self.eventos = list(self._snapshot[2])


class _RepoUsuariosFalso:
    def __init__(self, mundo: MundoFalso, eventos: list) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, usuario: Usuario) -> Usuario:
        self._eventos.append("add:usuarios")
        if any(
            existente.email.lower() == usuario.email.lower()
            for existente in self._mundo.usuarios
        ):
            raise error_de_unicidad("uq_usuario_email")
        usuario.id = self._mundo.siguiente_id()
        self._mundo.usuarios.append(usuario)
        return usuario


class _RepoRolesFalso:
    def __init__(self, mundo: MundoFalso, eventos: list) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, asignacion: AsignacionRol) -> AsignacionRol:
        self._eventos.append("add:roles")
        if self._mundo.fallar_roles is not None:
            raise error_de_unicidad(self._mundo.fallar_roles)
        asignacion.id = self._mundo.siguiente_id()
        self._mundo.asignaciones.append(asignacion)
        return asignacion


class _RepoEventosFalso:
    def __init__(self, mundo: MundoFalso, eventos: list) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, evento) -> None:
        self._eventos.append("add:eventos")
        if self._mundo.fallar_eventos is not None:
            raise error_de_unicidad(self._mundo.fallar_eventos)
        self._mundo.eventos.append(evento)


class UoWFalso:
    def __init__(self, mundo: MundoFalso) -> None:
        self.mundo = mundo
        self.eventos_list = mundo.eventos  # marcadores ("enter"/"exit"/"hash") para asserts
        self.usuarios = _RepoUsuariosFalso(mundo, mundo.eventos)
        self.roles = _RepoRolesFalso(mundo, mundo.eventos)
        self.eventos = _RepoEventosFalso(mundo, mundo.eventos)  # uow.eventos.add(...)
        self.entradas = 0
        self.salidas: list = []
        self.confirmado = False
        self.revertido = False

    async def __aenter__(self) -> "UoWFalso":
        self.entradas += 1
        self.eventos_list.append("enter")
        self.mundo.abrir_transaccion()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.salidas.append(exc_type)
        self.eventos_list.append("exit")
        if exc_type is None:
            self.confirmado = True
        else:
            self.revertido = True
            self.mundo.revertir()
        return False

    @property
    def repositorios(self):
        return (self.usuarios, self.roles, self.eventos)


# --- tests ---


async def test_alta_personal_calcula_el_hash_antes_de_abrir_la_transaccion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        mundo.eventos.append("hash")
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    await service.alta_personal(
        uow, _data(), admin=_admin(), settings=_settings(), semaphore=_semaphore()
    )

    assert mundo.eventos.index("hash") < mundo.eventos.index("enter")


async def test_alta_personal_usa_las_rounds_y_el_semaforo_compartido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)
    semaforo = _semaphore()
    vistos: list = []

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        vistos.append((password, rounds, semaphore))
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    await service.alta_personal(
        uow, _data(), admin=_admin(), settings=_settings(rounds=7), semaphore=semaforo
    )

    assert vistos == [(PASSWORD, 7, semaforo)]


async def test_alta_personal_abre_un_solo_uow(monkeypatch: pytest.MonkeyPatch) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    await service.alta_personal(
        uow, _data(), admin=_admin(), settings=_settings(), semaphore=_semaphore()
    )

    assert uow.entradas == 1
    assert uow.salidas == [None]
    assert uow.confirmado is True


async def test_alta_personal_escribe_usuario_rol_y_evento_en_ese_orden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    await service.alta_personal(
        uow, _data(), admin=_admin(), settings=_settings(), semaphore=_semaphore()
    )

    escrituras = [e for e in mundo.eventos if isinstance(e, str) and e.startswith("add:")]
    assert escrituras == ["add:usuarios", "add:roles", "add:eventos"]


async def test_alta_personal_propaga_admin_como_otorgada_por_y_debe_cambiar_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    admin = _admin(usuario_id=42, email="jefa@example.com")
    usuario = await service.alta_personal(
        uow, _data(rol="VENDEDOR"), admin=admin, settings=_settings(), semaphore=_semaphore()
    )

    assert usuario.debe_cambiar_password is True
    assert mundo.asignaciones[0].otorgada_por == 42
    evento = [e for e in mundo.eventos if isinstance(e, EventoSeguridad)][-1]
    assert evento.actor == "jefa@example.com"
    assert "Alta de personal" in evento.accion


async def test_alta_personal_email_ya_existente_da_409_sin_filas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    existente = Usuario(
        email="ana.paz@example.com", nombre="Existente", password_hash="x",
    )
    existente.id = mundo.siguiente_id()
    mundo.usuarios.append(existente)
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    with pytest.raises(HTTPException) as excinfo:
        await service.alta_personal(
            uow, _data(), admin=_admin(), settings=_settings(), semaphore=_semaphore()
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "Ya existe un usuario con ese email"
    assert mundo.usuarios == [existente]
    assert mundo.asignaciones == []
    assert uow.confirmado is False
    assert uow.revertido is True


async def test_alta_personal_rol_invalido_da_422_antes_de_tocar_la_base():
    """Un rol fuera de ADMIN/VENDEDOR es rechazado por el schema (422)."""
    with pytest.raises(Exception):
        PersonalCreate(email="x@example.com", nombre="X", password=PASSWORD, rol="CLIENTE")


async def test_alta_personal_fallo_de_evento_revierte_usuario_y_rol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo = MundoFalso()
    mundo.fallar_eventos = "uq_asignacion_rol_abierta"
    uow = UoWFalso(mundo)

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    with pytest.raises(HTTPException):
        await service.alta_personal(
            uow, _data(), admin=_admin(), settings=_settings(), semaphore=_semaphore()
        )

    assert mundo.usuarios == []
    assert mundo.asignaciones == []
    assert uow.confirmado is False
    assert uow.revertido is True
