"""Cierre de C-07: rutas de clientes exigen VENDEDOR o ADMIN (C-13, 2.1-2.3)."""

import inspect
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import update

from app.modules.clientes import service as clientes_service
from app.modules.clientes.repository import ClienteRepository
from tests.conftest import email_unico

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def _login(client: httpx.AsyncClient, usuario, password: str = PASSWORD) -> None:
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": usuario.email, "password": password}
    )
    assert response.status_code == 200


def _peticiones(cliente_id: int) -> list[tuple[str, str, dict]]:
    return [
        (
            "post",
            "/clientes/",
            {"json": {"nombre": "Nuevo", "email": email_unico("c13-post")}},
        ),
        ("get", f"/clientes/{cliente_id}", {}),
        ("patch", f"/clientes/{cliente_id}", {"json": {"nombre": "Renombrado"}}),
        (
            "post",
            f"/clientes/{cliente_id}/perfil",
            {"json": {"telefono": "555-0100", "direccion": "Calle 1"}},
        ),
        ("get", f"/clientes/{cliente_id}/ventas", {}),
    ]


async def test_sin_cookie_las_rutas_de_clientes_dan_401(
    api_client: httpx.AsyncClient,
) -> None:
    for metodo, url, kwargs in _peticiones(999_999_999):
        response = await getattr(api_client, metodo)(url, **kwargs)

        assert response.status_code == 401, (metodo, url, response.text)
        assert response.json() == {"detail": "No autenticado"}


async def test_cliente_no_accede_a_ninguna_ruta_de_clientes(
    api_client: httpx.AsyncClient, usuario_factory, cliente_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    cliente = await cliente_factory()
    await _login(api_client, usuario)

    for metodo, url, kwargs in _peticiones(cliente.id):
        response = await getattr(api_client, metodo)(url, **kwargs)

        assert response.status_code == 403, (metodo, url, response.text)
        assert response.json() == {"detail": "No autorizado"}
        for rol in ("CLIENTE", "VENDEDOR", "ADMIN"):
            assert rol not in response.text


@pytest.mark.parametrize("roles", [("VENDEDOR",), ("ADMIN",)])
async def test_personal_atiende_las_rutas_de_clientes(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    roles: tuple[str, ...],
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=roles)
    cliente = await cliente_factory()
    await _login(api_client, usuario)

    detalle = await api_client.get(f"/clientes/{cliente.id}")
    assert detalle.status_code == 200
    assert detalle.json()["id"] == cliente.id

    actualizado = await api_client.patch(
        f"/clientes/{cliente.id}", json={"nombre": "Renombrado"}
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["nombre"] == "Renombrado"

    perfil = await api_client.post(
        f"/clientes/{cliente.id}/perfil",
        json={"telefono": "555-0100", "direccion": "Calle 1"},
    )
    assert perfil.status_code == 201
    assert perfil.json()["cliente_id"] == cliente.id

    ventas = await api_client.get(f"/clientes/{cliente.id}/ventas")
    assert ventas.status_code == 200
    assert set(ventas.json()) == {"items", "total", "page", "size", "pages"}
    assert ventas.json()["items"] == []

    creado = await api_client.post(
        "/clientes/",
        json={"nombre": "Cliente nuevo", "email": email_unico("c13-alta")},
    )
    assert creado.status_code == 201
    assert creado.json()["id"]
    cliente_factory.registrar(creado.json()["id"])


@pytest.mark.parametrize("roles", [("VENDEDOR",), ("ADMIN",)])
async def test_cliente_inexistente_da_404_solo_para_personal(
    api_client: httpx.AsyncClient, usuario_factory, roles: tuple[str, ...]
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=roles)
    await _login(api_client, usuario)

    rutas = [
        ("get", "/clientes/999999999", {}),
        ("patch", "/clientes/999999999", {"json": {"nombre": "X"}}),
        ("post", "/clientes/999999999/perfil", {"json": {}}),
        ("get", "/clientes/999999999/ventas", {}),
    ]
    for metodo, url, kwargs in rutas:
        response = await getattr(api_client, metodo)(url, **kwargs)

        assert response.status_code == 404, (metodo, url, response.text)


async def test_el_403_de_cliente_no_ejecuta_la_consulta_de_ventas(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    cliente = await cliente_factory()
    await _login(api_client, usuario)
    llamadas = 0

    async def prohibida(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        raise AssertionError("un CLIENTE no debe ejecutar la consulta de ventas")

    monkeypatch.setattr(ClienteRepository, "ventas_de", prohibida)

    response = await api_client.get(f"/clientes/{cliente.id}/ventas")

    assert response.status_code == 403
    assert llamadas == 0


@pytest.mark.parametrize(
    "cambio",
    [
        {"revocada_en": datetime.now(timezone.utc)},
        {"vence_en": datetime.now(timezone.utc) - timedelta(seconds=1)},
    ],
    ids=["revocado", "vencido"],
)
async def test_rol_revocado_o_vencido_quita_el_acceso_con_la_misma_cookie(
    api_client: httpx.AsyncClient,
    db_sessionmaker,
    usuario_factory,
    cliente_factory,
    cambio: dict,
) -> None:
    from app.modules.usuarios.models import AsignacionRol

    usuario = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    cliente = await cliente_factory()
    await _login(api_client, usuario)

    async with db_sessionmaker() as session:
        await session.execute(
            update(AsignacionRol)
            .where(
                AsignacionRol.usuario_id == usuario.id,
                AsignacionRol.rol == "VENDEDOR",
            )
            .values(**cambio)
        )
        await session.commit()

    response = await api_client.get(f"/clientes/{cliente.id}/ventas")

    assert response.status_code == 403
    assert response.json() == {"detail": "No autorizado"}


async def test_ventas_de_cliente_pagina_sin_repetir_ni_omitir(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    venta_factory,
) -> None:
    """El orden determinista por `Venta.id` evita repetidos entre páginas."""
    usuario = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    cliente = await cliente_factory()
    ventas = [await venta_factory(cliente_id=cliente.id) for _ in range(3)]
    await _login(api_client, usuario)

    primera = await api_client.get(
        f"/clientes/{cliente.id}/ventas", params={"page": 1, "size": 2}
    )
    segunda = await api_client.get(
        f"/clientes/{cliente.id}/ventas", params={"page": 2, "size": 2}
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    ids_primera = [item["id"] for item in primera.json()["items"]]
    ids_segunda = [item["id"] for item in segunda.json()["items"]]
    assert ids_primera == [ventas[0].id, ventas[1].id]
    assert ids_segunda == [ventas[2].id]
    assert ids_primera + ids_segunda == [v.id for v in ventas]


async def test_ventas_de_stmt_ordena_por_venta_id() -> None:
    from sqlalchemy.dialects import postgresql

    stmt = ClienteRepository.ventas_de_stmt(7)
    sql = str(stmt.compile(dialect=postgresql.dialect()))

    assert "ORDER BY venta.id" in sql


async def test_ventas_de_exige_el_parametro_actual() -> None:
    parametro = inspect.signature(clientes_service.ventas_de).parameters["actual"]

    assert parametro.default is inspect.Parameter.empty
