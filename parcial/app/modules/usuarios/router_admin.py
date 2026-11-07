"""Rutas de administración de usuarios, roles y eventos (C-15).

El router **construye el UoW** (CV-01) y delega en el servicio; no hay lógica
de negocio aquí. Se monta en el **grupo protegido** de `main.py`, por lo que
`control_cambio_password` (montado una sola vez a nivel de ese router) y
`requiere_rol("ADMIN")` se aplican a todas las rutas.
"""

from fastapi import APIRouter, Depends, Path, Query, Request

from app.core.dependencies import IdentidadActual, requiere_rol
from app.core.paginacion import Pagina
from app.modules.usuarios import service
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad
from app.modules.usuarios.schemas import (
    AsignacionRolCreate,
    AsignacionRolRead,
    EventoSeguridadRead,
    PersonalCreate,
    UsuarioRead,
)
from app.modules.usuarios.unit_of_work import AdminUnitOfWork, get_admin_uow

_solo_admin = requiere_rol("ADMIN")

router_usuarios = APIRouter(prefix="/usuarios", tags=["usuarios"])
router_eventos = APIRouter(prefix="/eventos", tags=["eventos"])


@router_usuarios.post(
    "/", response_model=UsuarioRead, status_code=201
)
async def alta_personal(
    data: PersonalCreate,
    request: Request,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AdminUnitOfWork = Depends(get_admin_uow),
) -> UsuarioRead:
    """Alta de personal con contraseña provisoria (SU-02, RN-16)."""
    admin = _sesion.usuario
    usuario = await service.alta_personal(
        uow,
        data,
        admin=admin,
        settings=request.app.state.settings,
        semaphore=request.app.state.bcrypt_sem,
    )
    return UsuarioRead.model_validate(usuario)


@router_usuarios.post(
    "/{usuario_id}/roles",
    response_model=AsignacionRolRead,
    status_code=201,
)
async def asignar_rol(
    usuario_id: int,
    data: AsignacionRolCreate,
    request: Request,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AdminUnitOfWork = Depends(get_admin_uow),
) -> AsignacionRolRead:
    """Otorgar un rol con vigencia opcional (RN-03, RN-16)."""
    admin = _sesion.usuario
    asignacion = await service.asignar_rol(uow, usuario_id, data, admin=admin)
    return AsignacionRolRead.model_validate(asignacion)


@router_usuarios.delete(
    "/{usuario_id}/roles/{rol}",
    response_model=AsignacionRolRead,
)
async def revocar_rol(
    usuario_id: int,
    request: Request,
    rol: str = Path(..., pattern="^(ADMIN|VENDEDOR|CLIENTE)$"),
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AdminUnitOfWork = Depends(get_admin_uow),
) -> AsignacionRolRead:
    """Revocar un rol escribiendo `revocada_en` (nunca borra la fila; RN-05)."""
    admin = _sesion.usuario
    asignacion = await service.revocar_rol(uow, usuario_id, rol, admin=admin)
    return AsignacionRolRead.model_validate(asignacion)


@router_usuarios.get(
    "/{usuario_id}/roles", response_model=list[AsignacionRolRead]
)
async def listar_roles(
    usuario_id: int,
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AdminUnitOfWork = Depends(get_admin_uow),
) -> list[AsignacionRolRead]:
    """Historial completo de roles de un usuario (vigentes, vencidas, revocadas)."""
    asignaciones = await service.listar_roles(uow, usuario_id)
    return [AsignacionRolRead.model_validate(a) for a in asignaciones]


@router_eventos.get("/", response_model=Pagina[EventoSeguridadRead])
async def listar_eventos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _sesion: IdentidadActual = Depends(_solo_admin),
    uow: AdminUnitOfWork = Depends(get_admin_uow),
) -> Pagina[EventoSeguridadRead]:
    """Historial paginado de eventos de seguridad (DD-18, RN-16)."""
    pagina = await uow.eventos.listado(page=page, size=size)
    return Pagina(
        items=[
            EventoSeguridadRead.model_validate(item) for item in pagina.items
        ],
        total=pagina.total,
        page=pagina.page,
        size=pagina.size,
        pages=pagina.pages,
    )
