# Proposal — C-04 migraciones-0003-0004

## Why

`C-03` ya definió los modelos nuevos (cuatro tablas de acceso, `movimiento_stock`, `libro.borrado_en` + índice
parcial del ISBN, `cliente.usuario_id`), pero la base todavía sólo tiene las migraciones `0001`/`0002` del TP.
Sin las migraciones `0003`/`0004`, un `alembic upgrade head` sobre una base vacía **no crea** esas tablas
ni el disparador de sólo agregado, así que el proyecto no levanta desde cero y `RN-12` queda sin garante. Esta
es una de las condiciones que anulan la corrección («que no crea su esquema con `alembic upgrade head` sobre
una base vacía») y concentra el 10 % de «Integridad».

## What Changes

- Generar `0003_..._acceso_y_stock.py` con `alembic revision --autogenerate` contra una base con el esquema
  del TP aplicado, **leerla entera antes de aplicarla** y corregirla a mano lo que la comparación no infiere
  (tipos, `postgresql_where` de los dos índices parciales, `borrado_en` como `timestamptz`, índices de las
  FKs nuevas, drop del `UNIQUE(isbn)` común).
- Verificar que la tercera trae las **8 piezas**: `usuario`, `asignacion_rol`, `intento_acceso`,
  `evento_seguridad`, `movimiento_stock`, `cliente.usuario_id`, `libro.borrado_en` y los **dos** índices únicos
  parciales.
- Comentario de cabecera en `0003` que diga que se leyó antes de aplicar y **qué** se corrigió a mano.
- Escribir `0004_..._append_only.py` **a mano**: `CREATE FUNCTION` + `CREATE TRIGGER` que rechazan
  **cualquier** `UPDATE` o `DELETE` sobre `movimiento_stock`; `downgrade` con `DROP TRIGGER` **y**
  `DROP FUNCTION`.
- Garantizar el round-trip sobre base vacía (`upgrade head` → `downgrade base` → `upgrade head`) y
  `alembic check` sin diferencias (`CV-10`).
- Asegurar que `migrations/env.py` importe `app.modules.usuarios.models` (hoy no lo hace) para que
  `autogenerate` vea las tablas de acceso.
- Sin `create_all` en ningún lado (`CV-14`).

## Capabilities

### New Capabilities

- `schema-migrations`: esquema versionado del parcial — las cuatro migraciones encadenadas, la tercera
  autogenerada y leída, la cuarta con el disparador de sólo agregado, el round-trip sobre base vacía y la
  ausencia de diferencias en `alembic check`.

### Modified Capabilities

Ninguna. `data-model` (C-03) ya fija la forma de las tablas; este change fija **cómo se materializan** en
la base. `legacy-baseline` ya exige que las migraciones nuevas se encadenen a la última revisión heredada,
y este change cumple esa exigencia sin cambiar sus requisitos.

## Impact

- **Código nuevo**: `parcial/migrations/versions/0003_..._acceso_y_stock.py` y
  `parcial/migrations/versions/0004_..._append_only.py`.
- **Código modificado**: `parcial/migrations/env.py` (import de `app.modules.usuarios.models`).
- **Base de datos**: 5 tablas nuevas, 1 columna nueva en `cliente`, 1 columna nueva en `libro`, drop de
  `UNIQUE(isbn)` común, 2 índices parciales nuevos, 1 función + 1 disparador.
- **Dependencias**: sólo lo ya instalado (Alembic 1.13, SQLAlchemy 2.0, asyncpg, PostgreSQL 16). Sin
  paquetes nuevos.
- **Changes aguas abajo**: `C-05`…`C-16` asumen que `alembic upgrade head` deja el esquema completo en una
  base vacía; `C-17` (seed) y `C-18` (casos) corren sobre esa base.
- **Riesgo principal**: si la migración autogenerada no se lee, puede dejar tipos mal inferidos o un
  `UNIQUE` común en `isbn`, rompiendo RN-13 y el round-trip. Se mitiga con la lectura obligatoria y el
  comentario de cabecera (CV-10).