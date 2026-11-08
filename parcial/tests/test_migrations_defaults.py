"""Defaults de fecha evaluados por la base (C-04, migración 0005).

Dos verificaciones complementarias:

1. Estructural: `pg_get_expr` de las cinco columnas debe ser `now()`. El
   defecto histórico era un `server_default="now()"` como **cadena**, que
   PostgreSQL compiló a un literal `timestamptz` con la hora del DDL.
2. De comportamiento: dos inserciones en transacciones separadas reciben un
   `cuando` próximo al reloj real y distinto entre sí (en PostgreSQL `now()` es
   el inicio de la transacción).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

COLUMNAS_CON_DEFAULT = [
    ("asignacion_rol", "desde"),
    ("intento_acceso", "cuando"),
    ("evento_seguridad", "cuando"),
    ("movimiento_stock", "cuando"),
    ("venta", "fecha"),
]

_SQL_DEFAULT = text(
    """
    SELECT pg_get_expr(d.adbin, d.adrelid)
    FROM pg_attrdef d
    JOIN pg_attribute a
      ON a.attrelid = d.adrelid AND a.attnum = d.adnum
    WHERE d.adrelid = CAST(:tabla AS regclass)
      AND a.attname = :columna
    """
)


async def test_los_cinco_defaults_de_fecha_son_now(db_sessionmaker) -> None:
    async with db_sessionmaker() as session:
        for tabla, columna in COLUMNAS_CON_DEFAULT:
            expr = (
                await session.execute(
                    _SQL_DEFAULT, {"tabla": tabla, "columna": columna}
                )
            ).scalar_one_or_none()
            assert expr is not None, f"{tabla}.{columna} no tiene DEFAULT"
            assert expr == "now()", f"{tabla}.{columna} tiene {expr!r}, no now()"


async def test_dos_transacciones_separadas_no_comparten_el_sello(db_sessionmaker) -> None:
    """El default se evalúa al insertar, no quedó congelado en el DDL."""
    ids: list[int] = []
    valores: list[datetime] = []
    try:
        for _ in range(2):
            async with db_sessionmaker() as session:
                fila = (
                    await session.execute(
                        text(
                            "INSERT INTO evento_seguridad (actor, accion) "
                            "VALUES ('prueba-defaults', 'verificacion') "
                            "RETURNING id, cuando"
                        )
                    )
                ).one()
                await session.commit()
                ids.append(int(fila[0]))
                valores.append(fila[1])

        ahora = datetime.now(timezone.utc)
        for cuando in valores:
            assert abs(ahora - cuando) < timedelta(minutes=5), cuando
        assert valores[0] != valores[1], valores
    finally:
        if ids:
            async with db_sessionmaker() as session:
                await session.execute(
                    text("DELETE FROM evento_seguridad WHERE id = ANY(:ids)"),
                    {"ids": ids},
                )
                await session.commit()
