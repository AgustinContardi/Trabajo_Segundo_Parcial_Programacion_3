"""Matriz RBAC del catálogo (C-13, 3.1-3.3)."""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


async def _login(client: httpx.AsyncClient, usuario, password: str = PASSWORD) -> None:
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": usuario.email, "password": password}
    )
    assert response.status_code == 200, response.text


async def _sin_cookie_y_sin_rol(
    client: httpx.AsyncClient,
    usuario_factory,
    metodo: str,
    url: str,
    kwargs: dict,
) -> None:
    """Verifica 401 sin cookie y 403 genérico para VENDEDOR y CLIENTE."""
    client.cookies.clear()
    response = await getattr(client, metodo)(url, **kwargs)
    assert response.status_code == 401, (metodo, url, response.text)
    assert response.json() == {"detail": "No autenticado"}

    for rol in ("VENDEDOR", "CLIENTE"):
        usuario = await usuario_factory(password=PASSWORD, roles=(rol,))
        await _login(client, usuario)
        response = await getattr(client, metodo)(url, **kwargs)
        assert response.status_code == 403, (rol, metodo, url, response.text)
        assert response.json() == {"detail": "No autorizado"}
        assert rol not in response.text


async def _admin(
    client: httpx.AsyncClient, usuario_factory
) -> None:
    usuario = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    await _login(client, usuario)


async def test_editoriales_solo_admin_muta(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    editorial = await catalogo_factory.editorial()
    nueva = f"Editorial nueva {uuid.uuid4().hex}"

    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "post",
        "/editoriales/",
        {"json": {"nombre": nueva, "pais": "Chile"}},
    )
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "patch",
        f"/editoriales/{editorial.id}",
        {"json": {"pais": "Uruguay"}},
    )

    await _admin(api_client, usuario_factory)
    creada = await api_client.post(
        "/editoriales/", json={"nombre": nueva, "pais": "Chile"}
    )
    assert creada.status_code == 201
    catalogo_factory.registrar_editorial(creada.json()["id"])

    actualizada = await api_client.patch(
        f"/editoriales/{editorial.id}", json={"pais": "Uruguay"}
    )
    assert actualizada.status_code == 200
    assert actualizada.json()["pais"] == "Uruguay"


async def test_generos_solo_admin_crea(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    nombre = f"Genero nuevo {uuid.uuid4().hex}"
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "post",
        "/generos/",
        {"json": {"nombre": nombre}},
    )

    await _admin(api_client, usuario_factory)
    creado = await api_client.post("/generos/", json={"nombre": nombre})

    assert creado.status_code == 201
    catalogo_factory.registrar_genero(creado.json()["id"])


async def test_autores_solo_admin_muta(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    autor = await catalogo_factory.autor()
    nombre = f"Autor nuevo {uuid.uuid4().hex}"

    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "post",
        "/autores/",
        {"json": {"nombre": nombre, "nacionalidad": "Chile"}},
    )
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "patch",
        f"/autores/{autor.id}",
        {"json": {"nacionalidad": "Uruguay"}},
    )

    await _admin(api_client, usuario_factory)
    creado = await api_client.post(
        "/autores/", json={"nombre": nombre, "nacionalidad": "Chile"}
    )
    assert creado.status_code == 201
    catalogo_factory.registrar_autor(creado.json()["id"])

    actualizado = await api_client.patch(
        f"/autores/{autor.id}", json={"nacionalidad": "Uruguay"}
    )
    assert actualizado.status_code == 200
    assert actualizado.json()["nacionalidad"] == "Uruguay"


async def test_libros_y_stock_solo_admin(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    editorial = await catalogo_factory.editorial()
    para_editar = await catalogo_factory.libro(editorial_id=editorial.id)
    para_baja = await catalogo_factory.libro(editorial_id=editorial.id)
    isbn = f"isbn-nuevo-{uuid.uuid4().hex}"
    cuerpo_libro = {
        "isbn": isbn,
        "titulo": "Libro nuevo",
        "precio": "12.50",
        "stock_inicial": 0,
        "editorial_id": editorial.id,
        "autores": [],
    }

    await _sin_cookie_y_sin_rol(
        api_client, usuario_factory, "post", "/libros/", {"json": cuerpo_libro}
    )
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "patch",
        f"/libros/{para_editar.id}",
        {"json": {"titulo": "Editado"}},
    )
    await _sin_cookie_y_sin_rol(
        api_client, usuario_factory, "delete", f"/libros/{para_baja.id}", {}
    )
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "post",
        f"/libros/{para_editar.id}/reponer",
        {"json": {"cantidad": 5}},
    )
    await _sin_cookie_y_sin_rol(
        api_client,
        usuario_factory,
        "get",
        f"/libros/{para_editar.id}/movimientos",
        {},
    )

    await _admin(api_client, usuario_factory)
    creado = await api_client.post("/libros/", json=cuerpo_libro)
    assert creado.status_code == 201
    assert creado.json()["isbn"] == isbn
    catalogo_factory.registrar_libro(creado.json()["id"])

    editado = await api_client.patch(
        f"/libros/{para_editar.id}", json={"titulo": "Editado"}
    )
    assert editado.status_code == 200
    assert editado.json()["titulo"] == "Editado"

    baja = await api_client.delete(f"/libros/{para_baja.id}")
    assert baja.status_code == 204


async def test_admin_reponer_y_movimientos_contrato(
    api_client: httpx.AsyncClient,
    api_app,
    settings,
    usuario_factory,
    catalogo_factory,
) -> None:
    """Reponer y leer movimientos dentro de una transacción que se revierte.

    `movimiento_stock` es de sólo agregado (RN-12): no se puede limpiar con
    DELETE. La prueba envuelve las escrituras en una transacción externa y la
    revierte, de modo que la base queda igual y el trigger nunca se burla.
    """
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.database import crear_engine, get_session

    editorial = await catalogo_factory.editorial()
    libro = await catalogo_factory.libro(editorial_id=editorial.id)

    engine = crear_engine(settings)
    conexion = await engine.connect()
    transaccion = await conexion.begin()
    fabrica = async_sessionmaker(
        bind=conexion,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    sesion = fabrica()

    async def sesion_compartida(request: Request):
        yield sesion

    api_app.dependency_overrides[get_session] = sesion_compartida
    try:
        await _admin(api_client, usuario_factory)
        repuesto = await api_client.post(
            f"/libros/{libro.id}/reponer", json={"cantidad": 5}
        )
        assert repuesto.status_code == 200
        assert repuesto.json()["stock"] == 5

        movimientos = await api_client.get(f"/libros/{libro.id}/movimientos")
        assert movimientos.status_code == 200
        assert len(movimientos.json()) == 1
        assert movimientos.json()[0]["cantidad"] == 5
    finally:
        api_app.dependency_overrides.pop(get_session, None)
        await sesion.close()
        await transaccion.rollback()
        await conexion.close()
        await engine.dispose()


async def test_patch_de_autor_homonimo_no_promete_un_409(
    api_client: httpx.AsyncClient, usuario_factory, catalogo_factory
) -> None:
    """`autor` no declara unicidad: copiar los datos de otro autor da 200."""
    primero = await catalogo_factory.autor()
    segundo = await catalogo_factory.autor()
    await _admin(api_client, usuario_factory)

    response = await api_client.patch(
        f"/autores/{primero.id}",
        json={"nombre": segundo.nombre, "nacionalidad": segundo.nacionalidad},
    )

    assert response.status_code == 200, response.text
    assert response.json()["nombre"] == segundo.nombre


async def test_lecturas_publicas_siguen_abiertas(
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
        sin_cookie = await api_client.get(url)
        assert sin_cookie.status_code == 200, (url, sin_cookie.text)

        api_client.cookies.set("access_token", "cookie-invalida-ignorada")
        con_cookie_invalida = await api_client.get(url)
        assert con_cookie_invalida.status_code == 200, (url, con_cookie_invalida.text)
