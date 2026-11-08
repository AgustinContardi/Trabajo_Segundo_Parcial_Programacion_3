"""Modelos de tabla `libro`, `libro_autor` (TP cap. 1-4) y `movimiento_stock` (parcial)."""

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
from sqlalchemy.sql import text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.editoriales.models import Editorial
    from app.modules.generos.models import Genero
    from app.modules.usuarios.models import Usuario
    from app.modules.ventas.models import RenglonVenta, Venta


class Libro(SQLModel, table=True):
    __tablename__ = "libro"
    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_libro_precio_positivo"),
        CheckConstraint("stock >= 0", name="ck_libro_stock_no_negativo"),
        Index(
            "uq_libro_isbn_vigente",
            "isbn",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    isbn: str = Field(sa_column=Column("isbn", String, nullable=False))
    titulo: str = Field(sa_column=Column("titulo", String, nullable=False))
    precio: Decimal = Field(sa_column=Column("precio", Numeric(10, 2), nullable=False))
    stock: int = Field(sa_column=Column("stock", Integer, nullable=False))
    editorial_id: int = Field(
        sa_column=Column(
            "editorial_id",
            BigInteger,
            ForeignKey("editorial.id", ondelete="NO ACTION"),
            nullable=False,
            index=True,
        )
    )
    genero_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            "genero_id",
            BigInteger,
            ForeignKey("genero.id", ondelete="NO ACTION"),
            nullable=True,
            index=True,
        ),
    )
    borrado_en: Optional[datetime] = Field(
        default=None,
        sa_column=Column("borrado_en", DateTime(timezone=True), nullable=True),
    )

    editorial: Optional["Editorial"] = Relationship(back_populates="libros")
    genero: Optional["Genero"] = Relationship(back_populates="libros")
    autorias: List["LibroAutor"] = Relationship(back_populates="libro")
    renglones: List["RenglonVenta"] = Relationship(back_populates="libro")
    movimientos: List["MovimientoStock"] = Relationship(back_populates="libro")


class LibroAutor(SQLModel, table=True):
    __tablename__ = "libro_autor"
    __table_args__ = (
        CheckConstraint(
            "rol IN ('autor','coautor','traductor','ilustrador')",
            name="ck_libro_autor_rol",
        ),
        CheckConstraint("orden >= 1", name="ck_libro_autor_orden"),
        Index("ix_libro_autor_libro_id", "libro_id"),
        Index("ix_libro_autor_autor_id", "autor_id"),
    )

    libro_id: int = Field(
        sa_column=Column(
            "libro_id",
            BigInteger,
            ForeignKey("libro.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    autor_id: int = Field(
        sa_column=Column(
            "autor_id",
            BigInteger,
            ForeignKey("autor.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    rol: str = Field(sa_column=Column("rol", String, nullable=False))
    orden: int = Field(sa_column=Column("orden", Integer, nullable=False))

    libro: "Libro" = Relationship(back_populates="autorias")
    autor: "Autor" = Relationship(back_populates="autorias")


class MovimientoStock(SQLModel, table=True):
    __tablename__ = "movimiento_stock"
    __table_args__ = (
        CheckConstraint(
            "cantidad <> 0", name="ck_movimiento_stock_cantidad_no_cero"
        ),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    libro_id: int = Field(
        sa_column=Column(
            "libro_id",
            BigInteger,
            ForeignKey("libro.id", ondelete="NO ACTION"),
            nullable=False,
            index=True,
        )
    )
    venta_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            "venta_id",
            BigInteger,
            ForeignKey("venta.id", ondelete="NO ACTION"),
            nullable=True,
            index=True,
        ),
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
    cantidad: int = Field(sa_column=Column("cantidad", Integer, nullable=False))
    motivo: str = Field(sa_column=Column("motivo", String, nullable=False))
    cuando: datetime = Field(
        sa_column=Column(
            "cuando", DateTime(timezone=True), nullable=False, server_default=text("now()")
        )
    )

    libro: "Libro" = Relationship(back_populates="movimientos")
    venta: Optional["Venta"] = Relationship()
    usuario: Optional["Usuario"] = Relationship()