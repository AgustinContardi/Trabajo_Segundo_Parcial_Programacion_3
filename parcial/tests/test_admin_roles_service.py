"""Servicio de roles: asignar, revocar y listar (C-15, tarea 5).

UoW y repositorios falsos en memoria. Verifica el orden `404 → 409 →
RN-05 → escritura`, el cierre + apertura en reasignación de vencido y
`RN-05` (autoprotección y último administrador).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.usuarios import service
from app.modules.usuarios.models import AsignacionRol, Usuario
from app.modules.usuarios.repository import AbiertaRol
from app.modules.usuarios.schemas import AsignacionRolCreate

pytestmark = pytest.mark.asyncio

PASSWORD = "clave-segura-123"


def _data(rol: str = "VENDEDOR", vence_en=None) -> AsignacionRolCreate:
    return AsignacionRolCreate(rol=rol, vence_en=vence_en)


def _admin(usuario_id: int = 999, email: str = "admin@example.com") -> SimpleNamespace:
    return SimpleNamespace(id=usuario_id, email=email, nombre="Admin")


class MundoFalso:
    def __init__(self) -> None:
        self.usuarios: dict[int, Usuario] = {}
        self.asignaciones: list[AsignacionRol] = []
        self.eventos: list = []
        self._siguiente_id = 100
        self.fallar_get_abierta: bool = False

    def siguiente_id(self) -> int:
        self._siguiente_id += 1
        return self._siguiente_id

    def sembrar_usuario(self, usuario_id: int, email: str) -> Usuario:
        u = Usuario(email=email, nombre="U", password_hash="x", activo=True)
        u.id = usuario_id
        self.usuarios[usuario_id] = u
        return u


class _RepoUsuariosFalso:
    def __init__(self, mundo: MundoFalso) -> None:
        self._mundo = mundo

    async def get_by_id(self, usuario_id: int) -> Usuario | None:
        return self._mundo.usuarios.get(usuario_id)


class _RepoRolesFalso:
    def __init__(self, mundo: MundoFalso) -> None:
        self._mundo = mundo

    async def get_abierta(self, usuario_id: int, rol: str) -> AbiertaRol | None:
        for a in self._mundo.asignaciones:
            if (
                a.usuario_id == usuario_id
                and a.rol == rol
                and a.revocada_en is None
            ):
                vigente = a.vence_en is None or a.vence_en > datetime.now(timezone.utc)
                return AbiertaRol(asignacion=a, vigente=vigente)
        return None

    async def listar_por_usuario(self, usuario_id: int) -> list[AsignacionRol]:
        filas = [a for a in self._mundo.asignaciones if a.usuario_id == usuario_id]
        filas.sort(key=lambda a: (a.desde, a.id), reverse=True)
        return filas

    async def contar_admins_vigentes(
        self, excluir_id: int | None = None, bloquear: bool = False
    ) -> int:
        ahora = datetime.now(timezone.utc)
        count = 0
        for a in self._mundo.asignaciones:
            if a.rol == "ADMIN" and a.revocada_en is None:
                if a.vence_en is None or a.vence_en > ahora:
                    if a.id != excluir_id:
                        count += 1
        return count

    async def cerrar(self, asignacion: AsignacionRol) -> None:
        asignacion.revocada_en = datetime.now(timezone.utc)

    async def abrir(
        self,
        usuario_id: int,
        rol: str,
        *,
        vence_en=None,
        otorgada_por=None,
    ) -> AsignacionRol:
        a = AsignacionRol(
            usuario_id=usuario_id,
            rol=rol,
            desde=datetime.now(timezone.utc),
            vence_en=vence_en,
            revocada_en=None,
            otorgada_por=otorgada_por,
        )
        a.id = self._mundo.siguiente_id()
        self._mundo.asignaciones.append(a)
        return a


class _RepoEventosFalso:
    def __init__(self, mundo: MundoFalso) -> None:
        self._mundo = mundo

    async def add(self, evento) -> None:
        self._mundo.eventos.append(evento)


class UoWFalso:
    def __init__(self, mundo: MundoFalso) -> None:
        self.mundo = mundo
        self.usuarios = _RepoUsuariosFalso(mundo)
        self.roles = _RepoRolesFalso(mundo)
        self.eventos = _RepoEventosFalso(mundo)
        self.confirmado = False
        self.revertido = False

    async def __aenter__(self) -> "UoWFalso":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.confirmado = True
        else:
            self.revertido = True
        return False


# --- asignar_rol ---


async def test_asignar_rol_nueva_escribe_fila_con_otorgada_por_y_evento():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    uow = UoWFalso(mundo)

    asignacion = await service.asignar_rol(
        uow, 1, _data("VENDEDOR"), admin=_admin()
    )

    assert asignacion.usuario_id == 1
    assert asignacion.rol == "VENDEDOR"
    assert asignacion.otorgada_por == 999
    assert asignacion.revocada_en is None
    assert len(mundo.asignaciones) == 1
    evento = mundo.eventos[-1]
    assert evento.actor == "admin@example.com"
    assert "VENDEDOR" in evento.accion


async def test_asignar_rol_usuario_inexistente_da_404():
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.asignar_rol(uow, 99999, _data("VENDEDOR"), admin=_admin())

    assert excinfo.value.status_code == 404
    assert len(mundo.asignaciones) == 0
    assert len(mundo.eventos) == 0


async def test_asignar_rol_abierta_vigente_mismo_rol_da_409_sin_escribir():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    mundo.asignaciones.append(
        AsignacionRol(id=101, usuario_id=1, rol="ADMIN",
                      desde=datetime.now(timezone.utc), otorgada_por=999)
    )
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.asignar_rol(uow, 1, _data("ADMIN"), admin=_admin())

    assert excinfo.value.status_code == 409
    assert len(mundo.asignaciones) == 1  # no se agregó nada
    assert len(mundo.eventos) == 0


async def test_asignar_rol_roles_distintos_simultaneos_da_201():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    fila_admin = AsignacionRol(
        usuario_id=1, rol="ADMIN",
        desde=datetime.now(timezone.utc), otorgada_por=999,
    )
    fila_admin.id = mundo.siguiente_id()
    mundo.asignaciones.append(fila_admin)
    uow = UoWFalso(mundo)

    asignacion = await service.asignar_rol(uow, 1, _data("VENDEDOR"), admin=_admin())

    assert asignacion.id is not None
    assert asignacion.rol == "VENDEDOR"
    assert len(mundo.asignaciones) == 2  # la ADMIN original sigue


async def test_asignar_rol_reasigna_vencido_cierra_y_abre_en_una_transaccion():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    anterior = AsignacionRol(
        usuario_id=1, rol="ADMIN",
        desde=datetime.now(timezone.utc) - timedelta(days=2),
        vence_en=datetime.now(timezone.utc) - timedelta(days=1),  # vencida
        revocada_en=None, otorgada_por=999,
    )
    anterior.id = mundo.siguiente_id()
    mundo.asignaciones.append(anterior)
    uow = UoWFalso(mundo)

    nueva = await service.asignar_rol(uow, 1, _data("ADMIN"), admin=_admin())

    assert nueva.id is not None
    assert nueva.id != anterior.id
    assert anterior.revocada_en is not None  # se cerró la anterior
    assert nueva.revocada_en is None
    assert len(mundo.asignaciones) == 2  # historial conservado
    assert len(mundo.eventos) == 1  # una sola línea de evento para la operación


async def test_asignar_rol_reasigna_previamente_revocado_da_201():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    mundo.asignaciones.append(
        AsignacionRol(
            id=101, usuario_id=1, rol="VENDEDOR",
            desde=datetime.now(timezone.utc) - timedelta(days=2),
            revocada_en=datetime.now(timezone.utc),  # ya revocada
            otorgada_por=999,
        )
    )
    uow = UoWFalso(mundo)

    asignacion = await service.asignar_rol(uow, 1, _data("VENDEDOR"), admin=_admin())

    assert asignacion.id is not None
    assert len(mundo.asignaciones) == 2  # la revocada sigue + la nueva


# --- revocar_rol ---


async def test_revocar_rol_escribe_revocada_en_no_borra_la_fila_y_deja_evento():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    fila = AsignacionRol(
        id=101, usuario_id=1, rol="VENDEDOR",
        desde=datetime.now(timezone.utc), otorgada_por=999,
    )
    mundo.asignaciones.append(fila)
    uow = UoWFalso(mundo)

    resultado = await service.revocar_rol(uow, 1, "VENDEDOR", admin=_admin())

    assert resultado.revocada_en is not None
    assert resultado.id == 101
    assert resultado.rol == "VENDEDOR"
    assert len(mundo.asignaciones) == 1  # la fila no se borró
    evento = mundo.eventos[-1]
    assert evento.actor == "admin@example.com"
    assert "VENDEDOR" in evento.accion


async def test_revocar_rol_abierta_vencida_da_200():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    fila = AsignacionRol(
        id=101, usuario_id=1, rol="ADMIN",
        desde=datetime.now(timezone.utc) - timedelta(days=2),
        vence_en=datetime.now(timezone.utc) - timedelta(days=1),  # vencida
        revocada_en=None, otorgada_por=999,
    )
    mundo.asignaciones.append(fila)
    uow = UoWFalso(mundo)

    resultado = await service.revocar_rol(uow, 1, "ADMIN", admin=_admin())

    assert resultado.revocada_en is not None


async def test_revocar_rol_nunca_asignado_da_404():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, 1, "ADMIN", admin=_admin())

    assert excinfo.value.status_code == 404
    assert len(mundo.eventos) == 0


async def test_revocar_rol_usuario_inexistente_da_404():
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, 99999, "ADMIN", admin=_admin())

    assert excinfo.value.status_code == 404


async def test_revocar_rol_ya_revocada_da_409_sin_escribir():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    fila = AsignacionRol(
        id=101, usuario_id=1, rol="ADMIN",
        desde=datetime.now(timezone.utc),
        revocada_en=datetime.now(timezone.utc),  # ya revocada
        otorgada_por=999,
    )
    mundo.asignaciones.append(fila)
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, 1, "ADMIN", admin=_admin())

    assert excinfo.value.status_code == 409
    assert fila.revocada_en is not None  # sin cambios adicionales
    assert len(mundo.eventos) == 0


# --- RN-05: autoprotección y último administrador ---


async def test_rn05_revocar_propio_admin_da_409():
    mundo = MundoFalso()
    admin_id = 50
    mundo.sembrar_usuario(admin_id, "admin@example.com")
    fila = AsignacionRol(
        id=101, usuario_id=admin_id, rol="ADMIN",
        desde=datetime.now(timezone.utc), otorgada_por=1,
    )
    mundo.asignaciones.append(fila)
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, admin_id, "ADMIN", admin=_admin(usuario_id=admin_id))

    assert excinfo.value.status_code == 409
    assert fila.revocada_en is None  # intacta
    assert len(mundo.eventos) == 0


async def test_rn05_revocar_ultimo_admin_vigente_da_409_incluso_otro_admin():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    mundo.sembrar_usuario(2, "admin2@example.com")
    # Un único ADMIN vigente (id 101)
    fila = AsignacionRol(
        id=101, usuario_id=1, rol="ADMIN",
        desde=datetime.now(timezone.utc), otorgada_por=2,
    )
    mundo.asignaciones.append(fila)
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, 1, "ADMIN", admin=_admin(usuario_id=2))

    assert excinfo.value.status_code == 409
    assert fila.revocada_en is None  # intacta
    assert len(mundo.eventos) == 0


async def test_rn05_dos_admins_vigentes_revocar_otro_da_200():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    mundo.sembrar_usuario(2, "admin2@example.com")
    mundo.asignaciones.append(
        AsignacionRol(id=101, usuario_id=1, rol="ADMIN", desde=datetime.now(timezone.utc), otorgada_por=1)
    )
    mundo.asignaciones.append(
        AsignacionRol(id=102, usuario_id=2, rol="ADMIN", desde=datetime.now(timezone.utc), otorgada_por=1)
    )
    uow = UoWFalso(mundo)

    resultado = await service.revocar_rol(uow, 1, "ADMIN", admin=_admin(usuario_id=2))

    assert resultado.revocada_en is not None
    # Queda exactamente un ADMIN vigente (el del admin que hace la revocación)
    vigentes = [a for a in mundo.asignaciones if a.rol == "ADMIN" and a.revocada_en is None]
    assert len(vigentes) == 1


async def test_rn05_admin_vigente_mas_admin_vencido_revocar_vigente_da_409():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    mundo.sembrar_usuario(2, "admin2@example.com")
    mundo.asignaciones.append(
        AsignacionRol(id=101, usuario_id=1, rol="ADMIN", desde=datetime.now(timezone.utc), otorgada_por=1)
    )
    mundo.asignaciones.append(
        AsignacionRol(
            id=102, usuario_id=2, rol="ADMIN", desde=datetime.now(timezone.utc),
            vence_en=datetime.now(timezone.utc) - timedelta(days=1),  # vencido -> no cuenta
            otorgada_por=1,
        )
    )
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.revocar_rol(uow, 1, "ADMIN", admin=_admin(usuario_id=2))

    assert excinfo.value.status_code == 409


# --- listar_roles ---


async def test_listar_roles_historial_completo_ordenado_desc():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    ahora = datetime.now(timezone.utc)
    mundo.asignaciones.append(
        AsignacionRol(id=101, usuario_id=1, rol="VENDEDOR", desde=ahora - timedelta(days=2), otorgada_por=999)
    )
    mundo.asignaciones.append(
        AsignacionRol(id=102, usuario_id=1, rol="ADMIN", desde=ahora - timedelta(days=1), revocada_en=ahora, otorgada_por=999)
    )
    mundo.asignaciones.append(
        AsignacionRol(id=103, usuario_id=1, rol="CLIENTE", desde=ahora, otorgada_por=999)
    )
    uow = UoWFalso(mundo)

    historial = await service.listar_roles(uow, 1)

    assert [a.rol for a in historial] == ["CLIENTE", "ADMIN", "VENDEDOR"]
    assert historial[0].desde >= historial[1].desde >= historial[2].desde


async def test_listar_roles_usuario_inexistente_da_404():
    mundo = MundoFalso()
    uow = UoWFalso(mundo)

    with pytest.raises(HTTPException) as excinfo:
        await service.listar_roles(uow, 99999)

    assert excinfo.value.status_code == 404


async def test_listar_roles_sin_asignaciones_devuelve_lista_vacia():
    mundo = MundoFalso()
    mundo.sembrar_usuario(1, "ana@example.com")
    uow = UoWFalso(mundo)

    assert await service.listar_roles(uow, 1) == []
