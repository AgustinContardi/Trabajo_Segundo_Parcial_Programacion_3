# Auditoría — C-04 migraciones-0003-0004

> **Fecha**: 2026-11-08 · **Auditor**: agente (solo lectura) · **Base**: PostgreSQL 17.11 @ 127.0.0.1:5432, db `libreria`
> **Objeto**: change archivado `openspec/changes/archive/2026-11-05-c-04-migraciones-0003-0004/` contra
> `docs/CHECKLIST_ENTREGA.md` §3 (y spec `schema-migrations`).
> **Restricciones respetadas**: sin pytest, sin seed, sin INSERT/UPDATE/DELETE, sin uvicorn, sin DDL destructivo
> (no se re-ejecutó `downgrade`; se valida por evidencia del change + estado actual).

## Veredicto

**FAIL documentado** — la aceptación de §3 se cumple (6/6 ítems), pero la migración 0003 deja vigente el defecto
conocido del `server_default='now()'` literal congelado, con impacto real en datos escritos por la app y el seed.

## Tabla por ítem (§3 Migraciones + spec)

| # | Ítem | Verificación realizada | Resultado |
|---|---|---|---|
| 1 | Exactamente cuatro versiones (2 TP + autogenerada + manual) | `ls migrations/versions` → 4 archivos; `alembic history` → 0ba1752f7c23 → 5f67a857f685 → dd4a0e5e9cf7 → c8d2dea5529f (head) | **PASS** |
| 2 | `alembic current` en head | `python -m alembic current` → `c8d2dea5529f (head)`; `alembic_version` en DB = `c8d2dea5529f` | **PASS** |
| 3 | 0003 trae las 8 piezas | Archivo `dd4a0e5e9cf7_acceso_y_stock.py`: `usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`, `movimiento_stock`, `cliente.usuario_id`, `libro.borrado_en`, 2 índices parciales (`uq_asignacion_rol_abierta`, `uq_libro_isbn_vigente` con `postgresql_where`) + drop de `uq_libro_isbn` común. En DB: ambos índices parciales existen con el `WHERE` correcto; `uq_libro_isbn` ausente | **PASS** |
| 4 | Comentario de cabecera en cada migración nueva (leída antes de aplicar + correcciones) | 0003: cabecera `NOTA (CV-10 / regla 9)` con 6 correcciones enumeradas. 0004: cabecera `NOTA (CV-10 / regla 9): migración escrita a mano` (DD-04) | **PASS** |
| 5 | 0004 manual: función + trigger append-only; downgrade borra ambos | Archivo: `CREATE OR REPLACE FUNCTION movimiento_stock_no_modificable()` (RAISE EXCEPTION) + `CREATE TRIGGER trg_movimiento_stock_no_modificable BEFORE UPDATE OR DELETE ON movimiento_stock FOR EACH ROW`; downgrade `DROP TRIGGER` antes que `DROP FUNCTION`. En DB: trigger existe (tgtype 27 = BEFORE ROW UPDATE+DELETE, habilitado), función existe | **PASS** |
| 6 | Round-trip `upgrade head → downgrade base → upgrade head` sin error | No re-ejecutado (DDL destructivo, auditoría solo lectura). Evidencia: tasks.md 5.1–5.2 `[x]`, cambio archivado con round-trip OK, y la base actual está completa en head | **PASS (por evidencia)** |
| 7 | `alembic check` sin drift | Ejecutado hoy: «No new upgrade operations detected.», exit 0 | **PASS** |
| 8 | FK nuevas con índice, fechas nuevas `timestamptz`, dinero `NUMERIC` | En DB: `ix_asignacion_rol_usuario_id`, `ix_asignacion_rol_otorgada_por`, `ix_movimiento_stock_libro_id/usuario_id/venta_id`, `ix_cliente_usuario_id`; todas las fechas nuevas son `timestamp with time zone`; dinero `NUMERIC` intacto | **PASS** |
| 9 | Sin `create_all` en el repo | `grep -rn "create_all" parcial/ --include=*.py` → sin coincidencias | **PASS** |
| 10 | `env.py` importa los modelos de dominio | `import app.modules.usuarios.models  # noqa: F401` presente junto a los demás módulos | **PASS** |
| 11 | `server_default='now()'` correcto (no literal congelado) | `pg_get_expr(adbin, adrelid)` en DB: `asignacion_rol.desde`, `intento_acceso.cuando`, `evento_seguridad.cuando`, `movimiento_stock.cuando` tienen default **`'2026-11-08 12:18:56.115576-03'::timestamp with time zone`** (literal congelado al momento de migrar). Los modelos replican el literal (`server_default="now()"` como string), por eso `alembic check` no lo detecta | **FAIL (documentado)** |

## Defecto documentado — literal congelado (no corregido, por orden expresa)

- **Causa**: en 0003 (y en los modelos de C-03) `server_default="now()"` es una *cadena*; SQLAlchemy la compila como
  literal `DEFAULT 'now()'`, que PostgreSQL cast **una vez** al crear la columna → timestamp de migración congelado.
- **Impacto real confirmado en datos** (SELECT de solo lectura, hoy):
  - `movimiento_stock`: 7 filas, `min(cuando) = max(cuando) = 2026-11-08 12:18:56.115576-03`, `count(DISTINCT cuando) = 1` → **todas** con la misma hora congelada.
  - `evento_seguridad`: 1 fila con la misma hora congelada.
  - `intento_acceso` y `asignacion_rol.desde` se salvan porque el código escribe `cuando`/`desde` explícitamente
    (`usuarios/service.py` lo declara en comentario: «el DEFAULT migrado … es un literal congelado (defecto heredado)»).
  - `libros/repository.py:88` (`MovimientoStock(...)`) **no** pasa `cuando` y los `EventoSeguridad(actor=..., accion=...)`
    tampoco → la app y el seed escriben fechas incorrectas en esas dos tablas (RN-11, RN-16).
- **Alcance extra**: `venta.fecha` tiene el mismo literal, heredado de la migración `0001` del TP (fuera del scope de C-04, pero misma cura).
- **Fix recomendado** (regla 9: nunca editar migraciones aplicadas):
  1. Migración **nueva** `0005` que reemplace los `DEFAULT` por `now()` real:
     `ALTER TABLE … ALTER COLUMN cuando SET DEFAULT now()` (4 columnas de 0003 + `venta.fecha` de 0001), con `downgrade` que los deje como estaban.
  2. Modelos: cambiar `server_default="now()"` por `server_default=sa.text("now()")` en los 5 lugares
     (`usuarios/models.py` ×3, `libros/models.py` ×1, `ventas/models.py` ×1) y re-correr `alembic check` (debe quedar limpio).
  3. Ajustar `seed.py`/servicios para que toda escritura pase `cuando=datetime.now(timezone.utc)` explícito o confiar en el default corregido.

## Observaciones menores (fuera del scope de C-04)

- `asignacion_rol` tiene **7** columnas (`id, usuario_id, rol, desde, vence_en, revocada_en, otorgada_por`); el
  checklist §4 dice «las **8** columnas» pero lista esas 7. No es ítem de §3; corresponde revisarlo en la auditoría
  de C-03/modelo de datos. Modelo y migración son consistentes (`alembic check` limpio).
- El round-trip y la prueba del trigger (caso C-14) no se re-ejecutaron en esta auditoría por ser mutaciones;
  quedan cubiertos por la evidencia del change y por el estado actual del trigger/función en DB.
