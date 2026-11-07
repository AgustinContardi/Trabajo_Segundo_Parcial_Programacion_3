"""Lógica de negocio del módulo `usuarios`: autenticación (C-11) y registro (C-12).

El servicio recibe el Unit of Work y lo abre con `async with`; nunca una sesión
asincrónica ni construye el UoW (CV-01). La única escritura que no comparte la
transacción de la petición es `intento_acceso` (DD-05).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import traducir_integrity_error
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import (
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.unit_of_work import (
    CambioPasswordUnitOfWork,
    RegistroUnitOfWork,
    UsuariosUnitOfWork,
)

_CREDENCIALES_INVALIDAS = "Credenciales inválidas"
_DEMASIADOS_INTENTOS = "Demasiados intentos de inicio de sesión"


@dataclass(frozen=True)
class ResultadoLogin:
    """Identidad autenticada y token emitido (nunca se serializa el token)."""

    usuario: Usuario
    token: str
    expira_en_segundos: int


def _hash_de_verificacion(usuario: Usuario | None, hash_ficticio: str | bytes) -> str:
    """Usa el hash real si la cuenta existe o el ficticio si no (RN-08)."""
    if usuario is not None:
        return usuario.password_hash
    if isinstance(hash_ficticio, bytes):
        return hash_ficticio.decode("ascii")
    return hash_ficticio


def _retry_after_ms(
    primer_fallo: datetime | None, ventana_segundos: int
) -> int:
    """Milisegundos hasta que el fallo más antiguo salga de la ventana.

    El contrato del proyecto expresa `Retry-After` como un entero decimal en
    milisegundos, sin convertir a segundos.
    """
    tope = max(1, ventana_segundos * 1000)
    if primer_fallo is None:
        return tope
    restante = (
        primer_fallo + timedelta(seconds=ventana_segundos) - datetime.now(timezone.utc)
    ).total_seconds()
    return max(1, min(tope, math.ceil(restante * 1000)))


async def registrar_intento_acceso(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    ip: str,
    exito: bool,
) -> None:
    """Registra un intento de login en su propia sesión y transacción.

    Qué hace distinto: abre una sesión nueva desde `sessionmaker` y confirma
    por sí misma, sin pasar por el Unit of Work de la petición.

    Por qué no puede compartir la transacción: el fallo que alimenta RN-07 es
    justamente el que la transacción del login revierte al responder 401; si se
    escribiera dentro del UoW, la evidencia desaparecería con el error.

    Costo: deja filas aunque la petición falle o el login reviente después
    (DD-05); se acepta porque esas filas son el insumo del límite de intentos.
    """
    async with sessionmaker() as session:
        # `cuando` se escribe explícitamente: el DEFAULT migrado de la tabla es
        # un literal congelado (defecto heredado) y RN-07 necesita la hora real
        # del intento. No requiere migración en C-11.
        session.add(
            IntentoAcceso(
                email=email,
                ip=ip,
                exito=exito,
                cuando=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def autenticar(
    uow: UsuariosUnitOfWork,
    *,
    email: str,
    password: str,
    ip: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    semaphore,
    hash_ficticio: str | bytes,
) -> ResultadoLogin:
    """Autentica credenciales con el orden límite → hash → intento → respuesta."""
    expira_en_segundos = settings.ACCESS_TOKEN_TTL_MIN * 60
    bloqueado = False
    retry_after_ms = 0
    usuario: Usuario | None = None
    roles: list[str] = []

    # Lectura de login en el UoW de la petición (no incluye la auditoría).
    async with uow:
        resumen = await uow.intentos.resumen_fallos(
            email, ip, settings.LOGIN_VENTANA_SEG
        )
        if resumen.cantidad >= settings.LOGIN_MAX_INTENTOS:
            bloqueado = True
            retry_after_ms = _retry_after_ms(
                resumen.primer_fallo, settings.LOGIN_VENTANA_SEG
            )
        else:
            usuario = await uow.usuarios.get_by_email(email)
            if usuario is not None:
                roles = await uow.usuarios.roles_vigentes(usuario.id)

    if bloqueado:
        # El intento limitado también se registra (AB-03 / flujo 2).
        await registrar_intento_acceso(
            sessionmaker, email=email, ip=ip, exito=False
        )
        raise HTTPException(
            status_code=429,
            detail=_DEMASIADOS_INTENTOS,
            headers={"Retry-After": str(retry_after_ms)},
        )

    hash_verificacion = _hash_de_verificacion(usuario, hash_ficticio)
    exito = False
    token: str | None = None
    try:
        coincide = await verify_password(password, hash_verificacion, semaphore)
        if coincide and usuario is not None and usuario.activo:
            token = create_access_token(
                usuario.id,
                roles,
                secret=settings.JWT_SECRET,
                ttl_seconds=expira_en_segundos,
            )
            exito = True
    finally:
        # Se confirma siempre, incluso si bcrypt o la emisión fallan.
        await registrar_intento_acceso(
            sessionmaker, email=email, ip=ip, exito=exito
        )

    if token is None or usuario is None:
        raise HTTPException(
            status_code=401, detail=_CREDENCIALES_INVALIDAS
        )

    return ResultadoLogin(
        usuario=usuario,
        token=token,
        expira_en_segundos=expira_en_segundos,
    )


async def registrar(
    uow: RegistroUnitOfWork,
    data: UsuarioCreate,
    *,
    settings: Settings,
    semaphore,
) -> Usuario:
    """Alta atómica de `RN-02`: usuario + rol `CLIENTE` + ficha de cliente.

    Qué hace distinto: calcula el hash **antes** de abrir el Unit of Work, para
    no retener una conexión de base mientras corre bcrypt, y escribe las tres
    filas dentro de un único `async with`.

    Por qué el `except` va fuera del bloque: si se atrapara adentro, `__aexit__`
    vería una salida normal y confirmaría las filas parciales. Al salir la
    excepción, `__aexit__` ejecuta `rollback()` y recién después se traduce a
    `409`. La ficha va última para que el duplicado de cliente ejercite el
    rollback completo.
    """
    password_hash = await hash_password(
        data.password,
        rounds=settings.BCRYPT_ROUNDS,
        semaphore=semaphore,
    )

    usuario: Usuario
    try:
        async with uow:
            usuario = await uow.usuarios.add(
                Usuario(
                    email=data.email,
                    nombre=data.nombre,
                    password_hash=password_hash,
                )
            )
            await uow.roles.add(
                AsignacionRol(
                    usuario_id=usuario.id,
                    rol="CLIENTE",
                    desde=datetime.now(timezone.utc),
                )
            )
            await uow.clientes.add(
                Cliente(
                    nombre=data.nombre,
                    email=data.email,
                    usuario_id=usuario.id,
                )
            )
    except IntegrityError as exc:
        raise traducir_integrity_error(exc) from exc

    return usuario


async def cambiar_password(
    uow: CambioPasswordUnitOfWork,
    *,
    email: str,
    password_actual: str,
    password_nueva: str,
    settings: Settings,
    semaphore,
) -> None:
    """Cambio de contraseña atómico (RN-16).

    1. Lee el usuario en un UoW corto de lectura.
    2. Verifica la contraseña actual y hashea la nueva **fuera** del UoW
       (bcrypt en to_thread + semáforo), para no retener una conexión del pool.
    3. Dentro de un solo `async with uow`: password_hash,
       debe_cambiar_password = False y una línea de evento_seguridad
       (actor = email). Las tres escrituras se confirman o revierten juntas.
    """
    # 1. Lectura corta: obtener el hash almacenado.
    async with uow:
        usuario = await uow.usuarios.get_by_email(email)
    if usuario is None:
        raise HTTPException(status_code=401, detail=_CREDENCIALES_INVALIDAS)

    # 2. Verificar contraseña actual fuera del UoW (no es login, no escribe
    #    intento_acceso).
    if not await verify_password(password_actual, usuario.password_hash, semaphore):
        raise HTTPException(status_code=401, detail=_CREDENCIALES_INVALIDAS)

    # 3. Hashear nueva contraseña fuera del UoW.
    password_hash = await hash_password(
        password_nueva,
        rounds=settings.BCRYPT_ROUNDS,
        semaphore=semaphore,
    )

    # 4. Tres escrituras en una sola transacción.
    async with uow:
        usuario = await uow.usuarios.get_by_email(email)
        usuario.password_hash = password_hash
        usuario.debe_cambiar_password = False
        await uow.eventos.add(
            EventoSeguridad(actor=email, accion="Cambio de contraseña")
        )


async def alta_personal(
    uow,
    data,
    *,
    admin,
    settings: Settings,
    semaphore,
) -> Usuario:
    """Alta atómica de personal (RN-02 adaptado, SU-02, RN-16).

    1. Hashea la contraseña **antes** de abrir el UoW (bcrypt en to_thread +
       semáforo), para no retener una conexión del pool.
    2. Dentro de un solo `async with uow`: `usuario` con
       `debe_cambiar_password = true`, `asignacion_rol` inicial con
       `otorgada_por = admin.id` y una línea de `evento_seguridad` con
       `actor = admin.email` y `accion = "Alta de personal"`.
    3. Cualquier fallo revierte las tres escrituras (el `except` va fuera del
       bloque para que `__aexit__` haga `rollback()`).
    """
    password_hash = await hash_password(
        data.password,
        rounds=settings.BCRYPT_ROUNDS,
        semaphore=semaphore,
    )

    try:
        async with uow:
            usuario = await uow.usuarios.add(
                Usuario(
                    email=data.email,
                    nombre=data.nombre,
                    password_hash=password_hash,
                    debe_cambiar_password=True,
                )
            )
            await uow.roles.add(
                AsignacionRol(
                    usuario_id=usuario.id,
                    rol=data.rol,
                    desde=datetime.now(timezone.utc),
                    otorgada_por=admin.id,
                )
            )
            await uow.eventos.add(
                EventoSeguridad(actor=admin.email, accion="Alta de personal")
            )
    except IntegrityError as exc:
        raise traducir_integrity_error(exc) from exc

    return usuario


_USUARIO_NO_EXISTE = "El usuario indicado no existe"
_ROL_YA_ABIERTO = "El usuario ya tiene una asignación abierta de ese rol"
_ROL_NO_ASIGNADO = "El usuario no tiene ese rol asignado"
_ROL_YA_REVOCADO = "Ese rol ya está revocado para ese usuario"
_NO_PUEDE_PROPIO_ADMIN = "No puede revocar su propio rol de administrador"
_ULTIMO_ADMIN = "No se puede revocar el último administrador vigente"


async def asignar_rol(uow, usuario_id, data, *, admin) -> AsignacionRol:
    """Otorgar un rol con vigencia opcional.

    Orden: `404` (usuario inexistente) → `409` (asignación abierta vigente del
    mismo rol) → si existe pero vencida, `cerrar` + `flush` y `abrir` nueva en
    la misma transacción → `abrir`. Siempre escribe una línea de evento.
    """
    try:
        async with uow:
            usuario = await uow.usuarios.get_by_id(usuario_id)
            if usuario is None:
                raise HTTPException(status_code=404, detail=_USUARIO_NO_EXISTE)

            abierta = await uow.roles.get_abierta(usuario_id, data.rol)
            if abierta is not None and abierta.vigente:
                raise HTTPException(status_code=409, detail=_ROL_YA_ABIERTO)

            if abierta is not None and not abierta.vigente:
                # Reasignar rol vencido: cierra la fila anterior y abre la nueva.
                await uow.roles.cerrar(abierta.asignacion)

            asignacion = await uow.roles.abrir(
                usuario_id,
                data.rol,
                vence_en=data.vence_en,
                otorgada_por=admin.id,
            )
            await uow.eventos.add(
                EventoSeguridad(actor=admin.email, accion=f"Asignación de rol: {data.rol}")
            )
            return asignacion
    except IntegrityError as exc:
        raise traducir_integrity_error(exc) from exc


async def revocar_rol(uow, usuario_id, rol: str, *, admin) -> AsignacionRol:
    """Revocar un rol escribiendo `revocada_en` (nunca borra la fila).

    Orden (`CV-08`): `404` (usuario inexistente) → `404` (rol nunca asignado)
    / `409` (fila ya revocada) → `409` (autoprotección propio ADMIN) →
    `409` (último ADMIN vigente) → escritura.
    """
    try:
        async with uow:
            usuario = await uow.usuarios.get_by_id(usuario_id)
            if usuario is None:
                raise HTTPException(status_code=404, detail=_USUARIO_NO_EXISTE)

            abierta = await uow.roles.get_abierta(usuario_id, rol)
            if abierta is None:
                filas = await uow.roles.listar_por_usuario(usuario_id)
                if not any(f.rol == rol for f in filas):
                    raise HTTPException(status_code=404, detail=_ROL_NO_ASIGNADO)
                raise HTTPException(status_code=409, detail=_ROL_YA_REVOCADO)

            asignacion = abierta.asignacion

            if usuario_id == admin.id and rol == "ADMIN":
                raise HTTPException(status_code=409, detail=_NO_PUEDE_PROPIO_ADMIN)

            if rol == "ADMIN" and abierta.vigente:
                # Solo una asignación ADMIN vigente reduce el conteo de administradores.
                # Revocar una ya vencida no deja al sistema sin administradores.
                if await uow.roles.contar_admins_vigentes(
                    excluir_id=asignacion.id, bloquear=True
                ) == 0:
                    raise HTTPException(status_code=409, detail=_ULTIMO_ADMIN)

            await uow.roles.cerrar(asignacion)
            await uow.eventos.add(
                EventoSeguridad(actor=admin.email, accion=f"Revocación de rol: {rol}")
            )
            return asignacion
    except IntegrityError as exc:
        raise traducir_integrity_error(exc) from exc


async def listar_roles(uow, usuario_id) -> list[AsignacionRol]:
    """Historial completo de roles de un usuario: vigentes, vencidas y revocadas,
    ordenadas `desde DESC, id DESC`. `404` si el usuario no existe."""
    usuario = await uow.usuarios.get_by_id(usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail=_USUARIO_NO_EXISTE)
    return await uow.roles.listar_por_usuario(usuario_id)
