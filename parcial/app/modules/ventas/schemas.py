from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import SinNulMixin

# Cotas de las columnas: `bigint` para las FK y `integer` para `cantidad`.
# `strict=True` evita la coerción de booleanos, strings y floats (RN-09, RN-15).
BIGINT_MAX = 2**63 - 1
INT_MAX = 2**31 - 1

ClienteId = Annotated[int, Field(strict=True, ge=1, le=BIGINT_MAX)]
LibroId = Annotated[int, Field(strict=True, ge=1, le=BIGINT_MAX)]
Cantidad = Annotated[int, Field(strict=True, ge=1, le=INT_MAX)]


class RenglonCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    libro_id: LibroId
    cantidad: Cantidad


class VentaCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    cliente_id: ClienteId
    renglones: List[RenglonCreate] = Field(min_length=1)


class RenglonRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    venta_id: int
    libro_id: int
    cantidad: int
    precio_unitario: Decimal
    titulo: Optional[str] = None
    subtotal: Optional[Decimal] = None


class ClienteRef(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    nombre: str
    email: str


class VentaRead(BaseModel, SinNulMixin):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    cliente_id: int
    fecha: datetime
    total: Decimal
    cliente: Optional[ClienteRef] = None


class VentaDetailRead(VentaRead):
    renglones: List[RenglonRead] = Field(default_factory=list)
