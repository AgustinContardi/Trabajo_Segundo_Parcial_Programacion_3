from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.errors import SinNulMixin


class GeneroCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: str


class GeneroUpdate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None


class GeneroRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
