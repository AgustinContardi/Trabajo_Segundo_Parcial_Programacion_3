"""0004 append only (movimiento_stock)

Revision ID: c8d2dea5529f
Revises: dd4a0e5e9cf7
Create Date: 2026-11-05 19:53:52.142341

# NOTA (CV-10 / regla 9): migración escrita a mano. `autogenerate` no ve
# funciones ni disparadores (DD-04), por eso se crea con SQL explícito.
# Garantiza RN-12: movimiento_stock es de sólo agregado; cualquier UPDATE o
# DELETE falla venga de donde venga (app, psql, script).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d2dea5529f'
down_revision: Union[str, Sequence[str], None] = 'dd4a0e5e9cf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION movimiento_stock_no_modificable()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'movimiento_stock es de solo agregado: operacion % no permitida', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_movimiento_stock_no_modificable
        BEFORE UPDATE OR DELETE ON movimiento_stock
        FOR EACH ROW
        EXECUTE FUNCTION movimiento_stock_no_modificable();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_movimiento_stock_no_modificable ON movimiento_stock;")
    op.execute("DROP FUNCTION IF EXISTS movimiento_stock_no_modificable();")
