# Spec Delta — schema-migrations

## REMOVED Requirements

### Requirement: Exactly four chained migrations

**Reason**: El change correctivo agrega una quinta migración (`0005`) para reemplazar los `DEFAULT`
de fecha que quedaron congelados. Editar las migraciones 0001/0003 está prohibido por la regla dura 9,
así que el esquema pasa a tener cinco versiones encadenadas.

**Migration**: El requisito «Exactly five chained migrations» reemplaza a este con el mismo
comportamiento observable más la revisión `0005` como head. `alembic history` lista `0001`…`0005` y
`alembic upgrade head` aplica las cinco.

## ADDED Requirements

### Requirement: Exactly five chained migrations

The project SHALL contain exactly five migration versions, chained so that `0001` has no down
revision, each subsequent one revises the previous, and `0005` is the head. Revision `0005` SHALL be a
new file: migrations `0001`, `0002`, `0003` and `0004` MUST NOT be edited. Its filename SHALL carry the
ordinal `0005` and a descriptive suffix, consistent with the numeric convention used by `0001`/`0002`.

#### Scenario: five versions in order

- **WHEN** `alembic history` is inspected
- **THEN** it lists `0001`, `0002`, `0003`, `0004`, `0005` in order with `0005` as head

#### Scenario: applied migrations are not rewritten

- **WHEN** the files of migrations `0001`…`0004` are compared with the revision history of the
  repository
- **THEN** their content is unchanged; the fix lives only in `0005`

### Requirement: Server defaults evaluate now() at operation time

Las columnas `asignacion_rol.desde`, `intento_acceso.cuando`, `evento_seguridad.cuando`,
`movimiento_stock.cuando` y `venta.fecha` SHALL tener `DEFAULT now()` evaluado por PostgreSQL en el
momento de cada inserción, no un literal `timestamp with time zone` congelado. `pg_get_expr(adbin,
adrelid)` para las cinco columnas SHALL devolver `now()`. Los cinco modelos SQLModel SHALL declarar
`server_default=text("now()")` para que `alembic check` siga sin diferencias.

#### Scenario: pg_get_expr devuelve now()

- **WHEN** se consulta `pg_get_expr(adbin, adrelid)` para las cinco columnas
- **THEN** las cinco devuelven `now()` y ninguna devuelve un literal con fecha

#### Scenario: dos inserciones en transacciones distintas difieren

- **WHEN** se insertan dos filas de `evento_seguridad` en transacciones separadas con al menos 1 ms de
  diferencia
- **THEN** sus `cuando` no son idénticos y ambos están próximos a la hora real de la operación

#### Scenario: alembic check limpio

- **WHEN** se ejecuta `alembic check` después de `alembic upgrade head`
- **THEN** no reporta operaciones nuevas

### Requirement: Migration 0005 is reversible and preserves history

La migración `0005` SHALL usar `ALTER TABLE … ALTER COLUMN … SET DEFAULT now()` en `upgrade`. Su
`downgrade` SHALL restaurar la forma histórica de `0003` (cadena `'now()'`, que PostgreSQL congela al
aplicar) y SHALL declarar en la cabecera que esa forma reproduce el defecto heredado a propósito, para
que el descenso sea reversible. **No** SHALL reescribirse ninguna fila histórica.

#### Scenario: los datos históricos no se reescriben

- **WHEN** se ejecuta la migración `0005` sobre una base con filas previas
- **THEN** ninguna fila existente de `movimiento_stock`, `evento_seguridad`, `intento_acceso`,
  `asignacion_rol` o `venta` cambia de valor

#### Scenario: round trip reversible

- **WHEN** se ejecuta `alembic upgrade head`, `alembic downgrade base` y `alembic upgrade head`
- **THEN** los tres pasos terminan sin error y el head vuelve a dejar `now()` en las cinco columnas
