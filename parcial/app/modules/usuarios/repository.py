"""Repositorio del módulo `usuarios`.

Lecturas de autenticación (C-11) y alta de la asignación de rol del
auto-registro (C-12). Sólo `flush()` a través de `BaseRepository` (CV-02);
ninguna consulta precarga fuera de este módulo (CV-03). Las ventanas de tiempo
se calculan con el reloj de PostgreSQL (`now()`), no con el reloj del proceso.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select

from app.core.paginacion import Pagina, paginar
from app.core.repository import BaseRepository
from app.modules.usuarios.models import (
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)

# Corte inferior del conteo cuando el par email/IP nunca inició sesión.
_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class AbiertaRol:
    """Asignación abierta de un rol y si aún está vigente según `now()` de la base."""

    asignacion: AsignacionRol
    vigente: bool


@dataclass(frozen=True)
class ResumenFallos:
    """Fallos contabilizables y el más antiguo de ellos (para `Retry-After`)."""

    cantidad: int
    primer_fallo: datetime | None


class UsuarioRepository(BaseRepository[Usuario]):
    """Lecturas de identidad y de roles vigentes."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, Usuario)

    async def get_by_email(self, email: str) -> Usuario | None:
        """Busca un usuario por email (sin distinguir mayúsculas)."""
        stmt = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def roles_vigentes(self, usuario_id: int) -> list[str]:
        """Roles no revocados y no vencidos al momento de emitir el token."""
        stmt = (
            select(AsignacionRol.rol)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.revocada_en.is_(None),
                or_(
                    AsignacionRol.vence_en.is_(None),
                    AsignacionRol.vence_en > func.now(),
                ),
            )
            .order_by(AsignacionRol.rol)
        )
        result = await self._session.execute(stmt)
        return [str(rol) for rol in result.scalars().all()]


class AsignacionRolRepository(BaseRepository[AsignacionRol]):
    """Roles del usuario; alta (`abrir`) y cierre (`cerrar`) sólo `flush()` (CV-02)."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, AsignacionRol)

    async def get_abierta(self, usuario_id: int, rol: str) -> AbiertaRol | None:
        """La fila abierta (`revocada_en IS NULL`) del usuario para ese rol.

        `vigente` se calcula en SQL con el reloj de PostgreSQL:
        `vence_en IS NULL OR vence_en > now()`.
        """
        vigente_expr = (
            (AsignacionRol.vence_en.is_(None))
            | (AsignacionRol.vence_en > func.now())
        ).label("vigente")
        stmt = (
            select(AsignacionRol, vigente_expr)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.rol == rol,
                AsignacionRol.revocada_en.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return AbiertaRol(asignacion=row[0], vigente=bool(row[1]))

    async def listar_por_usuario(self, usuario_id: int) -> list[AsignacionRol]:
        """Todas las asignaciones del usuario, vigentes, vencidas y revocadas,
        ordenadas `desde DESC, id DESC`."""
        stmt = (
            select(AsignacionRol)
            .where(AsignacionRol.usuario_id == usuario_id)
            .order_by(AsignacionRol.desde.desc(), AsignacionRol.id.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def contar_admins_vigentes(
        self, excluir_id: int | None = None, bloquear: bool = False
    ) -> int:
        """Cuenta asignaciones `ADMIN` vigentes (`revocada_en IS NULL` y no
        vencidas al `now()` de la base).

        Con `bloquear=True` emite `SELECT ... FOR UPDATE` sobre **todas** las
        filas vigentes (para serializar revocaciones concurrentes de `ADMIN`);
        la exclusión del objetivo se hace en memoria (§3 del design de C-15).
        Nunca hace `commit()` (CV-02).
        """
        stmt = (
            select(AsignacionRol)
            .where(
                AsignacionRol.rol == "ADMIN",
                AsignacionRol.revocada_en.is_(None),
                or_(
                    AsignacionRol.vence_en.is_(None),
                    AsignacionRol.vence_en > func.now(),
                ),
            )
        )
        if bloquear:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        filas = list(result.scalars().all())
        if excluir_id is not None:
            filas = [f for f in filas if f.id != excluir_id]
        return len(filas)

    async def cerrar(
        self, asignacion: AsignacionRol, cuando: datetime | None = None
    ) -> None:
        """Escribe `revocada_en` (default `now()` del servidor) y hace `flush()`.
        Nunca borra la fila (SU-12).
        """
        asignacion.revocada_en = cuando or datetime.now(timezone.utc)
        await self._session.flush()

    async def abrir(
        self,
        usuario_id: int,
        rol: str,
        *,
        vence_en: datetime | None = None,
        otorgada_por: int | None = None,
    ) -> AsignacionRol:
        """Crea una asignación abierta y hace `flush()` (CV-02)."""
        asignacion = AsignacionRol(
            usuario_id=usuario_id,
            rol=rol,
            desde=datetime.now(timezone.utc),
            vence_en=vence_en,
            revocada_en=None,
            otorgada_por=otorgada_por,
        )
        self._session.add(asignacion)
        await self._session.flush()
        return asignacion


class IntentoAccesoRepository(BaseRepository[IntentoAcceso]):
    """Conteo de fallos que alimenta RN-07."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, IntentoAcceso)

    async def resumen_fallos(
        self, email: str, ip: str, ventana_segundos: int
    ) -> ResumenFallos:
        """Cuenta fallos del par email/IP dentro de la ventana.

        Sólo cuentan los fallos posteriores al último login exitoso del mismo
        par (SU-11) y posteriores a `now() - ventana`. Un email/IP sin éxitos
        previos cuenta todos sus fallos de la ventana.
        """
        ultimo_exito = (
            select(func.max(IntentoAcceso.cuando))
            .where(
                IntentoAcceso.email == email,
                IntentoAcceso.ip == ip,
                IntentoAcceso.exito.is_(True),
            )
            .scalar_subquery()
        )
        ventana = func.make_interval(0, 0, 0, 0, 0, 0, ventana_segundos)

        stmt = select(
            func.count(IntentoAcceso.id),
            func.min(IntentoAcceso.cuando),
        ).where(
            IntentoAcceso.email == email,
            IntentoAcceso.ip == ip,
            IntentoAcceso.exito.is_(False),
            IntentoAcceso.cuando > func.now() - ventana,
            IntentoAcceso.cuando > func.coalesce(ultimo_exito, _EPOCA),
        )
        result = await self._session.execute(stmt)
        cantidad, primer_fallo = result.one()
        return ResumenFallos(cantidad=int(cantidad), primer_fallo=primer_fallo)


class EventoSeguridadRepository(BaseRepository[EventoSeguridad]):
    """Lectura y escritura de eventos de seguridad (RN-16).

    `add()` escribe una línea y hace flush (sin commit: lo confirma el UoW).
    `listado()` devuelve el envoltorio canónico {items, total, page, size, pages}.
    """

    def __init__(self, session: Any) -> None:
        super().__init__(session, EventoSeguridad)

    async def listado(
        self, page: int = 1, size: int = 20
    ) -> Pagina[EventoSeguridad]:
        """Listado paginado de eventos, más recientes primero."""
        stmt = (
            select(EventoSeguridad)
            .order_by(EventoSeguridad.cuando.desc(), EventoSeguridad.id.desc())
        )
        return await paginar(self._session, stmt, page=page, size=size)
