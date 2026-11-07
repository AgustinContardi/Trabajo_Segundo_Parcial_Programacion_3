"""Contrato HTTP de `GET /eventos` (C-15, tarea 6.4) contra PostgreSQL real.

Envoltorio `{items, total, page, size, pages}`, ítems `{id, cuando, actor, accion}`,
`size` fuera de 1..100 → 422, página fuera de rango → 422, orden más reciente
primero, actor puede ser "SISTEMA".
"""

from datetime import datetime, timezone

import httpx
import pytest
import uuid

from app.core.config import get_settings
from app.core.database import crear_engine, crear_sessionmaker
from app.modules.usuarios.models import EventoSeguridad

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
EVENTOS = "/eventos/"


def _email(prefijo: str = "evt") -> str:
    return f"{prefijo}-{uuid.uuid4().hex}@example.com"


async def _login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _admin(api_client: httpx.AsyncClient, usuario_factory):
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=False
    )
    await _login(api_client, admin.email)
    return admin


async def _insertar_evento(actor: str = "SISTEMA", accion: str = "Evento de prueba") -> None:
    settings = get_settings()
    engine = crear_engine(settings)
    sessionmaker = crear_sessionmaker(engine)
    try:
        async with sessionmaker() as session:
            session.add(EventoSeguridad(cuando=datetime.now(timezone.utc), actor=actor, accion=accion))
            await session.commit()
    finally:
        await engine.dispose()


async def test_eventos_valor_por_defecto_da_envoltorio(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    response = await api_client.get(EVENTOS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "total", "page", "size", "pages"}
    assert body["page"] == 1
    assert body["size"] == 20
    assert isinstance(body["items"], list)


async def test_eventos_sin_filas_devuelve_items_vacio_y_pages_1(
    api_client: httpx.AsyncClient, usuario_factory, db_sessionmaker
) -> None:
    # evento_seguridad es append-only (RN-12): limpio para aislar esta prueba.
    async with db_sessionmaker() as session:
        from app.modules.usuarios.models import EventoSeguridad
        from sqlalchemy import delete
        await session.execute(delete(EventoSeguridad))
        await session.commit()
    await _admin(api_client, usuario_factory)
    response = await api_client.get(EVENTOS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["pages"] == 1


async def test_eventos_size_fuera_de_rango_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    for size in (0, 101, 500):
        response = await api_client.get(EVENTOS, params={"size": size})
        assert response.status_code == 422, (size, response.text)


async def test_eventos_pagina_fuera_de_rango_da_422(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _admin(api_client, usuario_factory)
    response = await api_client.get(EVENTOS, params={"page": 0})
    assert response.status_code == 422, response.text
    response = await api_client.get(EVENTOS, params={"page": 9999})
    assert response.status_code == 422, response.text


async def test_eventos_orden_mas_reciente_primero(
    api_client: httpx.AsyncClient, usuario_factory, db_sessionmaker
) -> None:
    admin = await _admin(api_client, usuario_factory)
    creados: list[tuple[int, str]] = []
    try:
        for prefijo in ("evt1", "evt2"):
            correo = _email(prefijo)
            respuesta = await api_client.post(
                "/usuarios/",
                json={"email": correo, "nombre": "E", "password": PASSWORD, "rol": "VENDEDOR"},
            )
            assert respuesta.status_code == 201, respuesta.text
            creados.append((respuesta.json()["id"], correo))
        response = await api_client.get(EVENTOS, params={"size": 50})
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert len(items) >= 2
        for item in items:
            assert set(item) == {"id", "cuando", "actor", "accion"}
        cuandos = [item["cuando"] for item in items]
        assert cuandos == sorted(cuandos, reverse=True)
    finally:
        from sqlalchemy import delete, or_

        from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario

        async with db_sessionmaker() as session:
            for usuario_id, correo in creados:
                await session.execute(
                    delete(AsignacionRol).where(
                        or_(
                            AsignacionRol.usuario_id == usuario_id,
                            AsignacionRol.otorgada_por == admin.id,
                        )
                    )
                )
                await session.execute(delete(Usuario).where(Usuario.id == usuario_id))
                await session.execute(delete(IntentoAcceso).where(IntentoAcceso.email == correo))
            await session.commit()


async def test_eventos_actor_sistema_se_lee_sin_error(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    await _insertar_evento("SISTEMA", "Evento de prueba")
    await _admin(api_client, usuario_factory)
    response = await api_client.get(EVENTOS)
    assert response.status_code == 200, response.text
    actores = [item["actor"] for item in response.json()["items"]]
    assert "SISTEMA" in actores


async def test_eventos_sin_sesion_da_401(api_client: httpx.AsyncClient) -> None:
    api_client.cookies.clear()
    response = await api_client.get(EVENTOS)
    assert response.status_code == 401, response.text


async def test_eventos_vendedor_da_403(
    api_client: httpx.AsyncClient, usuario_factory
) -> None:
    vendedor = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    await _login(api_client, vendedor.email)
    response = await api_client.get(EVENTOS)
    assert response.status_code == 403, response.text
