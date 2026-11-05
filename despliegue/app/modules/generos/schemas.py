from typing import Optional

from pydantic import BaseModel, ConfigDict


class GeneroCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str


class GeneroRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str