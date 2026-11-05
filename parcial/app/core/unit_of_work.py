"""Unit of Work base: frontera de transacción.

Contrato de este módulo (CV-01):
- Quién construye: el router (vía dependencia) instancia el Unit of Work con
  la sesión recibida.
- Quién abre: el servicio lo abre con ``async with``.
- Quién confirma: sólo ``__aexit__`` (confirmación sin excepción, reversión
  con excepción).
- Quién cierra: ``get_session`` (la sesión no la crea el Unit of Work).

El Unit of Work no posee ni cierra la sesión: sólo confirma o revierte al
salir del bloque. Devuelve ``False`` para no suprimir la excepción y que
FastAPI la traduzca a HTTP.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """Gestor de contexto asíncrono que delimita una transacción.

    Plantilla de ``<módulo>/unit_of_work.py`` (C-06…C-10, C-15) — se
    documenta, no se instancia en este change:

        class VentasUnitOfWork(UnitOfWork):
            def __init__(self, session: AsyncSession) -> None:
                super().__init__(session)
                self.ventas = VentaRepository(session, Venta)
                self.renglones = RenglonVentaRepository(session, RenglonVenta)
                self.libros = LibroRepository(session, Libro)
                self.clientes = ClienteRepository(session, Cliente)

    El router construye el Unit of Work (CV-01); el servicio lo abre con
    ``async with``; los repositorios sólo hacen ``flush()``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        return False