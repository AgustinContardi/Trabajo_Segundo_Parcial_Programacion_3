from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RenglonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    libro_id: int
    cantidad: int = Field(gt=0)


class VentaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: int
    renglones: List[RenglonCreate] = Field(min_length=1)


class RenglonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    venta_id: int
    libro_id: int
    cantidad: int
    precio_unitario: Decimal
    titulo: Optional[str] = None
    subtotal: Optional[Decimal] = None


class ClienteRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: str


class VentaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    fecha: datetime
    total: Decimal
    cliente: Optional[ClienteRef] = None


class VentaDetailRead(VentaRead):
    renglones: List[RenglonRead] = Field(default_factory=list)