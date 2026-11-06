"""Servicio atómico del auto-registro (C-12, 3.1/3.3).

Sin base ni `Settings` reales: UoW, repositorios y `hash_password` son dobles.
Se verifica el orden (hash → una sola transacción → usuario → rol → ficha), la
propagación de `usuario_id`, la traducción de `IntegrityError` y que cualquier
fallo revierte las tres escrituras.
"""

from datetime import timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.usuarios import service
from app.modules.usuarios.schemas import UsuarioCreate
from tests.registro_support import MundoFalso, UoWFalso

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


def _data(email: str = "ana@example.com") -> UsuarioCreate:
    return UsuarioCreate(
        email=email,
        nombre="Ana Pérez",
        password=PASSWORD,
    )


def _settings(rounds: int = 4) -> SimpleNamespace:
    return SimpleNamespace(BCRYPT_ROUNDS=rounds)


@pytest.fixture
def semaforo() -> SimpleNamespace:
    """Centinela: el servicio debe reenviar el semáforo compartido tal cual."""
    return SimpleNamespace(nombre="semaforo-compartido")


@pytest.fixture
def hash_espia(monkeypatch: pytest.MonkeyPatch, semaforo: SimpleNamespace):
    """Sustituye bcrypt por un doble que registra cada cálculo."""
    vistos: list[tuple[str, int, object]] = []

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        vistos.append((password, rounds, semaphore))
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)
    return vistos


async def test_registrar_calcula_el_hash_antes_de_abrir_la_transaccion(
    monkeypatch: pytest.MonkeyPatch, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)
    eventos = uow.eventos

    async def falso(password: str, *, rounds: int, semaphore) -> str:
        eventos.append("hash")
        return "$2b$04$hash-de-prueba"

    monkeypatch.setattr(service, "hash_password", falso)

    await service.registrar(uow, _data(), settings=_settings(), semaphore=semaforo)

    assert eventos.index("hash") < eventos.index("enter")


async def test_registrar_usa_las_rounds_y_el_semaforo_configurados(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    await service.registrar(
        uow, _data(), settings=_settings(rounds=7), semaphore=semaforo
    )

    assert hash_espia == [(PASSWORD, 7, semaforo)]


async def test_registrar_abre_un_solo_uow(hash_espia, semaforo: SimpleNamespace) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    await service.registrar(uow, _data(), settings=_settings(), semaphore=semaforo)

    assert uow.entradas == 1
    assert uow.salidas == [None]


async def test_registrar_escribe_usuario_rol_y_ficha_en_ese_orden(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    await service.registrar(uow, _data(), settings=_settings(), semaphore=semaforo)

    escrituras = [evento for evento in uow.eventos if evento.startswith("add:")]
    assert escrituras == ["add:usuarios", "add:roles", "add:clientes"]


async def test_registrar_propaga_el_usuario_id_al_rol_y_a_la_ficha(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    usuario = await service.registrar(
        uow, _data(), settings=_settings(), semaphore=semaforo
    )

    assert usuario.id is not None
    assert mundo.asignaciones[0].usuario_id == usuario.id
    assert mundo.clientes[0].usuario_id == usuario.id


async def test_registrar_crea_el_rol_cliente_vigente_y_sin_revocar(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    await service.registrar(uow, _data(), settings=_settings(), semaphore=semaforo)

    asignacion = mundo.asignaciones[0]
    assert asignacion.rol == "CLIENTE"
    assert asignacion.desde is not None
    assert asignacion.desde.tzinfo is timezone.utc
    assert asignacion.vence_en is None
    assert asignacion.revocada_en is None


async def test_registrar_devuelve_el_usuario_con_el_hash_y_el_email_normalizado(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    usuario = await service.registrar(
        uow,
        _data("  Ana@Example.COM "),
        settings=_settings(),
        semaphore=semaforo,
    )

    assert usuario.email == "ana@example.com"
    assert usuario.nombre == "Ana Pérez"
    assert usuario.password_hash == "$2b$04$hash-de-prueba"
    assert PASSWORD not in (usuario.password_hash or "")


async def test_registrar_email_ya_usado_por_un_usuario_da_409_sin_filas(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    existente = mundo.sembrar_usuario("ana@example.com")
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar(
            uow, _data(), settings=_settings(), semaphore=semaforo
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "Ya existe un usuario con ese email"
    assert mundo.usuarios == [existente]
    assert mundo.asignaciones == []
    assert mundo.clientes == []
    assert uow.confirmado is False
    assert uow.revertido is True


async def test_registrar_email_ya_usado_por_un_cliente_da_409_sin_apropiarse(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    ficha = mundo.sembrar_cliente("ana@example.com", nombre="Ficha ajena")
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar(
            uow, _data(), settings=_settings(), semaphore=semaforo
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "Ya existe un cliente con ese email"
    assert ficha.usuario_id is None
    assert (ficha.nombre, ficha.email) == ("Ficha ajena", "ana@example.com")
    assert mundo.usuarios == []
    assert mundo.asignaciones == []
    assert len(mundo.clientes) == 1


async def test_registrar_fallo_de_rol_revierte_el_usuario_ya_escrito(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    mundo.fallar_roles = "uq_asignacion_rol_abierta"
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar(
            uow, _data(), settings=_settings(), semaphore=semaforo
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == (
        "El usuario ya tiene una asignación abierta de ese rol"
    )
    assert mundo.usuarios == []
    assert mundo.asignaciones == []
    assert mundo.clientes == []


async def test_registrar_el_integrity_error_sale_del_bloque_para_que_revierta(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    mundo.fallar_clientes = "uq_cliente_email"
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException):
        await service.registrar(
            uow, _data(), settings=_settings(), semaphore=semaforo
        )

    # El `__aexit__` recibe la excepción (no una salida normal): revierte.
    assert uow.salidas == [IntegrityError]
    assert uow.confirmado is False
    assert uow.revertido is True


async def test_registrar_no_confirma_en_los_repositorios(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    await service.registrar(uow, _data(), settings=_settings(), semaphore=semaforo)

    assert all(repositorio.commit_llamado is False for repositorio in uow.repositorios)


async def test_registrar_constraint_desconocido_da_409_sin_texto_interno(
    hash_espia, semaforo: SimpleNamespace
) -> None:
    mundo = MundoFalso()
    mundo.fallar_clientes = "constraint_interno_desconocido"
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.registrar(
            uow, _data(), settings=_settings(), semaphore=semaforo
        )

    assert excinfo.value.status_code == 409
    assert "constraint_interno_desconocido" not in str(excinfo.value.detail)
    assert "duplicate key" not in str(excinfo.value.detail)
