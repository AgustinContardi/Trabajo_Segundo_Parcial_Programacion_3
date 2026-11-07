"""Contrato HTTP de `GET|POST /usuarios/{id}/roles` y `DELETE /usuarios/{id}/roles/{rol}`
(C-15, tarea 6.3) contra PostgreSQL real.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def _login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _admin(api_client: httpx.AsyncClient, usuario_factory) -> None:
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=False
    )
    await _login(api_client, admin.email)


def _roles_url(usuario_id: int) -> str:
    return f"/usuarios/{usuario_id}/roles"


async def test_asignar_rol_sin_vence_en_da_201(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    response = await api_client.post(
        _roles_url(objetivo.id),
        json={"rol": "ADMIN"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["usuario_id"] == objetivo.id
    assert body["rol"] == "ADMIN"
    assert body["vence_en"] is None
    assert body["revocada_en"] is None
    assert body["otorgada_por"] is not None
    assert body["desde"] is not None


async def test_asignar_rol_con_vence_en_futuro_da_201(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=())
    futuro = datetime.now(timezone.utc) + timedelta(days=1)
    response = await api_client.post(
        _roles_url(objetivo.id),
        json={"rol": "VENDEDOR", "vence_en": futuro.isoformat()},
    )
    assert response.status_code == 201, response.text
    assert response.json()["vence_en"] is not None


async def test_asignar_rol_vence_en_sin_zona_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    naive = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
    response = await api_client.post(
        _roles_url(objetivo.id),
        json={"rol": "VENDEDOR", "vence_en": naive.isoformat()},
    )
    assert response.status_code == 422, response.text


async def test_asignar_rol_vence_en_pasado_da_422_no_409(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    pasado = datetime.now(timezone.utc) - timedelta(days=1)
    response = await api_client.post(
        _roles_url(objetivo.id),
        json={"rol": "VENDEDOR", "vence_en": pasado.isoformat()},
    )
    assert response.status_code == 422, response.text


async def test_asignar_rol_rol_invalido_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    response = await api_client.post(
        _roles_url(objetivo.id),
        json={"rol": "SUPERVISOR"},
    )
    assert response.status_code == 422, response.text


async def test_asignar_rol_usuario_inexistente_da_404(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    response = await api_client.post("/usuarios/999999/roles", json={"rol": "VENDEDOR"})
    assert response.status_code == 404, response.text


async def test_asignar_rol_segunda_abierta_mismo_rol_da_409(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    # Ya tiene VENDEDOR abierto (sembrado por la factory)
    response = await api_client.post(
        _roles_url(objetivo.id), json={"rol": "VENDEDOR"}
    )
    assert response.status_code == 409, response.text
    assert response.json() == {
        "detail": "El usuario ya tiene una asignación abierta de ese rol"
    }


async def test_revocar_rol_escribe_revocada_en_da_200(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    response = await api_client.delete(
        f"/usuarios/{objetivo.id}/roles/ADMIN"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["usuario_id"] == objetivo.id
    assert body["rol"] == "ADMIN"
    assert body["revocada_en"] is not None


async def test_revocar_rol_nunca_asignado_da_404(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    response = await api_client.delete(f"/usuarios/{objetivo.id}/roles/ADMIN")
    assert response.status_code == 404, response.text


async def test_revocar_rol_ya_revocada_da_409(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    # Primera revocación
    await api_client.delete(f"/usuarios/{objetivo.id}/roles/ADMIN")
    # Segunda: ya revocada
    response = await api_client.delete(f"/usuarios/{objetivo.id}/roles/ADMIN")
    assert response.status_code == 409, response.text


async def test_revocar_propio_admin_da_409(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=False
    )
    await _login(api_client, admin.email)
    response = await api_client.delete(f"/usuarios/{admin.id}/roles/ADMIN")
    assert response.status_code == 409, response.text


async def test_listar_roles_historial_da_200(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    objetivo = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    response = await api_client.get(_roles_url(objetivo.id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    roles = [item["rol"] for item in body]
    assert "VENDEDOR" in roles


async def test_listar_roles_usuario_inexistente_da_404(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    response = await api_client.get("/usuarios/999999/roles")
    assert response.status_code == 404, response.text
