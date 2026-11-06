"""Dobles en memoria del auto-registro (C-12).

No hay base ni `Settings` reales: `MundoFalso` guarda las filas que los
repositorios falsos escribirían, impone las unicidades que la base impone
(`uq_usuario_email`, `uq_cliente_email`, `uq_asignacion_rol_abierta`) y permite
simular el fallo de cualquier escritura. `UoWFalso` reproduce la semántica del
`UnitOfWork` real: confirma al salir sin excepción y revierte al salir con una.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, Usuario


def error_de_unicidad(constraint: str) -> IntegrityError:
    """Imita el `IntegrityError` de asyncpg con el nombre del constraint."""
    original = Exception(
        f'duplicate key value violates unique constraint "{constraint}"'
    )
    return IntegrityError(
        'INSERT INTO tabla VALUES (...)', {}, original
    )


class MundoFalso:
    """Filas en memoria y control de fallos por tabla."""

    def __init__(self) -> None:
        self.usuarios: list[Usuario] = []
        self.asignaciones: list[AsignacionRol] = []
        self.clientes: list[Cliente] = []
        self.fallar_roles: str | None = None
        self.fallar_clientes: str | None = None
        self._siguiente_id = 100
        self._instantanea: tuple[list, list, list] | None = None

    def siguiente_id(self) -> int:
        self._siguiente_id += 1
        return self._siguiente_id

    def abrir_transaccion(self) -> None:
        self._instantanea = (
            list(self.usuarios),
            list(self.asignaciones),
            list(self.clientes),
        )

    def revertir(self) -> None:
        assert self._instantanea is not None
        self.usuarios = list(self._instantanea[0])
        self.asignaciones = list(self._instantanea[1])
        self.clientes = list(self._instantanea[2])

    def sembrar_usuario(self, email: str, nombre: str = "Existente") -> Usuario:
        usuario = Usuario(
            email=email,
            nombre=nombre,
            password_hash="$2b$12$hash-existente",
        )
        usuario.id = self.siguiente_id()
        self.usuarios.append(usuario)
        return usuario

    def sembrar_cliente(
        self, email: str, nombre: str = "Ficha existente"
    ) -> Cliente:
        cliente = Cliente(nombre=nombre, email=email, usuario_id=None)
        cliente.id = self.siguiente_id()
        self.clientes.append(cliente)
        return cliente


class _RepoUsuariosFalso:
    def __init__(self, mundo: MundoFalso, eventos: list[str]) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, usuario: Usuario) -> Usuario:
        self._eventos.append("add:usuarios")
        if any(
            existente.email.lower() == usuario.email.lower()
            for existente in self._mundo.usuarios
        ):
            raise error_de_unicidad("uq_usuario_email")
        usuario.id = self._mundo.siguiente_id()
        self._mundo.usuarios.append(usuario)
        return usuario


class _RepoRolesFalso:
    def __init__(self, mundo: MundoFalso, eventos: list[str]) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, asignacion: AsignacionRol) -> AsignacionRol:
        self._eventos.append("add:roles")
        if self._mundo.fallar_roles is not None:
            raise error_de_unicidad(self._mundo.fallar_roles)
        asignacion.id = self._mundo.siguiente_id()
        self._mundo.asignaciones.append(asignacion)
        return asignacion


class _RepoClientesFalso:
    def __init__(self, mundo: MundoFalso, eventos: list[str]) -> None:
        self._mundo = mundo
        self._eventos = eventos
        self.commit_llamado = False

    async def add(self, cliente: Cliente) -> Cliente:
        self._eventos.append("add:clientes")
        if self._mundo.fallar_clientes is not None:
            raise error_de_unicidad(self._mundo.fallar_clientes)
        if any(
            existente.email.lower() == cliente.email.lower()
            for existente in self._mundo.clientes
        ):
            # Nunca se toca la ficha ajena: sólo se intenta crear una nueva.
            raise error_de_unicidad("uq_cliente_email")
        cliente.id = self._mundo.siguiente_id()
        self._mundo.clientes.append(cliente)
        return cliente


class UoWFalso:
    """Unit of Work en memoria con la misma frontera que el real."""

    def __init__(self, mundo: MundoFalso, eventos: list[str] | None = None) -> None:
        self.mundo = mundo
        self.eventos = eventos if eventos is not None else []
        self.usuarios = _RepoUsuariosFalso(mundo, self.eventos)
        self.roles = _RepoRolesFalso(mundo, self.eventos)
        self.clientes = _RepoClientesFalso(mundo, self.eventos)
        self.entradas = 0
        self.salidas: list[type[BaseException] | None] = []
        self.confirmado = False
        self.revertido = False

    async def __aenter__(self) -> "UoWFalso":
        self.entradas += 1
        self.eventos.append("enter")
        self.mundo.abrir_transaccion()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.salidas.append(exc_type)
        self.eventos.append("exit")
        if exc_type is None:
            self.confirmado = True
        else:
            self.revertido = True
            self.mundo.revertir()
        return False

    @property
    def repositorios(self) -> tuple:
        return (self.usuarios, self.roles, self.clientes)
