"""Modelos de tabla del dominio de acceso: usuario, asignacion_rol, intento_acceso, evento_seguridad.

Convenciones (KB §4):
- `usuario` no tiene columna `rol` (los roles viven en `asignacion_rol`).
- `intento_acceso` y `evento_seguridad` no se relacionan con ninguna otra tabla.
- `evento_seguridad.actor` es `text`, no FK.
- La navegación `Usuario.cliente` <-> `Cliente.usuario` se declara en ambos extremos.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente


class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("email", name="uq_usuario_email"),)

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    email: str = Field(sa_column=Column("email", String, nullable=False))
    nombre: str = Field(sa_column=Column("nombre", String, nullable=False))
    password_hash: str = Field(sa_column=Column("password_hash", String, nullable=False))
    activo: bool = Field(
        default=True, sa_column=Column("activo", Boolean, nullable=False)
    )
    debe_cambiar_password: bool = Field(
        default=False, sa_column=Column("debe_cambiar_password", Boolean, nullable=False)
    )

    cliente: Optional["Cliente"] = Relationship(back_populates="usuario")
    asignaciones: List["AsignacionRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]"},
    )


class AsignacionRol(SQLModel, table=True):
    __tablename__ = "asignacion_rol"
    __table_args__ = (
        CheckConstraint(
            "rol IN ('ADMIN','VENDEDOR','CLIENTE')",
            name="ck_asignacion_rol_rol",
        ),
        Index(
            "uq_asignacion_rol_abierta",
            "usuario_id",
            "rol",
            unique=True,
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    usuario_id: int = Field(
        sa_column=Column(
            "usuario_id",
            BigInteger,
            ForeignKey("usuario.id", ondelete="NO ACTION"),
            nullable=False,
            index=True,
        )
    )
    rol: str = Field(sa_column=Column("rol", String, nullable=False))
    desde: datetime = Field(
        sa_column=Column(
            "desde", DateTime(timezone=True), nullable=False, server_default="now()"
        )
    )
    vence_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column("vence_en", DateTime(timezone=True), nullable=True),
    )
    revocada_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column("revocada_en", DateTime(timezone=True), nullable=True),
    )
    otorgada_por: Optional[int] = Field(
        default=None,
        sa_column=Column(
            "otorgada_por",
            BigInteger,
            ForeignKey("usuario.id", ondelete="NO ACTION"),
            nullable=True,
            index=True,
        ),
    )

    usuario: "Usuario" = Relationship(
        back_populates="asignaciones",
        sa_relationship_kwargs={"foreign_keys": "[AsignacionRol.usuario_id]"},
    )


class IntentoAcceso(SQLModel, table=True):
    __tablename__ = "intento_acceso"
    __table_args__ = (
        Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando"),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    cuando: datetime = Field(
        sa_column=Column(
            "cuando", DateTime(timezone=True), nullable=False, server_default="now()"
        )
    )
    email: str = Field(sa_column=Column("email", String, nullable=False))
    ip: str = Field(sa_column=Column("ip", String, nullable=False))
    exito: bool = Field(sa_column=Column("exito", Boolean, nullable=False))


class EventoSeguridad(SQLModel, table=True):
    __tablename__ = "evento_seguridad"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    cuando: datetime = Field(
        sa_column=Column(
            "cuando", DateTime(timezone=True), nullable=False, server_default="now()"
        )
    )
    actor: str = Field(sa_column=Column("actor", Text, nullable=False))
    accion: str = Field(sa_column=Column("accion", String, nullable=False))