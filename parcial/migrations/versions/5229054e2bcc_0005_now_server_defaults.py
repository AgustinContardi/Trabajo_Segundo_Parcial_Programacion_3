"""0005 now() reales en los defaults de fecha

Revision ID: 5229054e2bcc
Revises: c8d2dea5529f
Create Date: 2026-11-08 16:17:01.877102

# NOTA (regla 9): migración escrita a mano y leída antes de aplicarse.
# El `server_default="now()"` de 0001/0003 se compiló a un literal `timestamptz`
# con la hora del DDL (C-04). Esta revisión reemplaza el DEFAULT de las cinco
# columnas por `now()`, que PostgreSQL evalúa en cada INSERT.
#
# No hay `UPDATE`: las filas históricas conservan su sello original. La
# corrección aplica sólo a las escrituras nuevas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5229054e2bcc'
down_revision: Union[str, Sequence[str], None] = 'c8d2dea5529f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNAS = (
    ("asignacion_rol", "desde"),
    ("intento_acceso", "cuando"),
    ("evento_seguridad", "cuando"),
    ("movimiento_stock", "cuando"),
    ("venta", "fecha"),
)


def upgrade() -> None:
    """Deja `now()` evaluado por la base en las cinco columnas de fecha."""
    for tabla, columna in COLUMNAS:
        op.alter_column(
            tabla,
            columna,
            server_default=sa.text("now()"),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restaura la forma histórica de 0001/0003.

    Advertencia: `server_default="now()"` como cadena vuelve a congelar el
    valor en el momento del DDL; sólo se usa para que el descenso deje la base
    como la dejó 0003.
    """
    for tabla, columna in COLUMNAS:
        op.alter_column(
            tabla,
            columna,
            server_default="now()",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
