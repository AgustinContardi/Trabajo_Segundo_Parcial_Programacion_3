from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.errors import SinNulMixin, validar_password_bytes


class UsuarioCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    email: str
    nombre: str
    password: str

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, value: str) -> str:
        return validar_password_bytes(value)  # type: ignore[return-value]


class UsuarioUpdate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    email: Optional[str] = None
    nombre: Optional[str] = None
    password: Optional[str] = None
    activo: Optional[bool] = None
    debe_cambiar_password: Optional[bool] = None

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, value: Optional[str]) -> Optional[str]:
        return validar_password_bytes(value)


class UsuarioRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool
