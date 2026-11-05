# KB Alignment Report — TP cap. 1-4 (consigna PDF)

**Fuente de verdad**: `docs/TP_Cap1a4_Consigna (1).pdf` (consigna de los capítulos 1-4), texto extraído en
`C:\Users\ramir\AppData\Local\Temp\opencode\consigna_out.txt`.
**Alcance**: alineación **dirigida** de las porciones cap. 1-4 de la knowledge base. No se regeneró
ningún archivo: se preservó todo el contenido cap. 5-8 y las secciones proyecto-específicas
(`DD`, `SU`, `CV`, `RD`, preguntas abiertas).
**Fecha**: 2026-11-05.

---

## 1. Archivos de la KB revisados

| Archivo | Revisado | Edits |
|---|---|---|
| `knowledge-base/01_vision_y_objetivos.md` | Sí (alcance/rúbrica) | No |
| `knowledge-base/02_descripcion_general.md` | Sí (stack, arquitectura, API) | Sí |
| `knowledge-base/03_actores_y_roles.md` | Sí (fuera de alcance cap 5-6, no tocado) | No |
| `knowledge-base/04_modelo_de_datos.md` | Sí (ERD, tablas, CHECKs, índices) | Sí |
| `knowledge-base/05_reglas_de_negocio.md` | Sí (RN-01..RN-12) | Sí |
| `knowledge-base/06_funcionalidades.md` | Sí (US y trazabilidad) | Sí |
| `knowledge-base/07_flujos_principales.md` | Sí (flujos E2E cap 1-4) | No |
| `knowledge-base/08_arquitectura_propuesta.md` | Sí (capas) | No |
| `knowledge-base/09_decisiones_y_supuestos.md` | Sí (DD/SU) | Sí |
| `knowledge-base/10_preguntas_abiertas.md` | Sí (preservado) | No |
| `knowledge-base/11_despliegue_y_devops.md` | No (cap. despliegue) | No |

---

## 2. Discrepancias encontradas y corregidas

### 2.1 Stack (`02_descripcion_general.md`)

- **Faltaba `python-dotenv 1.0`** en la tabla de stack. La consigna lo lista explícitamente
  («Requisitos técnicos», p. 3) para la lectura del `.env`. Se agregó la fila correspondiente.
- El resto del stack coincide con la consigna: Python 3.12, FastAPI 0.111, SQLModel 0.0.24,
  SQLAlchemy 2.0 async, asyncpg 0.30, PostgreSQL 16, Alembic 1.13 (plantilla asincrónica),
  pydantic-settings 2.0, uvicorn vía `fastapi[standard]`.

### 2.2 Modelo de datos (`04_modelo_de_datos.md`)

| Tabla | Discrepancia | Corrección |
|---|---|---|
| `editorial` | Faltaba la columna `pais` (consigna: `id, nombre, pais`). | Agregada `pais varchar NN`. |
| `autor` | KB tenía `nombre, apellido`; la consigna pide `nombre, nacionalidad`. | `apellido` → `nacionalidad`. |
| `cliente` | KB tenía `apellido, telefono` marcados «confirmar»; la consigna del TP sólo lista `id, nombre, email`. `telefono` pertenece a `perfil_cliente`. | `apellido` se mantiene como «confirmar» con nota de que **no** aparece en la consigna; `telefono` se **movió** a `perfil_cliente`. |
| `perfil_cliente` | Faltaba `telefono`. | Agregada `telefono varchar NULL`. |
| `libro` | `genero_id` estaba `NN`; la consigna dice nulo permitido. | `genero_id` → `NULL` (FK, índice, nulo permitido). |
| `libro_autor` | `rol` sólo mencionaba `'coautor'`; faltaban valores y CHECKs; la PK estaba «confirmar». | CHECK `rol IN ('autor','coautor','traductor','ilustrador')`, CHECK `orden >= 1`, PK `(libro_id, autor_id)`, índices en ambas FKs. |
| `venta` | Faltaba `CHECK (total >= 0)`; `usuario_id` no está en la consigna del TP. | Agregado CHECK; anotado SU-07 (confirmar contra el repo). |
| `renglon_venta` | Faltaban `CHECK (cantidad > 0)` y `CHECK (precio_unitario > 0)`; el nombre `precio_unitario` se confirmó. | Agregados ambos CHECKs; anotado como confirmado por la consigna. |

Además se agregaron a la vista consolidada de índices/restricciones: UNIQUE de `editorial.nombre` y
`genero.nombre`, UNIQUE de `perfil_cliente.cliente_id`, PK e índices de `libro_autor`, CHECKs de
`venta` y `renglon_venta`.

Los marcadores «heredado TP cap 1-4 — confirmar» se mantuvieron donde la consigna **no** restate la
columna (id type, `apellido`, `fecha_nacimiento`, columnas extra de `libro`, etc.), porque el TP real
no está en el repo.

### 2.3 Reglas de negocio (`05_reglas_de_negocio.md`)

- Se agregó el row `UNIQUE (perfil_cliente.cliente_id)` a la tabla «Reglas del TP que siguen vigentes»
  (consigna RN-09 del TP: un cliente tiene a lo sumo un perfil).
- Se agregó una sección nueva **«Reglas del TP cap 1-4 (numeración original de la consigna)»** que
  conserva la numeración `RN-01…RN-12` del PDF y dice **dónde vive hoy** cada una (parcial `RN-xx`
  renumerado, o «Reglas del TP que siguen vigentes»). Esto evita renumerar las reglas parciales
  `RN-01…RN-16`, que son la fuente que usa la corrección del parcial.
- El resto de `RN-01…RN-16` parciales se mantuvo intacto (son las reglas del parcial, no del TP).

### 2.4 Funcionalidades (`06_funcionalidades.md`)

- Se agregó una tabla de trazabilidad de los **casos mínimos `C-01…C-08` de la consigna** (p. 10-11)
  contra la numeración actual `C-01…C-16` del parcial, para que quede claro dónde vive cada caso
  (p. ej. C-03 «segundo perfil» → US-032; C-07 «detalle con consultas fijas» → C-15 parcial).

### 2.5 API (`02_descripcion_general.md`)

- Se separó `POST /autores` del grupo combinado con `/editoriales` y `/generos`: la consigna da a
  `POST /autores` los códigos **201, 422** (sin 409, porque `autor` no tiene unicidad ni FK en el TP).
  `/editoriales` y `/generos` mantienen 201, 409, 422.

### 2.6 Decisiones y supuestos (`09_decisiones_y_supuestos.md`)

- Se agregó **DD-19**: las dos migraciones heredadas del TP se generan con `--autogenerate` en el
  orden que exige la consigna (primera: todas las tablas **menos** `genero`; segunda: agrega la tabla
  `genero` y la columna `libro.genero_id`).
- Se agregó **SU-16**: documenta que la consigna del TP restate explícitamente `editorial.pais`,
  `autor.nacionalidad` y `perfil_cliente.telefono` (que faltaban), que `cliente.apellido` **no**
  aparece en la consigna, y que `libro.genero_id` es nulo permitido.

---

## 3. Items que NO se pudieron resolver desde la consigna (siguen bloqueados por el TP real)

Estos puntos la consigna **no** fija o el repo del TP cap 1-4 **no está en este repositorio**
(ver `docs/HANDOFF_BASELINE_TP_CAP1a4.md`). Requieren el baseline real para cerrarse:

1. **Tipo de las claves primarias (SU-01)** — la consigna fija nombres de columnas, no tipos.
   Se asume `bigint identity`. Validar contra `migrations/0001`.
2. **`venta.usuario_id` (SU-07 / AB-02)** — la consigna del TP **no** lista `usuario_id` en `venta`;
   no se sabe si existe, qué tipo tiene ni su `ON DELETE`. Se mantiene como «confirmar».
3. **Nombre exacto del precio copiado (SU-08)** — la consigna dice «el precio de cada renglón se
   copia» pero no imprime el nombre de la columna. Se asume `precio_unitario` (confirmado en el PDF
   de los renglones: `precio_unitario (NUMERIC 10,2)`); validar contra el TP.
4. **Revisiones y nombres de archivo de las migraciones 0001/0002 (SU-09)** — la consigna exige
   el orden (sin `genero` → con `genero`), pero no los revision IDs ni los nombres de archivo.
5. **`ON DELETE` de las claves foráneas** — la consigna no lo especifica en ninguna FK.
6. **Columnas extra del TP** — `autor` (¿sólo `nombre, nacionalidad`?), `cliente.apellido` (¿existe?),
   `libro` (año, páginas, etc.), `perfil_cliente.fecha_nacimiento` y demás columnas «confirmar»
   siguen sin poder confirmarse sin el repo del TP.
7. **`editorial.pais` nullability y tipo** — la consigna lista la columna pero no su nullability.
8. **Casos C-01..C-08 numeración** — el parcial renumeró los casos; la tabla agregada en
   `06_funcionalidades.md` mapea los conceptos, pero los `.http` reales del TP no están en el repo.

---

## 4. Lo que NO se tocó (por diseño)

- Todo el contenido cap. 5-8 (auth, RBAC, UoW, stock, despliegue) y las secciones `DD`, `SU`,
  `CV`, `RD`, preguntas abiertas y seed data: preservados intactos.
- `AGENTS.md` / `CLAUDE.md`: no se sincronizaron (la tarea era sólo la KB). Si se desea, regenerar
  con `/active-orchestrator` tras esta alineación.
- No se marcó ninguna tarea como completa ni se tocó código/migraciones.

---

## 5. Resumen de archivos modificados

- `knowledge-base/02_descripcion_general.md`
- `knowledge-base/04_modelo_de_datos.md`
- `knowledge-base/05_reglas_de_negocio.md`
- `knowledge-base/06_funcionalidades.md`
- `knowledge-base/09_decisiones_y_supuestos.md`
- `docs/KB_ALIGNMENT_REPORT.md` (este archivo)
