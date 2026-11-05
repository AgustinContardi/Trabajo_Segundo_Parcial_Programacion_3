from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.errors import SinNulMixin


class AutorCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    nacionalidad: str


class AutorUpdate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    nacionalidad: Optional[str] = None


class AutorRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    nacionalidad: str
