from datetime import datetime, timezone
from typing import Annotated, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, field_validator

from app.core.errors import SinNulMixin, validar_password_bytes


def _normalizar_email(value: str) -> str:
    """Convención única de email: sin espacios extremos y en minúsculas.

    La comparten el alta (`UsuarioCreate`) y el login (`LoginRequest`) para que
    el valor guardado y el buscado coincidan; no es una regla de negocio nueva.
    """
    return value.strip().lower()


def _fecha_con_zona(value: datetime) -> datetime:
    """Rechaza datetimes sin zona horaria (tipo `AwareDatetime`)."""
    if value.tzinfo is None:
        raise ValueError("La fecha y hora debe incluir zona horaria")
    return value


# Fecha y hora obligatoriamente con zona horaria (timestamptz). Nunca naive.
AwareDatetime = Annotated[datetime, AfterValidator(_fecha_con_zona)]


class UsuarioCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    email: str
    nombre: str
    password: str

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, value: str) -> str:
        return _normalizar_email(value)

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


class LoginRequest(BaseModel, SinNulMixin):
    """Credenciales de acceso; `extra="forbid"` rechaza cualquier otro campo."""

    model_config = ConfigDict(extra="forbid")
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, value: str) -> str:
        return _normalizar_email(value)

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, value: str) -> str:
        return validar_password_bytes(value)  # type: ignore[return-value]


class LoginResponse(BaseModel):
    """Respuesta de login: nunca incluye el token ni el hash."""

    mensaje: str
    debe_cambiar_password: bool
    expira_en_segundos: int


class YoResponse(BaseModel):
    """Identidad actual: roles vigentes de la base y claim informativo del token."""

    usuario: UsuarioRead
    roles: list[str]
    roles_token: list[str]


class CambiarPasswordRequest(BaseModel, SinNulMixin):
    """Contraseña actual + nueva, cada una ≤ 72 bytes (límite de bcrypt)."""

    model_config = ConfigDict(extra="forbid")
    password_actual: str
    password_nueva: str

    @field_validator("password_actual", "password_nueva")
    @classmethod
    def _password_bytes(cls, value: str) -> str:
        return validar_password_bytes(value)  # type: ignore[return-value]


class CambiarPasswordResponse(BaseModel):
    """Respuesta de cambio de contraseña: solo mensaje, sin token ni cookie nueva."""

    mensaje: str


class PersonalCreate(BaseModel, SinNulMixin):
    """Alta de personal: email, nombre, password y rol inicial (ADMIN o VENDEDOR)."""

    model_config = ConfigDict(extra="forbid")
    email: str
    nombre: str
    password: str
    rol: Literal["ADMIN", "VENDEDOR"]

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, value: str) -> str:
        return _normalizar_email(value)

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, value: str) -> str:
        return validar_password_bytes(value)  # type: ignore[return-value]


class AsignacionRolCreate(BaseModel, SinNulMixin):
    """Otorgar un rol: rol (ADMIN/VENDEDOR/CLIENTE) y vence_en opcional con zona y futuro."""

    model_config = ConfigDict(extra="forbid")
    rol: Literal["ADMIN", "VENDEDOR", "CLIENTE"]
    vence_en: AwareDatetime | None = None

    @field_validator("vence_en")
    @classmethod
    def _vence_en_futuro(cls, value: AwareDatetime | None) -> AwareDatetime | None:
        if value is not None and value <= datetime.now(timezone.utc):
            raise ValueError("La fecha de vencimiento debe estar en el futuro")
        return value


class AsignacionRolRead(BaseModel, SinNulMixin):
    """Historial de una asignación de rol (vigente, vencida o revocada)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    usuario_id: int
    rol: str
    desde: datetime
    vence_en: datetime | None = None
    revocada_en: datetime | None = None
    otorgada_por: int | None = None


class EventoSeguridadRead(BaseModel, SinNulMixin):
    """Línea de auditoría de evento de seguridad."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    cuando: datetime
    actor: str
    accion: str
