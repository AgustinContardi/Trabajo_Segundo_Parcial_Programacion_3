"""Ejecución real del seed contra PostgreSQL (E2E, saltada por defecto).

`python seed.py` **vacía** la base apuntada por `Settings`, así que esta prueba
sólo se habilita cuando se exporta `SEED_E2E=1`:

    $env:SEED_E2E = "1"
    .\\.venv\\Scripts\\python.exe -m pytest tests/test_seed_ejecucion.py -q

Corre el script dos veces seguidas y verifica después de cada corrida el estado
completo: conteos, venta 1 con total 69000.00, stocks 10/5/8/3/1, las siete
cantidades de movimiento y el invariante de stock en 0 filas (CV-11, RN-11,
RN-12). La ejecución ocurre con `cwd` en `parcial/`, igual que la puesta en
marcha de la consigna.
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seed import CONTEOS_ESPERADOS, SQL_INVARIANTE, total_venta

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("SEED_E2E") != "1",
        reason=(
            "El seed vacía la base de Settings; exportá SEED_E2E=1 para "
            "correr la prueba de ejecución real."
        ),
    ),
]

DIRECTORIO_PARCIAL = Path(__file__).resolve().parents[1]


async def _correr_seed() -> None:
    """Ejecuta `python seed.py` con `cwd` en `parcial/` y exige código 0."""
    proceso = await asyncio.create_subprocess_exec(
        sys.executable,
        "seed.py",
        cwd=str(DIRECTORIO_PARCIAL),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    salida, error = await proceso.communicate()
    assert proceso.returncode == 0, (
        f"seed.py terminó con {proceso.returncode}\n"
        f"stdout:\n{salida.decode(errors='replace')}\n"
        f"stderr:\n{error.decode(errors='replace')}"
    )


async def _verificar_estado(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Comprueba con SQL el mismo contrato que imprime el seed."""
    async with sessionmaker() as session:
        for tabla, esperado in CONTEOS_ESPERADOS.items():
            obtenido = (
                await session.execute(text(f"SELECT count(*) FROM {tabla}"))
            ).scalar_one()
            assert int(obtenido) == esperado, tabla

        fila_venta = (
            await session.execute(text("SELECT id, total FROM venta WHERE id = 1"))
        ).first()
        assert fila_venta is not None, "Falta la venta con id = 1"
        assert int(fila_venta[0]) == 1
        assert Decimal(str(fila_venta[1])) == Decimal("69000.00") == total_venta()

        stocks = (
            await session.execute(text("SELECT stock FROM libro ORDER BY id"))
        ).scalars()
        assert [int(stock) for stock in stocks.all()] == [10, 5, 8, 3, 1]

        movimientos = (
            await session.execute(
                text(
                    "SELECT libro_id, cantidad FROM movimiento_stock "
                    "ORDER BY libro_id, id"
                )
            )
        ).all()
        assert [(int(libro_id), int(cantidad)) for libro_id, cantidad in movimientos] == [
            (1, 11),
            (1, -1),
            (2, 5),
            (3, 10),
            (3, -2),
            (4, 3),
            (5, 1),
        ]

        violaciones = (await session.execute(text(SQL_INVARIANTE))).all()
        assert violaciones == [], f"El invariante de stock tiene violaciones: {violaciones}"


async def test_seed_dos_corridas_consecutivas_dejan_el_mismo_estado(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _correr_seed()
    await _verificar_estado(db_sessionmaker)

    await _correr_seed()
    await _verificar_estado(db_sessionmaker)
