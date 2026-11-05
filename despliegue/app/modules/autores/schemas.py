from typing import Optional

from pydantic import BaseModel, ConfigDict


class AutorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    nacionalidad: str


class AutorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    nacionalidad: Optional[str] = None


class AutorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    nacionalidad: str