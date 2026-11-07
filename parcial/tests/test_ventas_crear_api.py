"""API de POST /ventas con main.app + PostgreSQL real (C-16)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

import httpx
import jwt
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.asyncio

settings = get_settings()


def _token_manual(subject: int, roles: list[str] | None = None) -> str:
    """Firma un JWT de prueba para autenticación por cookie."""
    payload: dict = {
        "sub": str(subject),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=1800),
    }
    if roles is not None:
        payload["roles"] = roles
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm="HS256")


async def _setup_escenario_venta(api_client, db_sessionmaker):
    """Crea vendedor, cliente y libros con stock; retorna ids y token."""
    from app.modules.clientes.models import Cliente
    from app.modules.editoriales.models import Editorial
    from app.modules.libros.models import Libro
    from app.modules.libros.repository import LibroRepository
    from app.modules.usuarios.models import AsignacionRol, Usuario

    async with db_sessionmaker() as session:
        # Editorial
        editorial = Editorial(
            nombre=f"Editorial API {uuid.uuid4().hex}",
            pais="Argentina",
        )
        session.add(editorial)
        await session.flush()
        await session.commit()

        # Vendedor
        vendedor = Usuario(
            email=f"v-api-{uuid.uuid4().hex}@example.com",
            nombre="Vendedor API",
            password_hash="$2b$12$x",
            activo=True,
            debe_cambiar_password=False,
        )
        session.add(vendedor)
        await session.flush()
        session.add(
            AsignacionRol(
                usuario_id=vendedor.id,
                rol="VENDEDOR",
                desde=datetime.now(timezone.utc),
            )
        )
        await session.flush()

        # Cliente
        cliente = Cliente(
            nombre="Cliente API",
            email=f"c-api-{uuid.uuid4().hex}@example.com",
        )
        session.add(cliente)
        await session.flush()

        # Libro con stock sembrado por el punto único (RN-11).
        libro = Libro(
            isbn=f"isbn-api-{uuid.uuid4().hex}",
            titulo="Libro API",
            precio=Decimal("15.00"),
            stock=0,
            editorial_id=editorial.id,
        )
        session.add(libro)
        await session.flush()
        await LibroRepository(session).aplicar_movimiento(
            libro, 10, "Stock inicial", vendedor.id
        )
        await session.commit()

        token = _token_manual(vendedor.id, ["VENDEDOR"])

    return {
        "vendedor_id": vendedor.id,
        "cliente_id": cliente.id,
        "libro_id": libro.id,
        "token": token,
    }


class TestApiVentasCrear:
    async def test_venta_valida_201(self, api_client, db_sessionmaker):
        escenario = await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": escenario["cliente_id"],
                "renglones": [
                    {"libro_id": escenario["libro_id"], "cantidad": 2},
                ],
            },
            cookies={"access_token": escenario["token"]},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["cliente_id"] == escenario["cliente_id"]
        assert float(body["total"]) == 30.00  # 2 * 15.00
        assert len(body["renglones"]) == 1
        assert body["renglones"][0]["libro_id"] == escenario["libro_id"]
        assert body["renglones"][0]["cantidad"] == 2
        assert float(body["renglones"][0]["precio_unitario"]) == 15.00

    async def test_campo_precio_extra_422(self, api_client, db_sessionmaker):
        escenario = await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": escenario["cliente_id"],
                "renglones": [
                    {"libro_id": escenario["libro_id"], "cantidad": 1},
                ],
                "precio": 999.00,
            },
            cookies={"access_token": escenario["token"]},
        )

        assert response.status_code == 422, response.text

    async def test_cero_renglones_422(self, api_client, db_sessionmaker):
        escenario = await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": escenario["cliente_id"],
                "renglones": [],
            },
            cookies={"access_token": escenario["token"]},
        )

        assert response.status_code == 422, response.text

    async def test_sin_sesion_401(self, api_client, db_sessionmaker):
        await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": 1,
                "renglones": [{"libro_id": 1, "cantidad": 1}],
            },
        )

        assert response.status_code == 401, response.text

    async def test_rol_cliente_403(self, api_client, db_sessionmaker):
        async with db_sessionmaker() as session:
            from app.modules.clientes.models import Cliente
            from app.modules.editoriales.models import Editorial
            from app.modules.libros.models import Libro
            from app.modules.libros.repository import LibroRepository
            from app.modules.usuarios.models import AsignacionRol, Usuario

            editorial = Editorial(
                nombre=f"Editorial API 2 {uuid.uuid4().hex}",
                pais="Argentina",
            )
            session.add(editorial)
            await session.flush()

            cliente = Cliente(
                nombre="Cliente API 2",
                email=f"c-api2-{uuid.uuid4().hex}@example.com",
            )
            session.add(cliente)
            await session.flush()

            # Usuario con rol CLIENTE (no VENDEDOR/ADMIN)
            usuario_cliente = Usuario(
                email=f"u-api2-{uuid.uuid4().hex}@example.com",
                nombre="Usuario Cliente",
                password_hash="$2b$12$x",
                activo=True,
                debe_cambiar_password=False,
            )
            session.add(usuario_cliente)
            await session.flush()
            session.add(
                AsignacionRol(
                    usuario_id=usuario_cliente.id,
                    rol="CLIENTE",
                    desde=datetime.now(timezone.utc),
                )
            )

            libro = Libro(
                isbn=f"isbn-api2-{uuid.uuid4().hex}",
                titulo="Libro API 2",
                precio=Decimal("10.00"),
                stock=0,
                editorial_id=editorial.id,
            )
            session.add(libro)
            await session.flush()
            await LibroRepository(session).aplicar_movimiento(
                libro, 5, "Stock inicial", usuario_cliente.id
            )
            await session.commit()

            token = _token_manual(usuario_cliente.id, ["CLIENTE"])

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": cliente.id,
                "renglones": [{"libro_id": libro.id, "cantidad": 1}],
            },
            cookies={"access_token": token},
        )

        assert response.status_code == 403, response.text

    async def test_cliente_inexistente_409(self, api_client, db_sessionmaker):
        escenario = await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": 99999,
                "renglones": [{"libro_id": escenario["libro_id"], "cantidad": 1}],
            },
            cookies={"access_token": escenario["token"]},
        )

        assert response.status_code == 409, response.text

    async def test_stock_insuficiente_409(self, api_client, db_sessionmaker):
        escenario = await _setup_escenario_venta(api_client, db_sessionmaker)

        response = await api_client.post(
            "/ventas/",
            json={
                "cliente_id": escenario["cliente_id"],
                "renglones": [
                    {"libro_id": escenario["libro_id"], "cantidad": 999},
                ],
            },
            cookies={"access_token": escenario["token"]},
        )

        assert response.status_code == 409, response.text
