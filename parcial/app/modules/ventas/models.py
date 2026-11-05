"""Modelos de tabla `venta` y `renglon_venta` (TP cap. 1-4)."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente
    from app.modules.libros.models import Libro


class Venta(SQLModel, table=True):
    __tablename__ = "venta"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_venta_total_no_negativo"),)

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    cliente_id: int = Field(
        sa_column=Column(
            "cliente_id",
            BigInteger,
            ForeignKey("cliente.id", ondelete="NO ACTION"),
            nullable=False,
            index=True,
        )
    )
    fecha: datetime = Field(
        sa_column=Column(
            "fecha", DateTime(timezone=True), nullable=False, server_default="now()"
        )
    )
    total: Decimal = Field(sa_column=Column("total", Numeric(12, 2), nullable=False))

    cliente: "Cliente" = Relationship(back_populates="ventas")
    renglones: List["RenglonVenta"] = Relationship(
        back_populates="venta", cascade_delete=True
    )


class RenglonVenta(SQLModel, table=True):
    __tablename__ = "renglon_venta"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_renglon_venta_cantidad_positiva"),
        CheckConstraint(
            "precio_unitario > 0", name="ck_renglon_venta_precio_unitario_positivo"
        ),
        Index("ix_renglon_venta_venta_id", "venta_id"),
        Index("ix_renglon_venta_libro_id", "libro_id"),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    venta_id: int = Field(
        sa_column=Column(
            "venta_id",
            BigInteger,
            ForeignKey("venta.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    libro_id: int = Field(
        sa_column=Column(
            "libro_id",
            BigInteger,
            ForeignKey("libro.id", ondelete="NO ACTION"),
            nullable=False,
        )
    )
    cantidad: int = Field(sa_column=Column("cantidad", Integer, nullable=False))
    precio_unitario: Decimal = Field(
        sa_column=Column("precio_unitario", Numeric(10, 2), nullable=False)
    )

    venta: "Venta" = Relationship(back_populates="renglones")
    libro: "Libro" = Relationship(back_populates="renglones")