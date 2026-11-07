"""Regresión: catálogo bajo la puerta del cambio obligatorio (C-15, tarea 7).

Un ADMIN con `debe_cambiar_password=true` recibe `403` en las mutaciones del
catálogo (sin ejecutar el handler de negocio), y las lecturas públicas siguen
en `200`. Incluye una tabla de rutas para detectar cambios accidentales de
paths/métodos.
"""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


def _nuevo_nombre(prefijo: str) -> str:
    return f"{prefijo} {uuid.uuid4().hex}"


async def _login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _admin_con_cambio_pendiente(
    api_client: httpx.AsyncClient, usuario_factory
):
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=True
    )
    await _login(api_client, admin.email)
    return admin


async def _admin_sin_cambio(
    api_client: httpx.AsyncClient, usuario_factory
):
    admin = await usuario_factory(
        password=PASSWORD, roles=("ADMIN",), debe_cambiar_password=False
    )
    await _login(api_client, admin.email)
    return admin


async def _esperar_403(
    api_client: httpx.AsyncClient,
    usuario_factory,
    metodo: str,
    url: str,
    kwargs: dict,
) -> None:
    await _admin_con_cambio_pendiente(api_client, usuario_factory)
    response = await getattr(api_client, metodo)(url, **kwargs)
    assert response.status_code == 403, (metodo, url, response.text)
    assert response.json() == {"detail": "No autorizado"}


async def test_editoriales_mutan_con_cambio_pendiente_da_403(
    api_client: httpx.AsyncClient,
    usuario_factory,
    catalogo_factory,
) -> None:
    editorial = await catalogo_factory.editorial()
    await _esperar_403(
        api_client, usuario_factory, "post", "/editoriales/",
        {"json": {"nombre": _nuevo_nombre("Editorial"), "pais": "Chile"}},
    )
    await _esperar_403(
        api_client, usuario_factory, "patch", f"/editoriales/{editorial.id}",
        {"json": {"pais": "Uruguay"}},
    )


async def test_generos_mutan_con_cambio_pendiente_da_403(
    api_client: httpx.AsyncClient,
    usuario_factory,
    catalogo_factory,
) -> None:
    await catalogo_factory.genero()
    await _esperar_403(
        api_client, usuario_factory, "post", "/generos/",
        {"json": {"nombre": _nuevo_nombre("Genero")}},
    )


async def test_autores_mutan_con_cambio_pendiente_da_403(
    api_client: httpx.AsyncClient,
    usuario_factory,
    catalogo_factory,
) -> None:
    autor = await catalogo_factory.autor()
    await _esperar_403(
        api_client, usuario_factory, "post", "/autores/",
        {"json": {"nombre": _nuevo_nombre("Autor"), "nacionalidad": "Chile"}},
    )
    await _esperar_403(
        api_client, usuario_factory, "patch", f"/autores/{autor.id}",
        {"json": {"nacionalidad": "Uruguay"}},
    )


async def test_libros_mutan_con_cambio_pendiente_da_403(
    api_client: httpx.AsyncClient,
    usuario_factory,
    catalogo_factory,
) -> None:
    editorial = await catalogo_factory.editorial()
    libro = await catalogo_factory.libro(editorial_id=editorial.id)
    isbn = f"isbn-{uuid.uuid4().hex}"
    cuerpo = {
        "isbn": isbn,
        "titulo": "Libro nuevo",
        "precio": "12.50",
        "stock_inicial": 0,
        "editorial_id": editorial.id,
        "autores": [],
    }
    await _esperar_403(
        api_client, usuario_factory, "post", "/libros/", {"json": cuerpo}
    )
    await _esperar_403(
        api_client, usuario_factory, "patch", f"/libros/{libro.id}",
        {"json": {"titulo": "Editado"}},
    )
    await _esperar_403(
        api_client, usuario_factory, "delete", f"/libros/{libro.id}", {}
    )
    await _esperar_403(
        api_client, usuario_factory, "post", f"/libros/{libro.id}/reponer",
        {"json": {"cantidad": 5}},
    )
    await _esperar_403(
        api_client, usuario_factory, "get", f"/libros/{libro.id}/movimientos", {}
    )


async def test_admin_sin_cambio_sigue_pudiendo_mutar_da_201(
    api_client: httpx.AsyncClient,
    usuario_factory,
    catalogo_factory,
) -> None:
    await _admin_sin_cambio(api_client, usuario_factory)
    editorial = await catalogo_factory.editorial()
    creada = await api_client.post(
        "/editoriales/",
        json={"nombre": _nuevo_nombre("Editorial"), "pais": "Chile"},
    )
    assert creada.status_code == 201, creada.text
    catalogo_factory.registrar_editorial(creada.json()["id"])

    actualizada = await api_client.patch(
        f"/editoriales/{editorial.id}", json={"pais": "Uruguay"}
    )
    assert actualizada.status_code == 200, actualizada.text


async def test_venedor_recibe_403_en_mutaciones(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    await catalogo_factory.editorial()
    vendedor = await usuario_factory(password=PASSWORD, roles=("VENDEDOR",))
    await _login(api_client, vendedor.email)
    response = await api_client.post(
        "/editoriales/",
        json={"nombre": _nuevo_nombre("Editorial"), "pais": "Chile"},
    )
    assert response.status_code == 403, response.text


async def test_lecturas_publicas_sin_cookie_son_200(
    api_client: httpx.AsyncClient, catalogo_factory
) -> None:
    editorial = await catalogo_factory.editorial()
    genero = await catalogo_factory.genero()
    autor = await catalogo_factory.autor()
    libro = await catalogo_factory.libro(
        editorial_id=editorial.id, genero_id=genero.id
    )

    rutas = [
        "/libros/",
        f"/libros/{libro.id}",
        "/editoriales/",
        f"/editoriales/{editorial.id}",
        f"/editoriales/{editorial.id}/libros",
        "/generos/",
        f"/generos/{genero.id}/libros",
        "/autores/",
        f"/autores/{autor.id}",
        f"/autores/{autor.id}/libros",
    ]
    for url in rutas:
        api_client.cookies.clear()
        response = await api_client.get(url)
        assert response.status_code == 200, (url, response.text)


# --- Tabla de rutas: paths y métodos del catálogo no cambian ---

RUTAS_CATALOGO_ESPERADAS = {
    ("POST", "/editoriales/"),
    ("GET", "/editoriales/"),
    ("GET", "/editoriales/{editorial_id}"),
    ("PATCH", "/editoriales/{editorial_id}"),
    ("GET", "/editoriales/{editorial_id}/libros"),
    ("POST", "/generos/"),
    ("GET", "/generos/"),
    ("GET", "/generos/{genero_id}/libros"),
    ("POST", "/autores/"),
    ("GET", "/autores/"),
    ("GET", "/autores/{autor_id}"),
    ("PATCH", "/autores/{autor_id}"),
    ("GET", "/autores/{autor_id}/libros"),
    ("POST", "/libros/"),
    ("GET", "/libros/"),
    ("GET", "/libros/{libro_id}"),
    ("PATCH", "/libros/{libro_id}"),
    ("DELETE", "/libros/{libro_id}"),
    ("POST", "/libros/{libro_id}/reponer"),
    ("GET", "/libros/{libro_id}/movimientos"),
}


async def test_tabla_de_rutas_catalogo_inalterada(api_app) -> None:
    """Fija el conjunto (método, path) del catálogo para detectar cambios
    accidentales de paths, métodos o tags al separar routers, a partir del
    esquema OpenAPI generado por la aplicación."""
    schema = api_app.openapi()
    rutas: set[tuple[str, str]] = set()
    for path, operaciones in schema.get("paths", {}).items():
        if path.startswith(("/editoriales", "/generos", "/autores", "/libros")):
            for metodo in operaciones:
                if metodo.upper() in ("GET", "POST", "PATCH", "DELETE"):
                    rutas.add((metodo.upper(), path))
    faltan = RUTAS_CATALOGO_ESPERADAS - rutas
    sobran = rutas - RUTAS_CATALOGO_ESPERADAS
    assert not faltan, f"Rutas del catálogo que desaparecieron: {faltan}"
    assert not sobran, f"Rutas del catálogo nuevas o modificadas: {sobran}"
