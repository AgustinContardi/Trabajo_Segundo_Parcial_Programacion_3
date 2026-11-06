"""Ventas: personal con rol y propiedad decidida por el servicio (C-13, 4.1-4.3)."""

import inspect

import httpx
import pytest

from app.modules.ventas import service as ventas_service

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def _login(client: httpx.AsyncClient, usuario, password: str = PASSWORD) -> None:
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": usuario.email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _cliente_con_venta(
    usuario_factory, cliente_factory, venta_factory, *, roles: tuple[str, ...]
):
    usuario = await usuario_factory(password=PASSWORD, roles=roles)
    cliente = await cliente_factory(usuario_id=usuario.id)
    venta = await venta_factory(cliente_id=cliente.id)
    return usuario, cliente, venta


async def test_listar_ventas_sin_cookie_da_401(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/ventas/")

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


async def test_cliente_no_lista_todas_las_ventas(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    await _login(api_client, usuario)

    response = await api_client.get("/ventas/")

    assert response.status_code == 403
    assert response.json() == {"detail": "No autorizado"}
    assert "CLIENTE" not in response.text


@pytest.mark.parametrize("roles", [("VENDEDOR",), ("ADMIN",)])
async def test_personal_lista_ventas_con_el_envoltorio(
    api_client: httpx.AsyncClient,
    usuario_factory,
    roles: tuple[str, ...],
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=roles)
    await _login(api_client, usuario)

    response = await api_client.get("/ventas/")

    assert response.status_code == 200
    assert set(response.json()) == {"items", "total", "page", "size", "pages"}


async def test_dueno_consulta_su_venta_sin_rol_de_personal(
    api_client: httpx.AsyncClient, usuario_factory, cliente_factory, venta_factory
) -> None:
    usuario, cliente, venta = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    await _login(api_client, usuario)

    response = await api_client.get(f"/ventas/{venta.id}")

    assert response.status_code == 200
    assert response.json()["id"] == venta.id
    assert response.json()["cliente"]["id"] == cliente.id


async def test_otro_cliente_no_consulta_una_venta_ajena(
    api_client: httpx.AsyncClient, usuario_factory, cliente_factory, venta_factory
) -> None:
    _, _, venta_ajena = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    otro_usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    await cliente_factory(usuario_id=otro_usuario.id)
    await _login(api_client, otro_usuario)

    response = await api_client.get(f"/ventas/{venta_ajena.id}")

    assert response.status_code == 403
    assert response.json() == {"detail": "No autorizado"}
    assert "CLIENTE" not in response.text


@pytest.mark.parametrize("roles", [("VENDEDOR",), ("ADMIN",)])
async def test_personal_consulta_cualquier_venta(
    api_client: httpx.AsyncClient,
    usuario_factory,
    cliente_factory,
    venta_factory,
    roles: tuple[str, ...],
) -> None:
    _, _, venta = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    personal = await usuario_factory(password=PASSWORD, roles=roles)
    await _login(api_client, personal)

    response = await api_client.get(f"/ventas/{venta.id}")

    assert response.status_code == 200
    assert response.json()["id"] == venta.id


async def test_venta_inexistente_da_404_a_cualquier_sesion(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    for roles in (("CLIENTE",), ("VENDEDOR",), ("ADMIN",)):
        usuario = await usuario_factory(password=PASSWORD, roles=roles)
        await _login(api_client, usuario)

        response = await api_client.get("/ventas/999999999")

        assert response.status_code == 404, roles
        assert response.json() == {"detail": "Venta no encontrada"}


async def test_mis_ventas_sin_cookie_da_401(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/ventas/mis-ventas")

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


async def test_mis_ventas_devuelve_solo_las_ventas_propias(
    api_client: httpx.AsyncClient, usuario_factory, cliente_factory, venta_factory
) -> None:
    usuario, cliente, venta = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    _, otro_cliente, _ = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    await _login(api_client, usuario)

    response = await api_client.get("/ventas/mis-ventas")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [venta.id]
    assert all(item["cliente_id"] == cliente.id for item in body["items"])
    assert all(item["cliente_id"] != otro_cliente.id for item in body["items"])


async def test_mis_ventas_sin_ficha_de_cliente_devuelve_pagina_vacia(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    await _login(api_client, usuario)

    response = await api_client.get("/ventas/mis-ventas")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "size": 20,
        "pages": 1,
    }


async def test_obtener_exige_identidad_actual_y_el_servicio_decide_la_propiedad(
    api_client: httpx.AsyncClient, usuario_factory, cliente_factory, venta_factory
) -> None:
    _, cliente, venta = await _cliente_con_venta(
        usuario_factory, cliente_factory, venta_factory, roles=("CLIENTE",)
    )
    otro_usuario = await usuario_factory(password=PASSWORD, roles=("CLIENTE",))
    await cliente_factory(usuario_id=otro_usuario.id)
    await _login(api_client, otro_usuario)

    parametro = inspect.signature(ventas_service.obtener).parameters["actual"]
    assert parametro.default is inspect.Parameter.empty

    # El servicio, no la ruta, decide: el cliente ajeno recibe 403.
    response = await api_client.get(f"/ventas/{venta.id}")
    assert response.status_code == 403
