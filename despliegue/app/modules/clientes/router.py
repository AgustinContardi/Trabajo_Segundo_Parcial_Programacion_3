from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.clientes import service
from app.modules.clientes.schemas import (
    ClienteCreate,
    ClienteDetailRead,
    ClienteRead,
    ClienteUpdate,
    PerfilCreate,
    PerfilRead,
)
from app.modules.ventas.schemas import ClienteRef, VentaRead
from app.modules.ventas import service as ventas_service

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.post("/", response_model=ClienteRead, status_code=201)
async def crear_cliente(data: ClienteCreate, session: AsyncSession = Depends(get_session)):
    obj = await service.crear(session, data.nombre, data.email)
    await session.commit()
    return obj


@router.get("/{cliente_id}", response_model=ClienteDetailRead)
async def obtener_cliente(cliente_id: int, session: AsyncSession = Depends(get_session)):
    obj = await service.obtener(session, cliente_id)
    return ClienteDetailRead(
        id=obj.id,
        nombre=obj.nombre,
        email=obj.email,
        perfil=(
            PerfilRead(
                id=obj.perfil.id,
                cliente_id=obj.perfil.cliente_id,
                telefono=obj.perfil.telefono,
                direccion=obj.perfil.direccion,
            )
            if obj.perfil is not None
            else None
        ),
    )


@router.patch("/{cliente_id}", response_model=ClienteDetailRead)
async def actualizar_cliente(
    cliente_id: int, data: ClienteUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await service.actualizar(session, cliente_id, data.nombre, data.email)
    await session.commit()
    obj = await service.obtener(session, obj.id)
    return ClienteDetailRead(
        id=obj.id,
        nombre=obj.nombre,
        email=obj.email,
        perfil=(
            PerfilRead(
                id=obj.perfil.id,
                cliente_id=obj.perfil.cliente_id,
                telefono=obj.perfil.telefono,
                direccion=obj.perfil.direccion,
            )
            if obj.perfil is not None
            else None
        ),
    )


@router.post("/{cliente_id}/perfil", response_model=PerfilRead, status_code=201)
async def crear_perfil(
    cliente_id: int, data: PerfilCreate, session: AsyncSession = Depends(get_session)
):
    obj = await service.crear_perfil(session, cliente_id, data.telefono, data.direccion)
    await session.commit()
    return obj


@router.get("/{cliente_id}/ventas", response_model=list[VentaRead])
async def ventas_de_cliente(cliente_id: int, session: AsyncSession = Depends(get_session)):
    ventas = await ventas_service.ventas_de_cliente(session, cliente_id)
    # attach cliente ref
    cliente = await service.obtener(session, cliente_id)
    result = []
    for v in ventas:
        result.append(
            VentaRead(
                id=v.id,
                cliente_id=v.cliente_id,
                fecha=v.fecha,
                total=v.total,
                cliente=ClienteRef(id=cliente.id, nombre=cliente.nombre, email=cliente.email),
            )
        )
    return result