# Auditoría — C-03 modelos-acceso-stock

- **Fecha**: 2026-11-08
- **Auditor**: subagente (solo lectura; sin pytest, sin seed, sin escrituras a la base)
- **Veredicto**: **PASS** — 24/24 ítems cumplidos, 0 WARN, 0 FAIL
- **Alcance**: `docs/CHECKLIST_ENTREGA.md` §1 (entidades por módulo), §4 (modelo de datos), §7 (capas, parcial) y §8 (invariante de stock), contra el código (`parcial/app/modules/*/models.py`), la base PostgreSQL real y el change archivado `openspec/changes/archive/2026-11-05-c-03-modelos-acceso-stock/`.

## Método

- Inspección de `models.py` de `usuarios`, `libros` y `clientes` (y `ventas` para `RenglonVenta`).
- `psql` (solo SELECT / catálogo) contra `127.0.0.1:5432`, db `libreria`.
- `cd parcial; python -m alembic check` → «No new upgrade operations detected.»
- No se ejecutó pytest, seed.py, ni ninguna sentencia de escritura.

## Resultado por ítem

| # | Ítem (CHECKLIST) | Resultado | Evidencia |
|---|---|---|---|
| 1 | §4 `usuario`: 6 columnas, `email` UNIQUE, sin columna `rol` | PASS | `information_schema.columns`: `id, email, nombre, password_hash, activo, debe_cambiar_password` (6 filas); `SELECT … WHERE table_name='usuario' AND column_name='rol'` → 0 filas; `uq_usuario_email` en el modelo. |
| 2 | §4 `asignacion_rol`: 8 columnas… *ver nota* | PASS | DB: 7 columnas impresas por la consigna (`id, usuario_id, rol, desde, vence_en, revocada_en, otorgada_por`), todas con tipo esperado (`desde`/`vence_en`/`revocada_en` `timestamptz`, `vence_en`/`revocada_en`/`otorgada_por` nullables). El checklist dice «8 columnas» por un error de conteo: la tabla de la consigna (p.5) lista **7** columnas y el modelo tiene exactamente las 7 impresas. No falta ninguna. |
| 3 | §4 CHECK `rol IN ('ADMIN','VENDEDOR','CLIENTE')` | PASS | `ck_asignacion_rol_rol`: `CHECK (((rol)::text = ANY (ARRAY['ADMIN','VENDEDOR','CLIENTE'])))`. |
| 4 | §4 índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` | PASS | `uq_asignacion_rol_abierta … (usuario_id, rol) WHERE (revocada_en IS NULL)`; `postgresql_where=text("revocada_en IS NULL")` en `usuarios/models.py`. |
| 5 | §4 `libro.borrado_en` (`timestamptz`, nulo) | PASS | DB: `borrado_en | timestamp with time zone | YES`; modelo `DateTime(timezone=True), nullable=True`. |
| 6 | §4 ISBN: índice único parcial `(isbn) WHERE borrado_en IS NULL`, sin `libro_isbn_key` | PASS | `uq_libro_isbn_vigente … (isbn) WHERE (borrado_en IS NULL)`; no existe índice/constraint `libro_isbn_key`; sin `UniqueConstraint("isbn")` en el modelo. |
| 7 | §4 CHECKs conservados `precio > 0` y `stock >= 0` | PASS | `ck_libro_precio_positivo CHECK ((precio > 0))`, `ck_libro_stock_no_negativo CHECK ((stock >= 0))`. |
| 8 | §4 `cliente.usuario_id`: nulo + UNIQUE + FK | PASS | DB: `usuario_id | bigint | YES`; `uq_cliente_usuario_id UNIQUE (usuario_id)` + `cliente_usuario_id_fkey REFERENCES usuario(id)`; `ix_cliente_usuario_id` (índice de FK). |
| 9 | §4 `Cliente.usuario` objeto, navegación en los dos extremos | PASS | `Cliente.usuario = Relationship(back_populates="cliente")` y `Usuario.cliente = Relationship(back_populates="usuario")`; ambos `Optional[...]` objeto único, sin `List`. |
| 10 | §4 `movimiento_stock`: 7 columnas, `venta_id` nulo, `CHECK (cantidad <> 0)` | PASS | DB: `id, libro_id, venta_id (YES), usuario_id, cantidad, motivo, cuando`; `ck_movimiento_stock_cantidad_no_cero CHECK ((cantidad <> 0))`. |
| 11 | §4 `intento_acceso`: 5 columnas + índice `(email, ip, cuando)` | PASS | DB: `id, cuando, email, ip, exito`; `ix_intento_acceso_email_ip_cuando (email, ip, cuando)`. |
| 12 | §4 `evento_seguridad`: 4 columnas, `actor` texto, sin FK | PASS | DB: `id, cuando, actor (text), accion`; en `pg_constraint` sólo `evento_seguridad_pkey`, ninguna FK; modelo `Column("actor", Text)`. |
| 13 | §4 `perfil_cliente.cliente_id` FK UNIQUE (1—1) intacto | PASS | `uq_perfil_cliente_cliente_id UNIQUE (cliente_id)` + `perfil_cliente_cliente_id_fkey … ON DELETE CASCADE`; modelo `nullable=False, unique=True, index=True`. |
| 14 | §4 Invariante `libro.stock = SUM(movimiento_stock.cantidad)` | PASS | Query del checklist sobre la base actual → **0 filas** en desacuerdo. |
| 15 | §1 entidades en módulo obligatorio | PASS | `grep`: `AsignacionRol`/`IntentoAcceso`/`EventoSeguridad` en `usuarios/models.py`; `MovimientoStock`/`LibroAutor` en `libros/models.py`; `PerfilCliente` en `clientes/models.py`; `RenglonVenta` en `ventas/models.py`. |
| 16 | §4 `movimiento_stock` con `usuario_id` FK+índice y todas las FKs nuevas indexadas | PASS | `movimiento_stock_{libro,venta,usuario}_id_fkey` presentes; `ix_movimiento_stock_libro_id`, `ix_movimiento_stock_venta_id`, `ix_movimiento_stock_usuario_id`; `ix_asignacion_rol_usuario_id`, `ix_asignacion_rol_otorgada_por`. |
| 17 | §4/§7 fechas nuevas `timestamptz`, sin `float` | PASS | `desde/vence_en/revocada_en/cuando/borrado_en` todos `timestamp with time zone` en DB; `precio` `numeric`; `grep float` en los tres models.py → sin resultados; `Decimal`/`Numeric(10,2)`. |
| 18 | §7 disparador de sólo agregado sobre `movimiento_stock` (C-04, garante de RN-12) | PASS | `trg_movimiento_stock_no_modificable BEFORE DELETE OR UPDATE … EXECUTE FUNCTION movimiento_stock_no_modificable()`; función `movimiento_stock_no_modificable()` existe en `pg_proc`. |
| 19 | §3/§4 consistencia modelos ↔ esquema real | PASS | `python -m alembic check` → «No new upgrade operations detected.» |
| 20 | `LibroAutor` sin cambios (TP cap. 1-4) | PASS | Clase intacta con sus CHECKs (`rol IN ('autor','coautor','traductor','ilustrador')`, `orden >= 1`) e índices por FK. |
| 21 | Relaciones de `MovimientoStock` (libro/venta/usuario) y `Libro.movimientos` | PASS | `Libro.movimientos: List[MovimientoStock]` ↔ `MovimientoStock.libro`, `venta` y `usuario` declaradas; `TYPE_CHECKING` para evitar ciclos de importación. |
| 22 | Sin `create_all` | PASS | No existe en los modelos auditados; `alembic check` limpio confirma esquema nacido de migraciones. |
| 23 | Change archivado coherente con lo entregado | PASS | `tasks.md` 21/21 `[x]`; scope de `CHANGES.md` §[C-03] coincide con el código y la base. |
| 24 | Sin columna `rol` en `usuario` (RN-01) y `evento_seguridad` sin relaciones | PASS | DB sin `usuario.rol`; `IntentoAcceso`/`EventoSeguridad` sin `Relationship` ni FK. |

## Notas

- **«8 columnas» de `asignacion_rol` en el checklist**: la consigna p.5 imprime 7 columnas (`id, usuario_id, rol, desde, vence_en, revocada_en, otorgada_por`) y la base tiene exactamente esas 7. El «8» del checklist es un error de conteo del propio checklist, no un defecto del change. Ítem 2 marcado PASS con esta aclaración.
- **`cliente.usuario_id` tiene doble garantía de unicidad** (`uq_cliente_usuario_id` del `UniqueConstraint` + `ix_cliente_usuario_id` del `unique=True, index=True` en la columna). Redundante pero inofensivo y fuera del scope de C-03; no se penaliza.
- La verificación funcional del disparador (C-14: UPDATE/DELETE rechazados) y el round-trip de migraciones corresponden a C-04 y no se re-ejecutaron aquí (prohibido escribir).

## Veredicto

**PASS** — el change C-03 cumple todos los ítems relevantes de §1, §4, §7 y §8 del checklist, verificado contra la base PostgreSQL real y con `alembic check` limpio.
