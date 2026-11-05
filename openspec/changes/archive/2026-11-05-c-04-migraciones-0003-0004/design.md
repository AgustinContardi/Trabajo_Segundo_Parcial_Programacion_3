# Design — C-04 migraciones-0003-0004

## Context

Ver `proposal.md` — Why. `C-03` dejó los modelos nuevos en `parcial/app/modules/{usuarios,libros,clientes}`,
y las migraciones `0001`/`0002` del TP ya están aplicadas. `migrations/env.py` ya importa los módulos de
dominio **excepto** `app.modules.usuarios.models`, que hay que agregar para que `autogenerate` vea las
tablas de acceso. No hay base de datos disponible en el entorno de planificación; la implementación
requiere PostgreSQL 16 local con el esquema del TP aplicado.

## Goals / Non-Goals

**Goals:**
- Materializar el esquema completo del parcial en dos migraciones nuevas (`0003` autogenerada y leída,
  `0004` a mano), encadenadas a `0002`.
- Garantizar `upgrade head` / `downgrade base` / `upgrade head` sobre base vacía y `alembic check` limpio.
- Instalar el garante de `RN-12` (disparador de sólo agregado) en la base.

**Non-Goals (de diseño):**
- No se tocan modelos, routers ni servicios: `C-03` ya los definió.
- No se crean repositorios, schemas ni endpoints (esos son `C-05`…`C-16`).
- No se agrega defensa en profundidad con un rol de base sin permisos (DD-04: el disparador alcanza).
- No se resuelve AB-02/AB-06 (vendedor en `venta`, nombre del precio copiado): fuera de alcance.

## Decisions

### D-01 — `0003` autogenerada y luego leída entera

**Decisión**: ejecutar `alembic revision --autogenerate -m "..."` contra una base con el esquema del TP
aplicado, **leer el archivo completo** antes de aplicarlo, y corregir a mano lo que la comparación no infiere.

**Por qué**:
- La consigna exige que cada migración nueva se lea antes de aplicarla y que lleve un comentario que lo diga.
- `autogenerate` es la única forma de no escribir a mano 5 tablas + cambios, pero infiere mal tipos e índices
  parciales.

**Alternativas descartadas**:
- *Escribir `0003` a mano*: más control, pero pierde la verificación cruzada que da `autogenerate` contra el
  metadata de SQLModel y duplica trabajo.

### D-02 — Importar `usuarios.models` en `env.py` antes de autogenerar

**Decisión**: agregar `import app.modules.usuarios.models` a `migrations/env.py` (hoy falta) para que
`target_metadata` incluya `usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`.

**Por qué**:
- Sin ese import, `autogenerate` no vería las tablas de acceso y generaría una migración incompleta.
- Es el mismo patrón que ya siguen los otros módulos.

**Alternativas descartadas**:
- *Importar en cada migración*: no es necesario; `env.py` es el único lugar que define `target_metadata`.

### D-03 — Correcciones a mano en `0003`

**Decisión**: tras leer la migración autogenerada, corregir a mano:
1. Tipos mal inferidos (por ejemplo `DateTime` sin zona → `DateTime(timezone=True)`).
2. `postgresql_where` de los dos índices parciales (`asignacion_rol` y `libro.isbn`).
3. `libro.borrado_en` como `timestamptz`.
4. Índices de las FKs nuevas (`usuario_id`, `otorgada_por`, `libro_id`, `venta_id`, `usuario_id` en
   `movimiento_stock`, `cliente.usuario_id`).
5. Drop del `UNIQUE(isbn)` común de `libro` (reemplazado por el índice parcial).

**Por qué**:
- `autogenerate` no infiere bien `postgresql_where` ni siempre crea índices para FKs nuevas.
- El `UNIQUE` común bloquearía el reuso del ISBN de un libro dado de baja (RN-13).

**Alternativas descartadas**:
- *Dejar el `UNIQUE` común además del parcial*: bloquea el reuso del ISBN, violando RN-13/C-13.

### D-04 — `0004` escrita a mano con función + disparador

**Decisión**: escribir `0004` a mano con una función PL/pgSQL `movimiento_stock_no_modificable()` y un
disparador `BEFORE UPDATE OR DELETE ON movimiento_stock` que levanta una excepción. El `downgrade` hace
`DROP TRIGGER` y luego `DROP FUNCTION`.

**Por qué**:
- `autogenerate` no ve funciones ni disparadores (DD-04).
- Rechazar `UPDATE` y `DELETE` venga de donde venga (app, `psql`, script) es lo que pide RN-12.

**Alternativas descartadas**:
- *Rol de base sin permiso de escritura*: mecanismo alternativo; la consigna dice que cualquiera de los dos
  alcanza y el parcial usa un solo rol, así que el disparador es el camino pedido.

### D-05 — Orden del `downgrade` de `0004`

**Decisión**: en el `downgrade`, borrar primero el disparador y después la función (la función no se puede
borrar mientras el disparador la referencia).

**Por qué**:
- Evita el error «cannot drop function because other objects depend on it».

**Alternativas descartadas**:
- *`DROP FUNCTION ... CASCADE`*: borraría también el disparador, pero oculta la dependencia y es menos
  explícito.

### D-06 — Verificación round-trip + `alembic check`

**Decisión**: tras aplicar, correr `upgrade head` → `downgrade base` → `upgrade head` sobre base vacía y
`alembic check`, documentando la salida. También verificar las 8 piezas de `0003` y probar el disparador con
`UPDATE`/`DELETE` (caso C-14).

**Por qué**:
- CV-10 exige `alembic check` sin operaciones nuevas antes de entregar.
- El round-trip detecta migraciones que no bajan bien (por ejemplo, no borrar el disparador).

**Alternativas descartadas**:
- *Verificar sólo `upgrade head`*: no detecta problemas de `downgrade` (por ejemplo, disparador huérfano).

## Risks / Trade-offs

- [Autogenerate no infiere `postgresql_where`] → se corrige a mano y se documenta en el comentario de cabecera.
  Mitigación: lectura obligatoria antes de aplicar.
- [Base con el TP aplicado no disponible] → la implementación requiere PostgreSQL 16 local; si no hay, se
  prepara el archivo a mano basándose en los modelos y se verifica en cuanto haya base. Mitigación: documentar
  el comando exacto.
- [Disparador bloquea mantenimiento legítimo] → corregir un movimiento exige compensar con otro (RN-12).
  Mitigación: documentado en la KB.
- [Encadenamiento mal puesto] → `down_revision` de `0003` debe ser la revisión de `0002` (`5f67a857f685`).
  Mitigación: verificar con `alembic history`.
- [env.py sin import de usuarios] → autogenerate incompleto. Mitigación: agregar el import antes de generar.

## Migration Plan

1. Agregar `import app.modules.usuarios.models` a `migrations/env.py`.
2. Aplicar `0001` y `0002` a una base vacía (si no lo están).
3. Ejecutar `alembic revision --autogenerate -m "acceso y stock"`.
4. Leer la migración entera; corregir tipos, `postgresql_where`, `borrado_en`, índices de FKs, drop del
   `UNIQUE(isbn)`.
5. Agregar el comentario de cabecera con las correcciones.
6. Escribir `0004` a mano con función + disparador y su `downgrade`.
7. Aplicar `alembic upgrade head`.
8. Verificar las 8 piezas de `0003` y probar el disparador con `UPDATE`/`DELETE`.
9. Correr `alembic downgrade base` → `alembic upgrade head` y `alembic check`.
10. Rollback: `alembic downgrade 0002` (borra tablas/columnas/índices/disparador/función).

## Open Questions

Ninguna que cambie las specs, el enfoque o las tasks. La disponibilidad de una base PostgreSQL 16 local para
ejecutar `autogenerate` y el round-trip es un requisito operativo de la implementación, no una pregunta de
diseño.