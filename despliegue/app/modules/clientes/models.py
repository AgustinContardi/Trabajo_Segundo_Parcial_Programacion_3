"""Modelos de tabla `cliente` y `perfil_cliente` (TP cap. 1-4)."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, Integer, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.ventas.models import Venta


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"
    __table_args__ = (UniqueConstraint("email", name="uq_cliente_email"),)

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    nombre: str = Field(sa_column=Column("nombre", String, nullable=False))
    email: str = Field(sa_column=Column("email", String, nullable=False))

    perfil: Optional["PerfilCliente"] = Relationship(back_populates="cliente")
    ventas: List["Venta"] = Relationship(back_populates="cliente")


class PerfilCliente(SQLModel, table=True):
    __tablename__ = "perfil_cliente"
    __table_args__ = (UniqueConstraint("cliente_id", name="uq_perfil_cliente_cliente_id"),)

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    cliente_id: int = Field(
        sa_column=Column(
            "cliente_id",
            BigInteger,
            ForeignKey("cliente.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    telefono: Optional[str] = Field(
        default=None, sa_column=Column("telefono", String, nullable=True)
    )
    direccion: Optional[str] = Field(
        default=None, sa_column=Column("direccion", String, nullable=True)
    )

    cliente: "Cliente" = Relationship(back_populates="perfil")