"""Modelo de tabla `genero` (TP cap. 1-4)."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Column, Identity, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.libros.models import Libro


class Genero(SQLModel, table=True):
    __tablename__ = "genero"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(), primary_key=True),
    )
    nombre: str = Field(sa_column=Column("nombre", String, nullable=False, unique=True))

    libros: List["Libro"] = Relationship(back_populates="genero")