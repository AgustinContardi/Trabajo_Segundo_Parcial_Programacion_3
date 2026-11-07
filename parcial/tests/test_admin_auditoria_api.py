"""Auditoria de C-15 contra PostgreSQL real (tarea 6.5, CHECKLIST §7).

Dos garantias de `RN-16` que faltaban como evidencia de integracion:

- Alta, asignacion y revocacion dejan tres lineas de `evento_seguridad` con
  `actor` igual al email del admin que las ejecuta.
- Un fallo forzado despues de escribir la auditoria revierte usuario, rol y
  evento: la auditoria vive en la misma transaccion que el cambio.
"""

import uuid

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.modules.usuarios import service
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario
from app.modules.usuarios.schemas import PersonalCreate
from app.modules.usuarios.unit_of_work import AdminUnitOfWork

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"
USUARIOS = "/usuarios/"
EVENTOS = "/eventos/"


def _email(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex}@example.com"


async def _login(
    client: httpx.AsyncClient, email: str, password: str = PASSWORD
) -> None:
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


async def test_alta_asignacion_y_revocacion_auditan_tres_eventos_del_admin(
    api_client: httpx.AsyncClient,
    usuario_factory,
    db_sessionmaker,
) -> None:
    admin = await _admin(api_client, usuario_factory)
    correo = _email("audit")
    usuario_id: int | None = None
    try:
        alta = await api_client.post(
            USUARIOS,
            json={
                "email": correo,
                "nombre": "Persona Auditada",
                "password": PASSWORD,
                "rol": "VENDEDOR",
            },
        )
        assert alta.status_code == 201, alta.text
        usuario_id = alta.json()["id"]

        asignada = await api_client.post(
            f"{USUARIOS}{usuario_id}/roles", json={"rol": "CLIENTE"}
        )
        assert asignada.status_code == 201, asignada.text

        revocada = await api_client.delete(
            f"{USUARIOS}{usuario_id}/roles/CLIENTE"
        )
        assert revocada.status_code == 200, revocada.text

        eventos = await api_client.get(EVENTOS, params={"size": 100})
        assert eventos.status_code == 200, eventos.text
        propios = [
            item
            for item in eventos.json()["items"]
            if item["actor"] == admin.email
        ]
        acciones = [item["accion"] for item in propios]
        assert len(propios) == 3, acciones
        assert any("Alta de personal" in accion for accion in acciones)
        assert any("Asignación de rol: CLIENTE" in accion for accion in acciones)
        assert any("Revocación de rol: CLIENTE" in accion for accion in acciones)
    finally:
        if usuario_id is not None:
            async with db_sessionmaker() as session:
                await session.execute(
                    delete(AsignacionRol).where(
                        AsignacionRol.usuario_id == usuario_id
                    )
                )
                await session.execute(
                    delete(Usuario).where(Usuario.id == usuario_id)
                )
                await session.commit()


async def test_fallo_tras_auditoria_revierte_usuario_rol_y_evento(
    db_sessionmaker,
    usuario_factory,
    settings,
    bcrypt_sem,
) -> None:
    admin = await usuario_factory(password=PASSWORD, roles=("ADMIN",))
    correo = _email("rollback")

    async with db_sessionmaker() as session:
        uow = AdminUnitOfWork(session)
        add_original = uow.eventos.add

        async def add_y_falla(evento: EventoSeguridad) -> EventoSeguridad:
            # La linea se escribe y se hace flush; el fallo ocurre despues, con
            # las tres escrituras ya dentro de la transaccion abierta.
            await add_original(evento)
            raise RuntimeError("fallo forzado despues de la auditoria")

        uow.eventos.add = add_y_falla

        with pytest.raises(RuntimeError):
            await service.alta_personal(
                uow,
                PersonalCreate(
                    email=correo,
                    nombre="Rollback",
                    password=PASSWORD,
                    rol="VENDEDOR",
                ),
                admin=admin,
                settings=settings,
                semaphore=bcrypt_sem,
            )

    async with db_sessionmaker() as session:
        usuarios = await session.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.email == correo)
        )
        eventos = await session.scalar(
            select(func.count())
            .select_from(EventoSeguridad)
            .where(
                EventoSeguridad.actor == admin.email,
                EventoSeguridad.accion == "Alta de personal",
            )
        )

    assert usuarios == 0
    assert eventos == 0
