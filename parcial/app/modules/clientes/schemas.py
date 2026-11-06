from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import SinNulMixin


class ClienteCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: str
    email: str


class ClienteUpdate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = None
    email: Optional[str] = None


class PerfilCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class PerfilRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    cliente_id: int
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class ClienteRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    email: str
    usuario_id: Optional[int] = None


class ClienteDetailRead(ClienteRead):
    perfil: Optional[PerfilRead] = None
