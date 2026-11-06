"""Unit of Work del módulo `usuarios`.

- `UsuariosUnitOfWork` (C-11) compone el login: usuarios + intentos.
- `RegistroUnitOfWork` (C-12) compone el auto-registro de RN-02: usuario, rol
  `CLIENTE` y ficha de cliente sobre una única sesión y una única transacción.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    IntentoAccesoRepository,
    UsuarioRepository,
)


class UsuariosUnitOfWork(UnitOfWork):
    """Compone los repositorios de autenticación con una sola sesión."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.usuarios = UsuarioRepository(session)
        self.intentos = IntentoAccesoRepository(session)


class RegistroUnitOfWork(UnitOfWork):
    """Compone las tres escrituras de `RN-02` con una única sesión."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.usuarios = UsuarioRepository(session)
        self.roles = AsignacionRolRepository(session)
        self.clientes = ClienteRepository(session)


async def get_usuarios_uow(
    session: AsyncSession = Depends(get_session),
) -> UsuariosUnitOfWork:
    return UsuariosUnitOfWork(session)


async def get_registro_uow(
    session: AsyncSession = Depends(get_session),
) -> RegistroUnitOfWork:
    return RegistroUnitOfWork(session)
