"""Modelo de tabla `autor` (TP cap. 1-4)."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Column, Identity, String
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.libros.models import LibroAutor


class Autor(SQLModel, table=True):
    __tablename__ = "autor"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    nombre: str = Field(sa_column=Column("nombre", String, nullable=False))
    nacionalidad: str = Field(sa_column=Column("nacionalidad", String, nullable=False))

    autorias: List["LibroAutor"] = Relationship(back_populates="autor")