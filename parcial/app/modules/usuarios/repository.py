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

from app.core.repository import BaseRepository
from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario

# Corte inferior del conteo cuando el par email/IP nunca inició sesión.
_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


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
    """Roles del usuario; el alta sólo usa `add()` heredado (`flush()`, CV-02)."""

    def __init__(self, session: Any) -> None:
        super().__init__(session, AsignacionRol)


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
