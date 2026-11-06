"""Endpoint `POST /auth/registro` sobre `main.app` (C-12, 4.1/4.2).

Sin PostgreSQL y sin `Settings` reales: el UoW se reemplaza por el doble en
memoria (`registro_support`), `app.state` recibe un `settings` mínimo y el
lifespan no se ejecuta. Así se verifica el contrato HTTP completo —201, 422,
409, atomicidad y ausencia de `password_hash`— sin depender del entorno.

La verificación contra PostgreSQL real (`test_registro_api` con `api_client` y
`SELECT count(*)`) queda pendiente: no hay base disponible en este entorno.
"""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from tests.registro_support import MundoFalso, UoWFalso

pytestmark = pytest.mark.asyncio

EMAIL = "ana@example.com"
NOMBRE = "Ana Pérez"
PASSWORD = "clave-segura-123"


def _cuerpo(**extra: object) -> dict[str, object]:
    cuerpo: dict[str, object] = {
        "email": EMAIL,
        "nombre": NOMBRE,
        "password": PASSWORD,
    }
    cuerpo.update(extra)
    return cuerpo


@pytest.fixture
def mundo() -> MundoFalso:
    return MundoFalso()


@pytest_asyncio.fixture
async def api(mundo: MundoFalso):
    """Cliente ASGI con el UoW del registro reemplazado por el doble."""
    from main import app
    from app.modules.usuarios.unit_of_work import get_registro_uow

    uows: list[UoWFalso] = []

    def fabrica() -> UoWFalso:
        uow = UoWFalso(mundo)
        uows.append(uow)
        return uow

    app.dependency_overrides[get_registro_uow] = fabrica
    app.state.settings = SimpleNamespace(BCRYPT_ROUNDS=4)
    app.state.bcrypt_sem = asyncio.Semaphore(1)

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as cliente:
            yield SimpleNamespace(cliente=cliente, uows=uows)
    finally:
        app.dependency_overrides.pop(get_registro_uow, None)
        del app.state.settings
        del app.state.bcrypt_sem


async def test_registro_alta_valida_da_201_y_crea_las_tres_filas(
    api, mundo: MundoFalso
) -> None:
    respuesta = await api.cliente.post("/auth/registro", json=_cuerpo())

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 101,
        "email": EMAIL,
        "nombre": NOMBRE,
        "activo": True,
        "debe_cambiar_password": False,
    }
    assert "password_hash" not in respuesta.text
    assert PASSWORD not in respuesta.text
    assert "set-cookie" not in respuesta.headers

    assert len(mundo.usuarios) == 1
    assert len(mundo.asignaciones) == 1
    assert len(mundo.clientes) == 1

    usuario = mundo.usuarios[0]
    asignacion = mundo.asignaciones[0]
    ficha = mundo.clientes[0]

    assert asignacion.rol == "CLIENTE"
    assert asignacion.desde is not None
    assert asignacion.desde.tzinfo is not None
    assert asignacion.vence_en is None
    assert asignacion.revocada_en is None
    assert ficha.usuario_id == usuario.id
    assert (ficha.email, ficha.nombre) == (EMAIL, NOMBRE)
    assert usuario.password_hash.startswith("$2b$04$")
    assert usuario.password_hash != PASSWORD


async def test_registro_guarda_el_hash_bcrypt_no_la_contrasena(
    api, mundo: MundoFalso
) -> None:
    await api.cliente.post("/auth/registro", json=_cuerpo())

    cargado = mundo.usuarios[0]
    assert cargado.password_hash not in (PASSWORD, "")
    assert len(cargado.password_hash) >= 59


@pytest.mark.parametrize(
    "cuerpo",
    [
        _cuerpo(rol="ADMIN"),
        _cuerpo(activo=False),
        _cuerpo(password="a" * 73),
        _cuerpo(password="ñ" * 40),
    ],
    ids=["rol", "campo-extra", "73-bytes", "40-enes"],
)
async def test_registro_contrato_invalido_da_422_sin_escribir_nada(
    api, mundo: MundoFalso, cuerpo: dict[str, object]
) -> None:
    respuesta = await api.cliente.post("/auth/registro", json=cuerpo)

    assert respuesta.status_code == 422
    assert mundo.usuarios == []
    assert mundo.asignaciones == []
    assert mundo.clientes == []


async def test_registro_contrato_acepta_72_bytes(api, mundo: MundoFalso) -> None:
    respuesta = await api.cliente.post(
        "/auth/registro", json=_cuerpo(password="a" * 72)
    )

    assert respuesta.status_code == 201
    assert len(mundo.usuarios) == 1


async def test_registro_nul_da_422_y_no_500(api, mundo: MundoFalso) -> None:
    respuesta = await api.cliente.post(
        "/auth/registro", json=_cuerpo(email="ana\x00@example.com")
    )

    assert respuesta.status_code == 422
    assert mundo.usuarios == []


async def test_registro_json_malformado_da_422_y_no_500(
    api, mundo: MundoFalso
) -> None:
    respuesta = await api.cliente.post(
        "/auth/registro",
        content=b"{",
        headers={"content-type": "application/json"},
    )

    assert respuesta.status_code == 422
    assert mundo.usuarios == []


async def test_registro_usuario_duplicado_da_409_con_mensaje_propio(
    api, mundo: MundoFalso
) -> None:
    existente = mundo.sembrar_usuario(EMAIL)

    respuesta = await api.cliente.post("/auth/registro", json=_cuerpo())

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya existe un usuario con ese email"
    assert "uq_usuario_email" not in respuesta.text
    assert "duplicate key" not in respuesta.text
    assert mundo.usuarios == [existente]
    assert mundo.asignaciones == []
    assert mundo.clientes == []


async def test_registro_cliente_duplicado_da_409_y_no_se_apropia_de_la_ficha(
    api, mundo: MundoFalso
) -> None:
    ficha = mundo.sembrar_cliente(EMAIL, nombre="Ficha ajena")

    respuesta = await api.cliente.post("/auth/registro", json=_cuerpo())

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya existe un cliente con ese email"
    assert "uq_cliente_email" not in respuesta.text
    assert ficha.usuario_id is None
    assert (ficha.nombre, ficha.email) == ("Ficha ajena", EMAIL)
    assert mundo.usuarios == []
    assert mundo.asignaciones == []
    assert mundo.clientes == [ficha]


async def test_registro_atomicidad_no_deja_usuario_ni_rol_tras_el_409(
    api, mundo: MundoFalso
) -> None:
    mundo.sembrar_cliente(EMAIL)

    await api.cliente.post("/auth/registro", json=_cuerpo())

    assert len(mundo.usuarios) == 0
    assert len(mundo.asignaciones) == 0
    assert api.uows[-1].confirmado is False
    assert api.uows[-1].revertido is True


async def test_registro_es_una_ruta_publica_post_201(
    api,
) -> None:
    from main import app

    # FastAPI de este entorno envuelve los routers incluidos en `_IncludedRouter`
    # (no aplana `app.routes`); el esquema OpenAPI es la vista pública estable.
    operacion = app.openapi()["paths"]["/auth/registro"]["post"]

    assert "201" in operacion["responses"]
    respuesta = operacion["responses"]["201"]["content"]["application/json"]
    assert respuesta["schema"]["$ref"].endswith("/UsuarioRead")
    cuerpo = operacion["requestBody"]["content"]["application/json"]
    assert cuerpo["schema"]["$ref"].endswith("/UsuarioCreate")
    assert "security" not in operacion
