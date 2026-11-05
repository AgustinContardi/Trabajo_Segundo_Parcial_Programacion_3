"""Modelos de tabla `libro` y `libro_autor` (TP cap. 1-4)."""

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
    UniqueConstraint,
)
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.editoriales.models import Editorial
    from app.modules.generos.models import Genero
    from app.modules.ventas.models import RenglonVenta


class Libro(SQLModel, table=True):
    __tablename__ = "libro"
    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_libro_precio_positivo"),
        CheckConstraint("stock >= 0", name="ck_libro_stock_no_negativo"),
        UniqueConstraint("isbn", name="uq_libro_isbn"),
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

    editorial: Optional["Editorial"] = Relationship(back_populates="libros")
    genero: Optional["Genero"] = Relationship(back_populates="libros")
    autorias: List["LibroAutor"] = Relationship(back_populates="libro")
    renglones: List["RenglonVenta"] = Relationship(back_populates="libro")


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