# Design — C-01 baseline-tp-y-fundacion

## Context

Ver `proposal.md` — Why. El repo sólo tiene documentación (`knowledge-base/`, `docs/`, `CHANGES.md`) y
OpenSpec; no existe código de aplicación. El diseño tiene que resolver dos problemas distintos:

1. **Fundación (A)**: dejar un proceso FastAPI que arranque, valide configuración, abra recursos en el
   `lifespan`, atienda una sesión por petición y exponga salud, sin esquema y sin lógica de dominio.
2. **Baseline (B)**: incorporar un TP cap. 1-4 que **no está disponible**. El diseño no puede describir
   su esquema; sólo puede definir cómo se verificará y qué se hará cuando llegue.

Restricciones que mandan sobre el diseño:

- 18 reglas duras de `AGENTS.md`: sin `create_all`, secretos sin default, esquema sólo por Alembic,
  migraciones autogeneradas leídas antes de aplicar, FK indexadas, dinero `NUMERIC`, fechas `timestamptz`,
  bcrypt fuera del event loop, token sólo en cookie, UoW construido por el router.
- Checklist §0, §1, §2 (primeros seis), §10 y §13 «Proyecto, configuración y ciclo de vida».
- `knowledge-base/08_arquitectura_propuesta.md` §Estructura, §Configuración, §Ciclo de vida.
- `knowledge-base/11_despliegue_y_devops.md`: `parcial/` y `despliegue/` son **dos proyectos distintos**.

Todos los paths de la aplicación son **relativos a `parcial/`** (`parcial/app/core/config.py`,
`parcial/main.py`, etc.). `docs/BASELINE_TP_CAP1a4.md` vive en la raíz del repo.

## Goals / Non-Goals

**Goals:**

- Que `uvicorn main:app` levante con sólo copiar `env.example` a `.env` y completar valores.
- Que el proceso falle **antes de escuchar** si falta un secreto, con el error de validación de
  `pydantic-settings` y sin traza de credenciales.
- Que el motor y la fábrica de sesiones nazcan en el `lifespan` y mueran con `dispose()`.
- Que `/health/live` y `/health/ready` distingan «vivo» de «listo» y no filtren detalles internos.
- Que `alembic.ini` se pueda versionar sin credenciales y que Alembic use la misma configuración que la app.
- Dejar el baseline **declarado como bloqueante externo**, con criterios de aceptación verificables.

**Non-Goals (de diseño):**

- No se crean `repository.py`, `unit_of_work.py`, `paginacion.py`, `security.py` ni `dependencies.py`:
  pertenecen a `C-02`/`C-11` y acá sólo se reserva su lugar en la estructura.
- No se crean modelos de dominio ni migraciones `0003`/`0004` (`C-03`/`C-04`).
- No se implementan los dos grupos de rutas (abierto/protegido): el grupo protegido necesita auth
  (`C-11`). En `main.py` queda sólo el grupo abierto con `health`.
- No se crea el `Dockerfile` ni se toca `despliegue/` más allá de la copia intacta (bloqueada).
- No se toca la lógica del TP heredado. Ni siquiera para «modernizarla».

## Decisions

### D-01 — Partir el change en (A) ejecutable y (B) bloqueado, sin inventar el baseline

**Decisión**: las tareas (A) se implementan ya; las (B) quedan `BLOQUEADO:` con razón y criterio de
desbloqueo. Ningún artefacto declara nombres de tablas heredadas, tipo de `id` ni revisiones de Alembic.

**Por qué**: el esquema heredado es un contrato con un material que no tenemos. Un nombre inventado
(`precio_unitario`, `bigint`, `0001_initial`) se propaga a modelos, migraciones y contratos, y descubrirlo
tarde obliga a rehacer `C-03`/`C-04` y posiblemente el seed. El costo de esperar es menor que el de
contaminar el esquema.

**Alternativas descartadas**:
- *Inventar un baseline mínimo plausible*: viola la consigna (no reescribir el TP) y la regla de no agregar
  reglas que no están.
- *Bloquear todo el change hasta recibir el TP*: deja el repo sin base y sin forma de validar configuración
  y `lifespan`, que sí son independientes.

### D-02 — `Settings` con trece variables, secretos `SecretStr` y URL derivada con `URL.create`

**Decisión**: `pydantic-settings` con `SettingsConfigDict(env_file=<parcial>/.env, extra="ignore")`.
`POSTGRES_PASSWORD` y `JWT_SECRET` son `SecretStr` **requeridos** (sin default). La URL es un
`@computed_field` que usa `sqlalchemy.engine.URL.create(drivername="postgresql+asyncpg", ...)` y devuelve
`render_as_string(hide_password=False)`.

**Por qué**:
- `SecretStr` evita que la contraseña o la clave aparezcan en `repr`, logs o mensajes de error de validación.
- `URL.create` escapa correctamente `@`, `:`, `/` y `%` en usuario y contraseña. Una f-string rompe con
  contraseñas reales y con la interpolación `%` de `alembic.ini`.
- El `env_file` se resuelve con `Path(__file__).resolve().parents[2] / ".env"` para que funcione tanto si
  uvicorn se lanza desde `parcial/` como si los tests corren desde la raíz del repo.
- `get_settings()` con `@lru_cache` se llama **sólo** dentro del `lifespan` y de `migrations/env.py`; nunca
  al importar, para que importar `app` no exija un entorno completo.

**Alternativas descartadas**:
- *Una única `DATABASE_URL`*: la consigna pide variables sueltas y `@computed_field`.
- *`str` plano para secretos*: se filtra en `repr` y en errores.
- *`Settings()` a nivel de módulo*: convierte un error de configuración en un error de import, antes de que
  el `lifespan` pueda reportarlo.

`COOKIE_SECURE` (la fila 14 de la tabla de la KB) **no** entra en este change: la checklist §2 fija las 13
de `CV-09`, y la cookie se implementa en `C-11`. Se agregará ahí, junto con el resto de la configuración de
autenticación. Queda anotado para que no se olvide.

### D-03 — Motor y fábrica de sesiones en el `lifespan`, guardados en `app.state`

**Decisión**: `app/core/database.py` no crea nada al importar. Expone:
- `crear_engine(settings) -> AsyncEngine` con `pool_size=settings.POOL_SIZE`, `echo=settings.SQL_ECHO`.
- `crear_sessionmaker(engine) -> async_sessionmaker[AsyncSession]` con `expire_on_commit=False`.
- `get_session(request: Request) -> AsyncGenerator[AsyncSession, None]`: toma
  `request.app.state.sessionmaker`, hace `session = factory()`, `try: yield session`, `finally:
  await session.close()`.

`main.py` define `lifespan(app)`: crea `Settings`, motor, fábrica, semáforo de bcrypt y `hash_ficticio`;
los guarda en `app.state`; `yield`; y en el `finally` hace `await engine.dispose()`.

**Por qué**:
- Un motor creado al importar nace antes de que exista el bucle de eventos y produce el síntoma «funciona
  al levantar el servidor y falla en los tests, o al revés». Con el `lifespan`, el ciclo de vida lo controla
  el mismo mecanismo en producción y en tests (`httpx.ASGITransport` + `LifespanManager` o `TestClient`).
- `app.state` es el lugar canónico de FastAPI para recursos de aplicación; no hace falta un singleton
  global ni variables de módulo mutables.
- `expire_on_commit=False` es obligatorio para que el servicio pueda construir la respuesta después del
  `commit` del UoW sin reabrir una transacción (regla `CV-02`).
- `finally` garantiza cierre de sesión incluso con excepción; el UoW no cierra la sesión que no creó.

**Alternativas descartadas**:
- *Motor global + `Depends` con `async_sessionmaker` importado*: difícil de testear, recursos fuera del
  ciclo de vida, y el pool no se libera al apagar.
- *`lru_cache` sobre `get_engine()`*: oculta el apagado y complica el `dispose()`.

### D-04 — `hash_ficticio` una sola vez, con `to_thread` y semáforo

**Decisión**: en el `lifespan`, crear `app.state.bcrypt_sem = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY)`
y calcular `app.state.hash_ficticio = bcrypt.hashpw(HASH_DUMMY, bcrypt.gensalt(rounds=...))` dentro de
`await asyncio.to_thread(...)` y del semáforo.

**Por qué**: RN-08 exige que el login tarde lo mismo exista o no el correo. Calcularlo por petición
duplicaría el costo y haría que el tiempo dependa de la carga; calcularlo al importar bloquearía el import.
`to_thread` respeta la regla de no bloquear el event loop, y el semáforo queda listo para `C-11`.

**Alternativas descartadas**: hash perezoso en la primera petición (el primer login tendría otro perfil de
tiempo y una carrera entre peticiones concurrentes).

### D-05 — Sondas separadas, `ready` con `SELECT 1` y 503 genérico

**Decisión**: `app/modules/health/router.py` con dos handlers `async def`:
- `GET /health/live` → `{"status": "ok"}` sin dependencias de base.
- `GET /health/ready` → usa `get_session`, ejecuta `SELECT 1`; en éxito `200`; en cualquier excepción de
  conexión responde `503` con un cuerpo fijo (`{"status": "unavailable"}`) y registra la causa en el log
  del servidor.

**Por qué**: el proceso puede estar vivo y no listo; el `HEALTHCHECK` de la imagen (`C-20`) necesita esa
distinción. No se expone el texto del driver ni la URL. `/health/live` no debe tocar el pool porque un
`live` que depende de la base reinicia un proceso sano cuando la base está caída.

**Alternativas descartadas**: un único `/health` (la consigna pide dos y el checklist §1 lo verifica).

### D-06 — Alembic lee de `Settings`, sin `sqlalchemy.url` en el `.ini`

**Decisión**: `alembic.ini` conserva `script_location = migrations` y **no** define `sqlalchemy.url`.
`migrations/env.py` (plantilla asincrónica) hace `settings = Settings()` y
`engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)`; ejecuta las migraciones con
`connection.run_sync(...)`. `target_metadata = SQLModel.metadata` (vacío hasta que `C-03` cree los modelos;
`C-04` deberá importarlos antes de autogenerar).

**Por qué**:
- El `.ini` se versiona y no puede llevar credenciales (checklist §0 y §2).
- Construir el motor directo desde `Settings` evita la interpolación `%` de `alembic.ini`, que rompe con
  contraseñas que contienen `%` y obliga a escapar `%%`.
- `NullPool` evita que un proceso de migración de vida corta retenga conexiones.
- `target_metadata = SQLModel.metadata` deja la base lista para `alembic revision --autogenerate` en `C-04`,
  con el recordatorio explícito de importar los modelos antes.

**Alternativas descartadas**: `config.set_main_option("sqlalchemy.url", ...)` (funciona, pero obliga a
escapar `%` y mantiene la URL en la configuración de Alembic); `env.py` con URL hardcodeada (prohibido).

### D-07 — Estructura mínima ahora, módulos de dominio cuando toquen

**Decisión**: crear `parcial/`, `parcial/app/`, `parcial/app/core/`, `parcial/app/modules/`,
`parcial/app/modules/health/` y `parcial/migrations/versions/`, con `__init__.py` en `app/`, `app/core/` y
`app/modules/`. `health/` queda **sin** `__init__.py` para que el único archivo sea `router.py`, como exige
el checklist §1 (Python 3 lo importa como paquete de espacio de nombres). **No** crear carpetas vacías de
`usuarios`, `clientes`, etc.: cada módulo nace en su change con sus seis capas reales.

**Por qué**: una carpeta vacía de `libros` no cumple la estructura (le faltan las seis capas) y sugiere un
avance que no existe. El checklist §1 se completa a lo largo de los changes; `C-01` sólo es responsable de
`health` con `router.py`, `main.py`, `env.example`, `.gitignore` y la ausencia de `create_all`.

**Alternativas descartadas**: crear las ocho carpetas con archivos vacíos para «cumplir» el `ls` (ruido y
falsa señal de progreso).

### D-08 — Dependencias con mínimos, no con `==` inventados

**Decisión**: `requirements.txt` usa `>=` con las versiones mínimas de la consigna y `fastapi[standard]`
para arrastrar uvicorn. No se fijan versiones exactas no verificadas.

**Por qué**: el entorno de corrección instala con `pip install -r requirements.txt`; fijar un patch que no
existe rompe la instalación. `>=` cumple «versión mínima» y deja que pip resuelva. `C-22` puede congelar el
árbol con `pip freeze` si hace falta reproducibilidad.

### D-09 — Baseline: criterios de aceptación, no suposiciones

**Decisión**: la adopción (B) se verifica con: rutas y comportamiento heredados conservados, migraciones
`0001`/`0002` idénticas y encadenadas, esquema heredado intacto (`\dt`/`\d` contra el original), documento
`docs/BASELINE_TP_CAP1a4.md` con los cuatro supuestos y su evidencia, y `despliegue/` idéntico al TP.
Los criterios viven en `specs/legacy-baseline/spec.md`.

**Por qué**: sin el material, lo único honesto es definir qué se va a comprobar. Eso permite recibir el TP
y ejecutar una aceptación objetiva, sin discusión sobre interpretaciones.

**Alternativas descartadas**: escribir un `docs/BASELINE_TP_CAP1a4.md` con valores «probables» y marcarlo
como pendiente. Un documento con datos no verificados se lee como verificado.

### D-10 — Prohibiciones que el esqueleto debe dejar explícitas

**Decisión**: en `main.py`, `database.py` y `config.py` se dejan comentarios de contrato que fijan:
no `create_all`; el esquema sólo por Alembic; ninguna migración autogenerada se aplica sin leerla; las FK
nuevas llevan índice; dinero `NUMERIC`/`Decimal`; fechas nuevas `timestamptz`; el token sólo en cookie; el
router construye el UoW (`CV-01`); los repositorios sólo `flush()` (`CV-02`); `selectinload` sólo en
`repository.py` (`CV-03`).

**Por qué**: este change no escribe esas capas, pero sí el lugar donde se van a escribir. Los comentarios
evitan que el primer módulo (`C-06`/`C-07`) copie un patrón incorrecto desde el esqueleto.

## Risks / Trade-offs

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El TP cap. 1-4 no llega | `C-01` no se puede archivar; `C-02`, `C-03` y `C-20` quedan bloqueados | Se implementa (A) ya; (B) queda con criterio de desbloqueo explícito; se escala al grupo/cátedra |
| El TP llega con un esquema distinto al que asume la KB | Hay que ajustar modelos y migraciones de `C-03`/`C-04` | No se escribe `0003` hasta cerrar `docs/BASELINE_TP_CAP1a4.md`; la verificación es `\d` contra el original |
| El TP trae `alembic.ini` con URL/credenciales | Se versionaría un secreto | Al adoptarlo, se reemplaza por el `.ini` sin URL de (A) y se revisa el historial de git antes de commitear |
| El TP usa `create_all` o un `id` no entero | Rompe reglas duras | La regla es no reescribir lógica, pero sí se corrige lo que impide cumplir la consigna; se documenta en `BASELINE_TP_CAP1a4.md` y en `DEPLOY.md` si afecta el despliegue |
| Contraseñas con `%`, `@` o `:` rompen la URL | La app no conecta | `URL.create` + `render_as_string`, no f-string |
| Los tests no ejecutan el `lifespan` | `app.state` vacío y fallos sólo en pytest | Test explícito de arranque/apagado; documentar el uso de `TestClient` o `LifespanManager` |
| Windows local vs Alpine en el contenedor | Wheels de `asyncpg`/`bcrypt` distintos | Local con Python 3.12; la imagen se valida en `C-20`, no acá |
| `COOKIE_SECURE` se olvida en `C-11` | Falla el checklist de cookie | Anotado en D-02 y en las tareas de `C-11` (fuera de este change) |

## Migration Plan

1. **(A) ahora**: crear el esqueleto en `parcial/`; no hay migraciones nuevas ni cambios de esquema. La
   aplicación arranca contra una base vacía y `/health/ready` responde `200` si PostgreSQL contesta.
   Rollback: borrar `parcial/` (todavía no hay datos ni migraciones propias).
2. **(B) al recibir el TP**: copiar el TP a `parcial/` y a `despliegue/`; reemplazar el `alembic.ini`
   heredado por el de (A); verificar `alembic history`, `\dt`/`\d` y los criterios de
   `specs/legacy-baseline/spec.md`; escribir `docs/BASELINE_TP_CAP1a4.md`; recién entonces marcar `C-01`
   como `[x]` en `CHANGES.md`. Rollback: restaurar la copia original del TP; `despliegue/` es descartable
   hasta `C-20`.
3. **Cierre**: no se archiva el change completo hasta que (B) esté hecho; (A) se puede mergear y usar como
   base de `C-02`/`C-03` mientras tanto.

## Open Questions

Ninguna que cambie las specs, el enfoque o las tareas. Lo que falta —tipo de `id`, `venta.usuario_id`,
nombre del precio copiado y revisiones de las migraciones— es un **bloqueante externo** documentado en
`proposal.md` §Bloqueantes, no una pregunta de diseño.
