# Tasks — C-04 migraciones-0003-0004

> Todo path de la aplicación es relativo a `parcial/`. Este change crea las migraciones `0003` y `0004` y
> ajusta `migrations/env.py`. La verificación final requiere PostgreSQL 16 con el esquema del TP aplicado;
> los pasos que dependen de la base están marcados como tales.

## 1. Preparación

- [x] 1.1 Agregar `import app.modules.usuarios.models` (con `# noqa: F401`) a
  `parcial/migrations/env.py` junto a los demás imports de modelos, y verificar que
  `python -c "import app.modules.usuarios.models"` y la importación conjunta de todos los módulos pasan.
- [x] 1.2 Confirmar que `0001` y `0002` están aplicadas en la base de trabajo
  (`alembic current` muestra `5f67a857f685`), y que `alembic history` lista las dos revisiones heredadas.

## 2. Migración 0003 — autogenerada y leída

- [x] 2.1 Ejecutar `alembic revision --autogenerate -m "acceso y stock"` contra la base con el esquema del
  TP aplicado, y anotar el `revision` generado y su `down_revision` (debe ser `5f67a857f685`).
- [x] 2.2 Leer la migración entera antes de aplicarla; verificar que incluye las 5 tablas nuevas y los
  cambios en `cliente`/`libro`, y detectar lo que infiere mal (tipos, `postgresql_where`, índices de FKs,
  `UNIQUE(isbn)` común).
- [x] 2.3 Corregir a mano en `0003`: tipos a `DateTime(timezone=True)`/`Numeric`, `postgresql_where` de los
  dos índices parciales, `libro.borrado_en` como `timestamptz`, índices de las FKs nuevas, y drop del
  `UNIQUE(isbn)` común de `libro`. Verificar con `grep` que el índice parcial existe y el `UniqueConstraint`
  común no.
- [x] 2.4 Agregar el comentario de cabecera en `0003` que declare que se leyó antes de aplicar y enumere las
  correcciones de 2.3. Verificar: el archivo contiene el comentario.

## 3. Migración 0004 — a mano

- [x] 3.1 Escribir `parcial/migrations/versions/0004_..._append_only.py` a mano con `CREATE FUNCTION`
  (PL/pgSQL) + `CREATE TRIGGER` `BEFORE UPDATE OR DELETE ON movimiento_stock` que rechace la operación.
  Verificar: el archivo contiene `CREATE FUNCTION` y `CREATE TRIGGER`.
- [x] 3.2 Implementar el `downgrade` con `DROP TRIGGER` y luego `DROP FUNCTION`, en ese orden. Verificar:
  `grep -n "DROP TRIGGER\|DROP FUNCTION"` muestra ambos, disparador primero.
- [x] 3.3 Encadenar `0004` a `0003` (`down_revision` = revisión de `0003`) y verificar con
  `alembic history` que `0004` es head.

## 4. Aplicación y verificación de las 8 piezas

- [x] 4.1 Aplicar `alembic upgrade head` y verificar que termina sin error. Verificar: `alembic current`
  muestra la revisión de `0004`.
- [x] 4.2 Verificar que `0003` trajo las 8 piezas: `usuario`, `asignacion_rol`, `intento_acceso`,
  `evento_seguridad`, `movimiento_stock`, `cliente.usuario_id`, `libro.borrado_en` y los dos índices únicos
  parciales (consulta a `information_schema`/`pg_indexes` o `\d`).
- [x] 4.3 Probar el disparador: ejecutar un `UPDATE` y un `DELETE` sobre `movimiento_stock` (si hay filas;
  si no, insertar una de prueba y luego intentar) y confirmar que ambos fallan. Verificar: `psql` devuelve
  error en las dos sentencias (caso C-14).

## 5. Round-trip y comprobaciones finales

- [x] 5.1 Correr `alembic downgrade base` y verificar que termina sin error (borra tablas, columnas, índices,
  disparador y función).
- [x] 5.2 Correr `alembic upgrade head` de nuevo y verificar que termina sin error.
- [x] 5.3 Correr `alembic check` y verificar que reporta sin operaciones pendientes. Verificar: salida
  «No new upgrade operations detected» (o equivalente) y código de salida 0 (CV-10).
- [x] 5.4 Verificar que no hay `create_all` en el repositorio: `grep -rn "create_all" parcial/` vacío
  (CV-14). Verificar: sin coincidencias.

## Workflow follow-up

- Archivar el change con `/opsx:archive` una vez verificada la implementación y marcar `C-04` como `[x]` en
  `CHANGES.md`.
- Correr el round-trip en una base limpia antes de entregar (§12 de `docs/CHECKLIST_ENTREGA.md`).