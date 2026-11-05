from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EditorialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    pais: str


class EditorialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    pais: Optional[str] = None


class EditorialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    pais: str