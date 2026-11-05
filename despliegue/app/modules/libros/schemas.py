from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- autores anidados en un libro ---
class LibroAutorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    autor_id: int
    rol: str
    orden: int = Field(ge=1)


class LibroAutorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    autor_id: int
    rol: str
    orden: int
    autor_nombre: Optional[str] = None


# --- editorial / genero resumidos ---
class EditorialRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    pais: Optional[str] = None


class GeneroRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


# --- libro ---
class LibroCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    isbn: str
    titulo: str
    precio: Decimal = Field(gt=0)
    stock: int = Field(ge=0)
    editorial_id: int
    genero_id: Optional[int] = None
    autores: List[LibroAutorCreate] = Field(default_factory=list)


class LibroUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: Optional[str] = None
    precio: Optional[Decimal] = Field(default=None, gt=0)


class LibroRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    isbn: str
    titulo: str
    precio: Decimal
    stock: int
    editorial_id: int
    genero_id: Optional[int] = None
    editorial: Optional[EditorialRef] = None
    genero: Optional[GeneroRef] = None


class LibroDetailRead(LibroRead):
    autores: List[LibroAutorRead] = Field(default_factory=list)