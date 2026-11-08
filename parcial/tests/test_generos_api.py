"""`GET /generos/{id}`: lectura pública del catálogo (C-06)."""

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_genero_existente_devuelve_id_y_nombre(
    api_client: httpx.AsyncClient, catalogo_factory
) -> None:
    genero = await catalogo_factory.genero()

    response = await api_client.get(f"/generos/{genero.id}")

    assert response.status_code == 200, response.text
    assert response.json() == {"id": genero.id, "nombre": genero.nombre}


async def test_genero_inexistente_da_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/generos/999999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Género no encontrado"}
