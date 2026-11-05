# Baseline TP cap. 1-4 — valores confirmados

Fuente: migraciones generadas en `parcial/migrations/versions/` y esquema aplicado en PostgreSQL 18.

## SU-01 — Tipo de las claves primarias
- **Confirmado**: `bigint` con `IDENTITY` (`sa.BigInteger(), sa.Identity(always=False)`).
- Evidencia: `0ba1752f7c23_0001_initial_tp_baseline.py` líneas de `sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False)` para `autor`, `cliente`, `editorial`, `libro`, `perfil_cliente`, `venta`, `renglon_venta`; y `5f67a857f685_0002_add_genero.py` para `genero`.

## SU-07 — `venta` no tiene `usuario_id`
- **Confirmado**: la tabla `venta` tiene únicamente `id, cliente_id, fecha, total`. No existe `usuario_id`.
- `cliente_id` es FK → `cliente.id` con `ON DELETE NO ACTION`.
- Evidencia: migración `0001`, tabla `venta` (columnas y `ForeignKeyConstraint(['cliente_id'], ['cliente.id'], ondelete='NO ACTION')`); `\d venta` en psql.

## SU-08 — Nombre del precio copiado en `renglon_venta`
- **Confirmado**: `precio_unitario` (`NUMERIC(10,2)`), con `CHECK (precio_unitario > 0)`.
- Evidencia: migración `0001`, tabla `renglon_venta`, columna `precio_unitario`.

## SU-09 — Revisiones y nombres de archivo de las migraciones
- Migración 1: revision `0ba1752f7c23`, archivo `0ba1752f7c23_0001_initial_tp_baseline.py`, `down_revision = None`. Crea todas las tablas excepto `genero`.
- Migración 2: revision `5f67a857f685`, archivo `5f67a857f685_0002_add_genero.py`, `down_revision = 0ba1752f7c23`. Agrega tabla `genero` y columna `libro.genero_id` (FK `fk_libro_genero`, índice `ix_libro_genero_id`).

## Tablas creadas
`autor`, `cliente`, `editorial`, `libro`, `perfil_cliente`, `venta`, `libro_autor`, `renglon_venta` (0001) + `genero` (0002).

## Verificación
- `alembic upgrade head` sobre base vacía: OK.
- `alembic downgrade -1` + `alembic upgrade head`: OK.
- `alembic downgrade base` + `alembic upgrade head`: OK.