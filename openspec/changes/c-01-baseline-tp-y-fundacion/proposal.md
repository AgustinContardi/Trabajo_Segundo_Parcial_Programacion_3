# Proposal — C-01 baseline-tp-y-fundacion

## Why

El repositorio no tiene todavía ninguna base ejecutable: no existen `parcial/`, `app/`, `migrations/` ni
`requirements.txt`. `C-01` es el **GATE 0** del roadmap: sin configuración, ciclo de vida y estructura no
puede empezar ninguno de los otros 21 changes, y una de las condiciones que anulan la corrección es «un
proyecto que no levanta».

Al mismo tiempo, la consigna exige que el parcial **se construya sobre el TP de los capítulos 1-4**
(catálogo, clientes, ventas, migraciones `0001` y `0002`) sin reescribir su lógica. Ese material **no está
en el repo** y el grupo no lo tiene a mano. Inventarlo —nombres de tablas heredadas, tipo de `id`,
revisiones de Alembic— sería peor que no hacerlo: contaminaría el esquema y rompería `upgrade head`.

Por eso este change se parte en dos mitades explícitas:

- **(A) Fundación**: todo lo que no depende del TP y se puede implementar ya. Baja el riesgo de «no
  levanta» y deja el terreno listo para el GATE 1.
- **(B) Adopción del baseline**: bloqueada hasta recibir el TP cap. 1-4. No se especula: se define **qué
  debe verificarse cuando llegue**.

## What Changes

### (A) Ejecutable ya — fundación de la aplicación

- Crear el esqueleto `parcial/` con la estructura obligatoria de `knowledge-base/08_arquitectura_propuesta.md`
  (sólo los paquetes y `__init__.py`; los módulos de dominio quedan para `C-06`…`C-10`).
- `parcial/requirements.txt` con las versiones mínimas de la consigna (Python 3.12, FastAPI 0.111,
  SQLModel 0.0.24, SQLAlchemy 2.0 async, asyncpg 0.30, Alembic 1.13, pydantic-settings 2.0, bcrypt 4.0,
  PyJWT 2.8).
- `app/core/config.py`: `Settings` de `pydantic-settings` con las **13 variables**, URL armada con
  `@computed_field` y driver `postgresql+asyncpg`. `POSTGRES_PASSWORD` y `JWT_SECRET` **sin default**: si
  faltan, la aplicación no arranca.
- `app/core/database.py` + `main.py`: motor y `async_sessionmaker` creados **sólo** dentro del `lifespan`,
  guardados en `app.state` (`pool_size=POOL_SIZE`, `expire_on_commit=False`); `get_session` entrega una
  sesión por petición y la cierra; `hash_ficticio` calculado **una vez** al arrancar; `engine.dispose()` al
  apagar. Nada se crea al importar.
- `app/modules/health/router.py` **y sólo `router.py`**: `GET /health/live` (no toca la base) y
  `GET /health/ready` (`SELECT 1`; **503** si la base no contesta).
- `alembic.ini` **sin** `sqlalchemy.url`; `migrations/env.py` (plantilla asincrónica) lee la URL de
  `Settings`. No se escribe ninguna migración nueva.
- `env.example` (sin punto inicial, con todas las variables, **sin secretos**), `.gitignore` con `.env`,
  `.dockerignore` no aplica acá (pertenece a `despliegue/`, `C-20`).
- `README.md` mínimo de `parcial/` con la puesta en marcha desde cero.

### (B) Bloqueado — adopción del baseline TP cap. 1-4

- Copiar el TP cap. 1-4 **ya entregado** a `parcial/` (código, `requirements.txt`, `alembic.ini`,
  `migrations/0001` y `0002`), **sin reescribir su lógica** (consigna p. 2 y Ej. 9).
- Copiar el mismo TP, **intacto**, a `despliegue/` como proyecto separado (regla de oro de
  `knowledge-base/11_despliegue_y_devops.md`): `despliegue/` **no** recibe nada del parcial.
- Cerrar las columnas heredadas y escribir `docs/BASELINE_TP_CAP1a4.md`: `SU-01` (tipo de `id`), `SU-07`
  (`venta.usuario_id`), `SU-08` (nombre del precio copiado en `renglon_venta`), `SU-09` (revisiones y
  nombres de archivo de las migraciones `0001`/`0002`). Mientras no exista ese documento, **ninguna
  migración nueva redefine esas columnas** (sólo agrega las indicadas).

### Non-goals (fuera de este change)

- `app/core/repository.py`, `unit_of_work.py`, `paginacion.py`, `security.py`, `dependencies.py` → `C-02`,
  `C-11`.
- Modelos de dominio, migraciones `0003`/`0004`, seed, auth, RBAC, CRUD → changes posteriores.
- `Dockerfile`, `.dockerignore`, `DEPLOY.md`, despliegue en el VPS → `C-20`/`C-21`.
- Cualquier corrección o refactor del TP heredado: no se toca su lógica.

## Capabilities

### New Capabilities

- `app-foundation`: configuración obligatoria y fail-fast, ciclo de vida del motor y de la sesión por
  petición, sondas de salud vivo/listo, configuración de Alembic sin credenciales y estructura de
  directorios obligatoria.
- `legacy-baseline`: conservación verificable del TP cap. 1-4 adoptado (esquema heredado intacto,
  migraciones `0001`/`0002` encadenadas, columnas dudosas cerradas y documentadas, copia intacta en
  `despliegue/`).

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío y este es el primer change del proyecto.

## Bloqueantes / Inputs requeridos

| ID | Insumo | Estado | Consecuencia |
|---|---|---|---|
| **IN-BASE-01** | Repo o `.zip` del **TP cap. 1-4** ya entregado (código, `requirements.txt`, `alembic.ini`, `migrations/0001` y `0002`) | **FALTANTE — bloqueante externo** | Sin él no se puede adoptar el baseline, ni cerrar `SU-01`/`SU-07`/`SU-08`/`SU-09`, ni encadenar las migraciones nuevas |
| **IN-BASE-02** | Respuesta del grupo/cátedra sobre las columnas heredadas listadas en `knowledge-base/10_preguntas_abiertas.md` §2 | **FALTANTE** | Sin él no se puede escribir `docs/BASELINE_TP_CAP1a4.md` |

**Criterio de desbloqueo**: el TP cap. 1-4 disponible en el repo (o entregado al agente), con su
`alembic history` ejecutable, y las cuatro columnas heredadas confirmadas contra las migraciones `0001` y
`0002`.

## Estado de completitud

- Las tareas de **(A)** se pueden implementar y verificar **ya**; no dependen de ningún insumo externo.
- Las tareas de **(B)** quedan `[ ]` con el prefijo `BLOQUEADO:` en `tasks.md`.
- **El change no se puede archivar completo** hasta que llegue el material del TP cap. 1-4. Se puede
  archivar (o dejar en curso) la mitad (A) sin marcar `C-01` como `[x]` en `CHANGES.md`, porque el roadmap
  exige el baseline adoptado para habilitar `C-02`, `C-03` y `C-20`.

## Impact

- **Código nuevo**: `parcial/` (estructura, `main.py`, `app/core/config.py`, `app/core/database.py`,
  `app/modules/health/router.py`, `migrations/env.py`, `alembic.ini`, `requirements.txt`, `env.example`,
  `.gitignore`, `README.md`) y, cuando se desbloquee, `despliegue/` (copia intacta del TP).
- **Documentación nueva**: `docs/BASELINE_TP_CAP1a4.md` (bloqueada).
- **API**: sólo `GET /health/live` y `GET /health/ready`. Ninguna ruta de dominio.
- **Dependencias**: fija el stack mínimo; no agrega paquetes fuera de la consigna.
- **Changes aguas abajo**: `C-02`, `C-03` y `C-20` no pueden empezar hasta que `C-01` esté completo. La
  mitad (A) ya deja `config.py`, `database.py` y el `lifespan` utilizables por `C-02`/`C-03`.
- **Riesgo principal**: que el TP cap. 1-4 no llegue, o que llegue con un esquema incompatible con lo que
  asume la KB. Se mitiga no inventando nada y dejando el cierre documentado como criterio de aceptación.
