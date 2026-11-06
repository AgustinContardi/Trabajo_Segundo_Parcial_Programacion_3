"""Contexto de autorización por rol (C-13, 1.1 y 1.2).

Las pruebas usan PostgreSQL real y la app de ``main`` con su ``lifespan``; la
cookie se firma con el helper ``token_manual`` para poder construir escenarios
que el login normal no produce (token que miente, rol revocado o vencido).
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
from sqlalchemy import update

from tests.conftest import token_manual

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sesion_client() -> AsyncIterator[httpx.AsyncClient]:
    """App de prueba con una ruta que expone la sesión y otra la identidad."""
    from fastapi import Depends, FastAPI

    from app.core.dependencies import (
        IdentidadActual,
        get_sesion_actual,
        get_usuario_actual,
    )
    from app.modules.usuarios.models import Usuario
    from main import lifespan

    app = FastAPI(lifespan=lifespan)

    @app.get("/_test/sesion")
    async def sesion(identidad: IdentidadActual = Depends(get_sesion_actual)):
        return {
            "id": identidad.usuario.id,
            "roles": list(identidad.roles_db),
            "roles_token": list(identidad.roles_token),
        }

    @app.get("/_test/usuario")
    async def usuario(actual: Usuario = Depends(get_usuario_actual)):
        return {"id": actual.id, "email": actual.email}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client


async def test_sesion_actual_devuelve_roles_db_y_roles_token(
    sesion_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("CLIENTE", "ADMIN"))
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=["VENDEDOR"],
    )
    sesion_client.cookies.set("access_token", token)

    response = await sesion_client.get("/_test/sesion")

    assert response.status_code == 200
    assert response.json() == {
        "id": usuario.id,
        "roles": ["ADMIN", "CLIENTE"],
        "roles_token": ["VENDEDOR"],
    }


async def test_sesion_actual_ignora_un_claim_roles_malformado(
    sesion_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("CLIENTE",))
    token = jwt.encode(
        {
            "sub": str(usuario.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "roles": 123,
        },
        settings.JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )
    sesion_client.cookies.set("access_token", token)

    response = await sesion_client.get("/_test/sesion")

    assert response.status_code == 200
    assert response.json()["roles_token"] == []
    assert response.json()["roles"] == ["CLIENTE"]


async def test_sesion_actual_sin_roles_en_la_base_devuelve_lista_vacia(
    sesion_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=())
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=[],
    )
    sesion_client.cookies.set("access_token", token)

    response = await sesion_client.get("/_test/sesion")

    assert response.status_code == 200
    assert response.json()["roles"] == []
    assert response.json()["roles_token"] == []


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda settings: None,
        lambda settings: "esto-no-es-un-jwt",
        lambda settings: token_manual(
            subject=1,
            secret="otro-secreto-de-prueba-de-32-bytes-o-mas",
        ),
        lambda settings: token_manual(
            subject=1,
            secret=settings.JWT_SECRET.get_secret_value(),
            exp_offset_seconds=-1,
        ),
    ],
)
async def test_sesion_actual_rechaza_cookie_ausente_o_token_invalido(
    sesion_client: httpx.AsyncClient, settings, token_factory
) -> None:
    token = token_factory(settings)
    if token is not None:
        sesion_client.cookies.set("access_token", token)

    response = await sesion_client.get("/_test/sesion")

    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado"}


async def test_sesion_actual_rechaza_usuario_inexistente_e_inactivo(
    sesion_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    inactivo = await usuario_factory(activo=False)
    for subject in (999_999_999, inactivo.id):
        token = token_manual(
            subject=subject, secret=settings.JWT_SECRET.get_secret_value()
        )
        sesion_client.cookies.set("access_token", token)

        response = await sesion_client.get("/_test/sesion")

        assert response.status_code == 401


@pytest_asyncio.fixture
async def rol_client() -> AsyncIterator[httpx.AsyncClient]:
    """App de prueba con rutas que exigen rol ADMIN."""
    from fastapi import Depends, FastAPI

    from app.core.dependencies import IdentidadActual, requiere_rol
    from main import lifespan

    app = FastAPI(lifespan=lifespan)

    @app.get("/_test/admin")
    async def admin(
        identidad: IdentidadActual = Depends(requiere_rol("ADMIN")),
    ):
        return {"id": identidad.usuario.id, "roles": list(identidad.roles_db)}

    @app.get("/_test/admin-minusculas")
    async def admin_minusculas(
        identidad: IdentidadActual = Depends(requiere_rol("admin")),
    ):
        return {"id": identidad.usuario.id}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client


async def _actualizar_asignacion(
    db_sessionmaker,
    usuario_id: int,
    rol: str,
    **valores,
) -> None:
    from app.modules.usuarios.models import AsignacionRol

    async with db_sessionmaker() as session:
        await session.execute(
            update(AsignacionRol)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.rol == rol,
            )
            .values(**valores)
        )
        await session.commit()


async def test_requiere_rol_permite_un_rol_vigente_de_la_base(
    rol_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=["ADMIN"],
    )
    rol_client.cookies.set("access_token", token)

    response = await rol_client.get("/_test/admin")

    assert response.status_code == 200
    assert response.json() == {"id": usuario.id, "roles": ["ADMIN"]}


async def test_requiere_rol_normaliza_a_mayusculas(
    rol_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    token = token_manual(
        subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value()
    )
    rol_client.cookies.set("access_token", token)

    response = await rol_client.get("/_test/admin-minusculas")

    assert response.status_code == 200


async def test_requiere_rol_deniega_un_rol_revocado_con_la_misma_cookie(
    rol_client: httpx.AsyncClient,
    settings,
    usuario_factory,
    db_sessionmaker,
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=["ADMIN"],
    )
    rol_client.cookies.set("access_token", token)
    assert (await rol_client.get("/_test/admin")).status_code == 200

    await _actualizar_asignacion(
        db_sessionmaker,
        usuario.id,
        "ADMIN",
        revocada_en=datetime.now(timezone.utc),
    )

    response = await rol_client.get("/_test/admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "No autorizado"}


async def test_requiere_rol_deniega_un_rol_vencido(
    rol_client: httpx.AsyncClient,
    settings,
    usuario_factory,
    db_sessionmaker,
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    await _actualizar_asignacion(
        db_sessionmaker,
        usuario.id,
        "ADMIN",
        vence_en=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=["ADMIN"],
    )
    rol_client.cookies.set("access_token", token)

    response = await rol_client.get("/_test/admin")

    assert response.status_code == 403


async def test_requiere_rol_ignora_un_rol_que_solo_declara_el_token(
    rol_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("CLIENTE",))
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=["ADMIN"],
    )
    rol_client.cookies.set("access_token", token)

    response = await rol_client.get("/_test/admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "No autorizado"}
    assert "ADMIN" not in response.text
    assert "CLIENTE" not in response.text


async def test_requiere_rol_acepta_un_rol_de_la_base_ausente_del_token(
    rol_client: httpx.AsyncClient, settings, usuario_factory
) -> None:
    usuario = await usuario_factory(roles=("ADMIN",))
    token = token_manual(
        subject=usuario.id,
        secret=settings.JWT_SECRET.get_secret_value(),
        roles=[],
    )
    rol_client.cookies.set("access_token", token)

    response = await rol_client.get("/_test/admin")

    assert response.status_code == 200
    assert response.json() == {"id": usuario.id, "roles": ["ADMIN"]}


async def test_requiere_rol_sin_roles_falla_al_construir() -> None:
    from app.core.dependencies import requiere_rol

    with pytest.raises(ValueError):
        requiere_rol()
    with pytest.raises(ValueError):
        requiere_rol("", "   ")


async def test_get_usuario_actual_sigue_sin_consultar_roles(
    sesion_client: httpx.AsyncClient,
    settings,
    usuario_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.usuarios.repository import UsuarioRepository

    usuario = await usuario_factory(roles=("ADMIN",))

    async def prohibida(*args, **kwargs):
        raise AssertionError("get_usuario_actual no debe consultar roles")

    monkeypatch.setattr(UsuarioRepository, "roles_vigentes", prohibida)
    token = token_manual(
        subject=usuario.id, secret=settings.JWT_SECRET.get_secret_value()
    )
    sesion_client.cookies.set("access_token", token)

    response = await sesion_client.get("/_test/usuario")

    assert response.status_code == 200
    assert response.json() == {"id": usuario.id, "email": usuario.email}
