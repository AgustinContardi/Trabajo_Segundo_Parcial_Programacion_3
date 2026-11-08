"""Stock inicial por el punto único e invariante global (RN-11, RN-12).

Los fixtures deben sembrar stock con `LibroRepository.aplicar_movimiento(...,
"Stock inicial", ...)`, nunca escribiendo `Libro(stock=N)` directo. Así
`libro.stock = SUM(movimiento_stock.cantidad)` se cumple desde el nacimiento
del libro y la query global puede exigir 0 filas.
"""

from decimal import Decimal
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio


async def test_libro_con_stock_inicial_crea_movimiento_y_stock_iguales(
    catalogo_factory,
    libro_con_stock_inicial,
    db_sessionmaker,
    invariante_stock,
) -> None:
    editorial = await catalogo_factory.editorial()
    libro = await libro_con_stock_inicial(
        editorial_id=editorial.id,
        precio=Decimal("12.50"),
        stock_inicial=7,
    )

    assert libro.stock == 7
    assert await invariante_stock(libro_ids=[libro.id]) == []


async def test_catalogo_factory_libro_con_stock_usa_el_punto_unico(
    catalogo_factory,
    invariante_stock,
    db_sessionmaker,
) -> None:
    editorial = await catalogo_factory.editorial()
    genero = await catalogo_factory.genero()
    libro = await catalogo_factory.libro(
        editorial_id=editorial.id,
        genero_id=genero.id,
        precio=Decimal("20.00"),
        stock=4,
    )

    assert libro.stock == 4
    assert await invariante_stock(libro_ids=[libro.id]) == []


async def test_stock_cero_no_requiere_movimiento(
    catalogo_factory,
    invariante_stock,
) -> None:
    editorial = await catalogo_factory.editorial()
    libro = await catalogo_factory.libro(editorial_id=editorial.id, stock=0)

    assert libro.stock == 0
    assert await invariante_stock(libro_ids=[libro.id]) == []


async def test_invariante_global_no_tiene_violaciones(invariante_stock) -> None:
    """La base local no debe conservar violaciones históricas (RN-11).

    Ejecuta `seed.py` antes de verificar para restaurar el estado canónico,
    ya que otras pruebas pueden haber modificado stocks y movimientos.
    """
    subprocess.run(
        ["python", "seed.py"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        check=True,
    )
    assert await invariante_stock() == []


async def test_un_stock_escrito_directo_rompe_el_invariante_y_se_detecta(
    catalogo_factory,
    db_sessionmaker,
    invariante_stock,
) -> None:
    """Control negativo: la query detecta una violación si se escribe directo."""
    from app.modules.libros.models import Libro
    from app.modules.editoriales.models import Editorial

    editorial = await catalogo_factory.editorial()
    async with db_sessionmaker() as session:
        libro = Libro(
            isbn="invariante-roto",
            titulo="Invariante roto",
            precio=Decimal("10.00"),
            stock=3,
            editorial_id=editorial.id,
        )
        session.add(libro)
        await session.commit()
        await session.refresh(libro)
    catalogo_factory.registrar_libro(libro.id)

    violaciones = await invariante_stock(libro_ids=[libro.id])
    assert [row[0] for row in violaciones] == [libro.id]
