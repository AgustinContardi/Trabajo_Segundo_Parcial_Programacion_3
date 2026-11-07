"""Tests de schemas de administración (C-15) — sin base de datos."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.modules.usuarios.schemas import (
    AsignacionRolCreate,
    AsignacionRolRead,
    EventoSeguridadRead,
    PersonalCreate,
)


class TestPersonalCreate:
    def test_valido_admin(self):
        data = PersonalCreate(
            email="ana@libreria.com",
            nombre="Ana Pérez",
            password="ClaveSegura123",
            rol="ADMIN",
        )
        assert data.email == "ana@libreria.com"
        assert data.nombre == "Ana Pérez"
        assert data.rol == "ADMIN"

    def test_valido_vendedor(self):
        data = PersonalCreate(
            email="juan@libreria.com",
            nombre="Juan Gómez",
            password="OtraClave456",
            rol="VENDEDOR",
        )
        assert data.rol == "VENDEDOR"

    def test_rol_invalido(self):
        with pytest.raises(ValidationError):
            PersonalCreate(
                email="x@y.com",
                nombre="X",
                password="Clave123",
                rol="CLIENTE",
            )

    def test_campo_extra(self):
        with pytest.raises(ValidationError):
            PersonalCreate(
                email="x@y.com",
                nombre="X",
                password="Clave123",
                rol="ADMIN",
                campo_extra="no",
            )

    def test_password_73_bytes(self):
        with pytest.raises(ValidationError):
            PersonalCreate(
                email="x@y.com",
                nombre="X",
                password="ñ" * 40,  # 40 chars × 2 bytes = 80 bytes > 72
                rol="ADMIN",
            )

    def test_password_72_bytes_ok(self):
        data = PersonalCreate(
            email="x@y.com",
            nombre="X",
            password="a" * 72,
            rol="ADMIN",
        )
        assert data.password == "a" * 72

    def test_email_normalizado(self):
        data = PersonalCreate(
            email="  ANA@Libreria.COM  ",
            nombre="Ana",
            password="Clave123",
            rol="VENDEDOR",
        )
        assert data.email == "ana@libreria.com"


class TestAsignacionRolCreate:
    def test_valido_sin_vence(self):
        data = AsignacionRolCreate(rol="ADMIN")
        assert data.rol == "ADMIN"
        assert data.vence_en is None

    def test_valido_futuro(self):
        futuro = datetime.now(timezone.utc) + timedelta(days=30)
        data = AsignacionRolCreate(rol="VENDEDOR", vence_en=futuro)
        assert data.vence_en == futuro

    def test_vence_en_pasado(self):
        pasado = datetime.now(timezone.utc) - timedelta(days=1)
        with pytest.raises(ValidationError):
            AsignacionRolCreate(rol="ADMIN", vence_en=pasado)

    def test_vence_en_sin_zona(self):
        naive = datetime.now() + timedelta(days=1)
        with pytest.raises(ValidationError):
            AsignacionRolCreate(rol="ADMIN", vence_en=naive)

    def test_rol_invalido(self):
        with pytest.raises(ValidationError):
            AsignacionRolCreate(rol="SUPERADMIN")

    def test_campo_extra(self):
        with pytest.raises(ValidationError):
            AsignacionRolCreate(rol="ADMIN", campo_extra="no")


class TestAsignacionRolRead:
    def test_from_attributes(self):
        data = AsignacionRolRead(
            id=1,
            usuario_id=5,
            rol="ADMIN",
            desde=datetime.now(timezone.utc),
            vence_en=None,
            revocada_en=None,
            otorgada_por=2,
        )
        assert data.id == 1
        assert data.rol == "ADMIN"


class TestEventoSeguridadRead:
    def test_from_attributes(self):
        data = EventoSeguridadRead(
            id=1,
            cuando=datetime.now(timezone.utc),
            actor="admin@libreria.com",
            accion="Alta de personal",
        )
        assert data.actor == "admin@libreria.com"
        assert data.accion == "Alta de personal"
