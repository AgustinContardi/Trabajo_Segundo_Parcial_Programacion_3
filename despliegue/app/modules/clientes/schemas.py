from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

class ClienteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    email: str


class ClienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    email: Optional[str] = None


class PerfilCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class PerfilRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: str


class ClienteDetailRead(ClienteRead):
    perfil: Optional[PerfilRead] = None