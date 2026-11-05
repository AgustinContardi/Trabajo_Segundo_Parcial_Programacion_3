# Handoff — falta el TP de los capítulos 1-4

> **Para:** quien tenga acceso al TP cap. 1-4 entregado (compañero de grupo).
> **Motivo:** el change `C-01 baseline-tp-y-fundacion` está a mitad de camino. La mitad que **no**
> depende del TP ya está implementada y verificada; la otra mitad está **BLOQUEADA** esperando este
> material. Sin él no se puede cerrar `C-01`, y con `C-01` abierto quedan parados `C-02`, `C-03`,
> `C-04`, `C-20` y todo lo que depende de ellos.

Fecha del handoff: 2026-11-05.

---

## 1. Qué hay que entregar

El **TP de los capítulos 1-4 tal como se entregó** (sin limpiar, sin refactorizar, sin arreglos).
Tiene que incluir, sí o sí:

| # | Elemento | Para qué se necesita |
|---|---|---|
| 1 | Código completo del TP (catálogo, clientes, ventas) | Adoptarlo en `parcial/` sin reescribir su lógica (consigna p. 2 y Ej. 9) |
| 2 | `requirements.txt` original | Fijar las versiones reales del baseline |
| 3 | `alembic.ini` original | Reemplazarlo por el de este change (sin `sqlalchemy.url`) y no perder configuración |
| 4 | `migrations/0001` y `0002` | Conservar revisiones y `down_revision`; las migraciones nuevas (`0003`+) se cuelgan de ahí |
| 5 | El esquema real de la base (o la forma de levantarla) | Confirmar las 4 columnas heredadas de §5 |

Si el TP está en un `.zip`, sirve igual. Si está en un repo, mejor: pasá la URL y la rama/tag exacta
que se entregó.

---

## 2. Cómo entregarlo (elegí una)

### Opción A — carpeta local (más rápida, no se versiona)

1. Descomprimí el TP en una carpeta **temporal, fuera del repo**:
   ```
   C:\Users\sanch\AppData\Local\Temp\opencode\tp-cap1a4\
   ```
2. Avisá que está ahí. Con eso se ejecutan las tareas 7.1 a 7.9.

> No lo pongas dentro de `parcial/`: `parcial/` es el proyecto del parcial, y el TP se **adopta**
> encima de forma controlada, no se mezcla a mano.

### Opción B — zip dentro del repo pero ignorado por git

1. Copiá el `.zip` a `_incoming/tp-cap1a4.zip` (la carpeta `_incoming/` está ignorada por git).
2. Avisá que está ahí.

### Opción C — rama del repo

1. Creá una rama `baseline/tp-cap1a4` con el contenido **intacto** del TP y pusheala.
2. Avisá el nombre de la rama.

---

## 3. Las 4 preguntas que hay que contestar con evidencia

Estas son las únicas incógnitas del baseline (`knowledge-base/10_preguntas_abiertas.md` §2). No se
pueden adivinar: se leen del TP y se escriben en `docs/BASELINE_TP_CAP1a4.md`.

| Supuesto | Pregunta exacta | Dónde se mira |
|---|---|---|
| `SU-01` | ¿El `id` de las tablas heredadas es `integer`/`serial`, `bigint`/`bigserial` o `UUID`? | `migrations/0001`, `\d <tabla>` |
| `SU-07` | ¿`venta` tiene `usuario_id`? ¿Qué tipo y qué `ON DELETE`? | `migrations/0001`/`0002`, `\d venta` |
| `SU-08` | ¿Cómo se llama la columna que copia el precio al renglón de venta (`precio_unitario`, `precio`, …)? | `migrations/0001`, `\d renglon_venta` |
| `SU-09` | ¿Cuáles son los `revision` y los nombres de archivo de `0001` y `0002`? | `alembic history`, `migrations/versions/` |

Ejemplo de respuesta útil (lo que buscamos, no lo que hay que escribir todavía):

```
SU-09: 0001_crear_catalogo.py  revision=3f1a9c2d7b10  down_revision=None
       0002_crear_clientes_ventas.py  revision=a84e01f6c2b9  down_revision=3f1a9c2d7b10
```

---

## 4. Paso a paso para quien retome (tareas 7.1 a 7.9)

Desde la raíz del repo:

```powershell
# 7.1 — recibir y descomprimir fuera de parcial/
#       (ver Opción A/B/C de §2)

# 7.1 — verificar que el TP viene completo
Get-ChildItem $env:TEMP\opencode\tp-cap1a4 -Recurse -Depth 2 | Select-Object FullName
Get-ChildItem $env:TEMP\opencode\tp-cap1a4\migrations\versions | Select-Object Name

# 7.9 — el change a ejecutar
openspec status --change "c-01-baseline-tp-y-fundacion" --json
```

Después, con el agente:

```
/opsx:apply c-01-baseline-tp-y-fundacion
```

y pedirle **explícitamente el grupo 7** (`7.1` a `7.9`). El grupo 1-6 ya está hecho y verificado.

### Reglas que el que retome NO puede romper

1. **No reescribir la lógica del TP** (consigna p. 2 y Ej. 9). Se adopta tal cual; lo nuevo se agrega
   encima.
2. `despliegue/` es una copia **intacta** del TP. No se le mete nada del parcial
   (`movimiento_stock`, `AsignacionRol`, `UnitOfWork` → no deben aparecer ahí).
3. Las migraciones `0001` y `0002` **no se editan**. Ni un espacio.
4. `parcial/alembic.ini` es el de este change: **sin** `sqlalchemy.url`.
5. Nada de `create_all`: el esquema nace sólo de Alembic.
6. No se escribe `0003` hasta que `docs/BASELINE_TP_CAP1a4.md` esté cerrado.

---

## 5. Criterio de "listo" (definición de terminado para el que entrega)

El que entrega el material puede darse por terminado cuando:

- [ ] El TP está disponible en una de las tres formas de §2 y se puede abrir.
- [ ] `migrations/versions/` tiene **dos** archivos (`0001` y `0002`).
- [ ] Se puede correr `alembic history` en el TP y lista las dos revisiones.
- [ ] Están contestadas las 4 preguntas de §3, con el archivo/línea o la consulta que lo respalda.
- [ ] Se sabe cómo levantar la base del TP (credenciales, host, puerto, nombre) o se entrega el
      esquema volcado con `pg_dump --schema-only`.

Si falta cualquiera de los dos primeros puntos, no desbloquea: `C-01` sigue abierto.

---

## 6. Estado actual (para ubicarse)

| Ítem | Estado |
|---|---|
| `C-01` grupo 1-6 (mitad A) | **Implementado y verificado** — 20/28 tareas `[x]` |
| `C-01` grupo 7 (mitad B) | **BLOQUEADO** — 9 tareas `[ ]` con criterio de desbloqueo en `tasks.md` |
| `C-01` en `CHANGES.md` | `[~]` en curso — **no** se marca `[x]` hasta cerrar el grupo 7 |
| Change OpenSpec | `openspec/changes/c-01-baseline-tp-y-fundacion/` |
| Verificación pendiente por falta de PostgreSQL local | `3.3`, `3.4`, `3.5`, mitad DB de `4.4`, `5.3`, `6.5` |

Cuando el grupo 7 esté cerrado: `/opsx:archive c-01-baseline-tp-y-fundacion` y marcar `[x]` en
`CHANGES.md`.
