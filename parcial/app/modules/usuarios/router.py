"""Router de autenticación (C-11): login y logout.

El router sólo traduce HTTP: construye el UoW (CV-01), delega en el servicio y
arma la cookie. No decide permisos por rol ni acepta el encabezado Bearer.
"""

from fastapi import APIRouter, Depends, Request, Response

from app.core.dependencies import IdentidadActual, get_sesion_actual
from app.core.security import clear_access_token_cookie, set_access_token_cookie
from app.modules.usuarios import service
from app.modules.usuarios.schemas import (
    LoginRequest,
    LoginResponse,
    UsuarioRead,
    YoResponse,
)
from app.modules.usuarios.unit_of_work import (
    UsuariosUnitOfWork,
    get_usuarios_uow,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _ip_de(request: Request) -> str:
    """IP del cliente; no confía en `X-Forwarded-For` sin proxy configurado."""
    return request.client.host if request.client is not None else "desconocida"


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    uow: UsuariosUnitOfWork = Depends(get_usuarios_uow),
) -> LoginResponse:
    state = request.app.state
    resultado = await service.autenticar(
        uow,
        email=str(data.email),
        password=data.password,
        ip=_ip_de(request),
        sessionmaker=state.sessionmaker,
        settings=state.settings,
        semaphore=state.bcrypt_sem,
        hash_ficticio=state.hash_ficticio,
    )
    set_access_token_cookie(
        response,
        resultado.token,
        max_age=resultado.expira_en_segundos,
        secure=state.settings.COOKIE_SECURE,
    )
    return LoginResponse(
        mensaje="Sesión iniciada",
        debe_cambiar_password=resultado.usuario.debe_cambiar_password,
        expira_en_segundos=resultado.expira_en_segundos,
    )


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Cierra la sesión expirando la cookie; no requiere identidad previa."""
    clear_access_token_cookie(
        response, secure=request.app.state.settings.COOKIE_SECURE
    )
    return {"mensaje": "Sesión cerrada"}


@router.get("/yo", response_model=YoResponse)
async def yo(
    sesion: IdentidadActual = Depends(get_sesion_actual),
) -> YoResponse:
    """Proyecta la identidad ya resuelta; no abre UoW ni emite token."""
    return YoResponse(
        usuario=UsuarioRead.model_validate(sesion.usuario),
        roles=list(sesion.roles_db),
        roles_token=list(sesion.roles_token),
    )
