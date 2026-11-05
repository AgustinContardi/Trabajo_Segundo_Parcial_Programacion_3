from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.errors import SinNulMixin


class EditorialCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    pais: str


class EditorialUpdate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    pais: Optional[str] = None


class EditorialRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    pais: str
