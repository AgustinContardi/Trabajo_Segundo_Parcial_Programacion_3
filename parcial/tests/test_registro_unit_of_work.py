"""Composición del Unit of Work del auto-registro (C-12, 2.1/2.2).

Sin base: se usa una sesión falsa que imita el contrato mínimo de
`AsyncSession` (`add` + `flush`, sin `commit`) para verificar que el
repositorio de roles sólo hace `flush()` y que el UoW comparte una única sesión
entre sus tres repositorios.
"""

import pytest

from app.core.database import get_session
from app.modules.usuarios.models import AsignacionRol
from app.modules.usuarios.repository import AsignacionRolRepository
from app.modules.usuarios.unit_of_work import RegistroUnitOfWork, get_registro_uow

pytestmark = pytest.mark.asyncio


class _SesionFalsa:
    """Sesión mínima: registra `add`, `flush`, `commit` y `rollback`."""

    def __init__(self) -> None:
        self.agregados: list[object] = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self._siguiente_id = 100

    def add(self, entidad: object) -> None:
        self.agregados.append(entidad)

    async def flush(self) -> None:
        self.flushes += 1
        self._siguiente_id += 1
        self.agregados[-1].id = self._siguiente_id  # type: ignore[attr-defined]

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


async def test_asignacion_rol_repository_hace_flush_y_asigna_id() -> None:
    sesion = _SesionFalsa()
    repositorio = AsignacionRolRepository(sesion)

    asignacion = await repositorio.add(
        AsignacionRol(usuario_id=1, rol="CLIENTE")
    )

    assert asignacion.id is not None
    assert asignacion in sesion.agregados
    assert sesion.flushes == 1
    assert sesion.commits == 0


async def test_registro_uow_comparte_una_sola_sesion_entre_sus_repositorios() -> None:
    sesion = _SesionFalsa()

    uow = RegistroUnitOfWork(sesion)

    assert uow.usuarios._session is sesion
    assert uow.roles._session is sesion
    assert uow.clientes._session is sesion


async def test_registro_uow_confirma_al_salir_sin_excepcion() -> None:
    sesion = _SesionFalsa()
    uow = RegistroUnitOfWork(sesion)

    async with uow:
        pass

    assert sesion.commits == 1
    assert sesion.rollbacks == 0


async def test_registro_uow_revierte_al_salir_con_excepcion() -> None:
    sesion = _SesionFalsa()
    uow = RegistroUnitOfWork(sesion)

    with pytest.raises(RuntimeError):
        async with uow:
            raise RuntimeError("fallo simulado")

    assert sesion.rollbacks == 1
    assert sesion.commits == 0


async def test_get_registro_uow_es_una_dependencia_sobre_get_session() -> None:
    sesion = _SesionFalsa()

    uow = await get_registro_uow(sesion)  # type: ignore[arg-type]

    assert isinstance(uow, RegistroUnitOfWork)
    assert get_registro_uow.__defaults__ is not None
    assert getattr(get_registro_uow.__defaults__[0], "dependency", None) is get_session
