# Auditoría — C-01 baseline-tp-y-fundacion

**Veredicto: C-01 PASS (0 FAIL / 7 WARN)**
Fecha de auditoría: 2026-11-08 · Entorno: Windows, Python 3.13.2, PostgreSQL 17.11 (`127.0.0.1:5432`,
usuario `libreria`, base `libreria`). Auditoría de **solo lectura**: sin pytest, sin seed, sin uvicorn,
sin INSERT/UPDATE/DELETE; únicamente `SELECT`, `alembic check`, imports y ASGI en proceso (TestClient).

Los 7 WARN son ítems cuya re-verificación exigiría mutar la base (seed, base temporal vacía), levantar
uvicorn o correr pytest — prohibido en esta auditoría. Todos tienen evidencia registrada y creíble de la
verificación previa **2026-11-07** (PG 17.11) en `openspec/changes/archive/2026-11-05-c-01-baseline-tp-y-fundacion/tasks.md`.

---

## §0 — Reglas no negociables (aplicables a C-01)

| Ítem | Resultado | Evidencia |
|---|---|---|
| Paths exactos de la consigna, sin shims ni alias | ✅ verificado ahora | `app/core/{config,database,security,dependencies,repository,paginacion,unit_of_work}.py` presentes; 8 módulos con seis capas cada uno (salvo health); `main.py`, `migrations/env.py`, `versions/` en su lugar |
| Sin credenciales en `alembic.ini`, `env.example`, README, código ni historial git | ✅ verificado ahora | `alembic.ini` sin `sqlalchemy.url`; valores de `POSTGRES_PASSWORD`/`JWT_SECRET` de `env.example` **difieren** de `parcial/.env`; los valores reales del `.env` **no aparecen** en `git log -p --all` (búsqueda por valor exacto). Los `@password = admin12345`/`clave-segura-123` del historial son contraseñas **ficticias** de `test/*.http` y tests, no credenciales del entorno |
| Router construye UoW / servicio abre con `async with` / sólo `__aexit__` confirma | ✅ verificado ahora | `async with` en routers: **0**; `UnitOfWork(` en services: **0**; `commit()` en repositorios: **0**; `UnitOfWork.__aexit__` confirma/revierte y no cierra sesión |
| `selectinload` sólo en `repository.py` | ✅ verificado ahora | 20 coincidencias en `app/`, **todas** en archivos `repository.py` (docstrings o imports/uso legítimo); 0 en models/services/routers |
| Sin `password_hash` en schemas | ✅ verificado ahora | 0 coincidencias en `app/modules/*/schemas.py` |
| Ninguna regla de negocio fuera de la consigna | ✅ verificado ahora (inspección) | `seed.py` y servicios citan `RN-xx`/`CV-xx`; las reglas del dominio pertenecen a changes posteriores (C-02…C-17) ya auditados por separado |

## §1 — Estructura

| Ítem | Resultado | Evidencia |
|---|---|---|
| `main.py` con `lifespan` y **dos** grupos de rutas | ✅ verificado ahora | Lectura de `main.py`: `lifespan` con `yield`/`finally: engine.dispose()`; `router_abierto` (health, auth, catálogo público) y `router_protegido` (`Depends(control_cambio_password)`); 16 `include_router` en dos bloques |
| `seed.py` en raíz de `parcial/` y ejecutable | ⚠️ WARN — no re-verificado | Existe `parcial/seed.py` con `import app.modules.usuarios.models` (corrección de 2026-11-07). Ejecutarlo trunca la base → prohibido. Evidencia previa 6.4: `Seed OK` ×2 corridas idempotentes sobre base temporal migrada |
| `app/core/` con los 7 archivos | ✅ verificado ahora | Los 7 presentes; `errors.py` adicional es de C-05 (no es alias ni shim; nota menor) |
| 8 módulos, cada uno (salvo health) con seis capas | ✅ verificado ahora | `usuarios` agrega `router_admin.py` (C-15); los 8 módulos listados con `models/schemas/repository/unit_of_work/service/router` |
| `health` sólo tiene `router.py` | ✅ verificado ahora | Único `.py` del módulo es `router.py` (`__pycache__` es artefacto runtime; nota menor) |
| Entidades en su módulo obligatorio | ✅ verificado ahora | `AsignacionRol`/`IntentoAcceso`/`EventoSeguridad` en usuarios; `MovimientoStock`/`LibroAutor` en libros; `PerfilCliente` en clientes; `RenglonVenta` en ventas |
| `migrations/` con `env.py`, `versions/` y 4 versiones en `alembic history` | ✅ verificado ahora | `alembic history`: `0ba1752f7c23 → 5f67a857f685 → dd4a0e5e9cf7 → c8d2dea5529f (head)`. Nota menor: `0003`/`0004` tienen nombre descriptivo (`acceso_y_stock`, `append_only`) sin prefijo numérico — glob del checklist §3 no matchea; convención de C-04 |
| `test/` con `.http` y `solo_agregado.sql`; `tests/` sólo pytest | ✅ verificado ahora | `test/`: 5 `.http` + `solo_agregado.sql` + `EVIDENCIA.md`; `tests/`: 47 archivos, todos pytest (`test_*.py`, `conftest.py`, `registro_support.py`), sin `.http`/`.sql` |
| `env.example` (sin punto) y `.gitignore` con `.env` | ✅ verificado ahora | `parcial/env.example` existe; `.gitignore` con `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`; `git check-ignore parcial/.env` → `parcial/.env`; `git ls-files` sin `.env` |
| Sin `create_all` | ✅ verificado ahora | 0 coincidencias en todo `parcial/**/*.py` (excluidas menciones en comentarios) |

## §2 — Configuración

| Ítem | Resultado | Evidencia |
|---|---|---|
| `Settings` con las 13 variables | ✅ verificado ahora | Lectura de `config.py`: las 13 de CV-09 presentes; `COOKIE_SECURE` es extra deliberado de C-11 (documentado en design D-02) |
| URL con `@computed_field` y driver `postgresql+asyncpg` | ✅ verificado ahora | `Settings().database_url` empieza con `postgresql+asyncpg://`, host `127.0.0.1:5432/libreria`; contraseña fuera de `repr`; construida con `URL.create(...).render_as_string(hide_password=False)` |
| `POSTGRES_PASSWORD` y `JWT_SECRET` sin default (fail-fast) | ✅ verificado ahora (equivalente) | `Settings(_env_file=None)` → `ValidationError` mencionando **ambas** variables. La prueba literal «renombrar .env + uvicorn» no se repitió para no tocar `.env`; evidencia previa 2.3: uvicorn sale con `ValidationError` antes de escuchar |
| Motor y sessionmaker sólo en `lifespan`, en `app.state` (`pool_size=POOL_SIZE`, `expire_on_commit=False`); `get_session` una sesión por petición que cierra en `finally` | ✅ verificado ahora | Lectura de `database.py` y `main.py`; con TestClient+lifespan: `app.state.sessionmaker/hash_ficticio/bcrypt_sem` presentes; `get_session` con `try/yield/finally: session.close()` |
| `hash_ficticio` una vez + `dispose()` al apagar | ✅ verificado ahora | TestClient: tras el contexto, `engine.pool.checkedin() == 0` y `pg_stat_activity` sin conexiones de la app (sólo el `psql` de medición). `hash_ficticio` calculado con `asyncio.to_thread` bajo semáforo dentro del lifespan |
| `alembic.ini` sin `sqlalchemy.url` con credenciales; `env.py` lee de `Settings`; `.env` existe y no versionado | ✅ verificado ahora | `alembic.ini` sin la clave; `env.py` usa `Settings().database_url` + `NullPool`; `git check-ignore`/`git ls-files` confirmados |

## §3 — Migraciones (lo relevante a C-01)

| Ítem | Resultado | Evidencia |
|---|---|---|
| `alembic current` = head y `alembic check` sin diferencias modelos↔esquema | ✅ verificado ahora | `alembic current` → `c8d2dea5529f (head)`; `alembic check` → exit 0, «No new upgrade operations detected»; `alembic_version` en la base = `c8d2dea5529f`; 15 tablas (`pg_tables`: 14 de dominio + `alembic_version`) |
| Base vacía + `upgrade head` (y downgrade base) sin error | ⚠️ WARN — no re-verificado | Requiere crear base temporal (DDL → prohibido). Evidencia previa 5.3: base `libreria_c01_empty_17404`, `upgrade head` exit 0 aplicando las 4 revisiones, 15 tablas, base eliminada |
| Cuatro versiones (2 TP + autogenerada + manual) | ✅ verificado ahora (parcial) | `alembic history` lista las 4; contenido de 0003/0004 pertenece a C-04 (auditado por separado) |

## §10 — Pruebas (lo básico de C-01)

| Ítem | Resultado | Evidencia |
|---|---|---|
| Todos los handlers son `async def` | ✅ verificado ahora | `^\s*def ` sin `async` en routers: **0** coincidencias |
| `pytest` completo contra PostgreSQL real | ⚠️ WARN — no re-verificado | Prohibido correr pytest (base compartida). Evidencia previa 6.4: `pytest -q` → **413 passed** |

## Ítems de ciclo de vida verificados en esta auditoría (ASGI en proceso, sin servidor)

| Ítem | Resultado | Evidencia |
|---|---|---|
| `GET /health/live` 200 con base operativa | ✅ verificado ahora | TestClient con lifespan real → `200 {"status":"ok"}` |
| `GET /health/ready` 200 con base operativa | ✅ verificado ahora | TestClient → `200 {"status":"ok"}` (SELECT 1 contra PG 17.11) |
| `ready` 503 con puerto cerrado, `live` sigue 200, cuerpo sin detalles internos | ✅ verificado ahora | `POSTGRES_PORT=65431` → `live 200`, `ready 503 {"status":"unavailable"}`; log servidor con mensaje propio, sin driver/URL/traza |
| Importar no abre conexiones | ✅ verificado ahora | `python -c "import main"` exit 0; `pg_stat_activity` antes y después: 1 conexión (el propio `psql`), ninguna de la app; sin `.env` el import también es exit 0 |
| Apagado limpio (dispose) | ✅ verificado ahora (equivalente) | Tras el contexto TestClient: pool `checkedin()==0`, `pg_stat_activity` sin conexiones de la app. El `Ctrl+C` literal sobre uvicorn no se repitió (prohibido levantar uvicorn); evidencia previa 3.5 con `CTRL_BREAK_EVENT` |
| Una sesión por petición (SQL_ECHO) | ⚠️ WARN — no re-verificado | Requiere uvicorn (prohibido). Evidencia previa 3.4: 2×`GET /health/ready` → exactamente 2×`BEGIN/SELECT 1/ROLLBACK`, 1 conexión `idle` reutilizada, 0 tras apagar |
| Arranque limpio desde carpeta limpia (venv + pip + `.env` + `alembic upgrade head` + uvicorn + sondas) | ⚠️ WARN — no re-verificado | Requiere venv nuevo y uvicorn (prohibido). Evidencia previa 1.4/6.5 (2026-11-07): secuencia completa en `%TEMP%\opencode\c01-clean-room` con PG 17.11, `live`/`ready` 200. Limitación registrada: Python 3.13.2 (README pide 3.12) |

## Baseline TP cap. 1-4 (grupo 7)

| Ítem | Resultado | Evidencia |
|---|---|---|
| `despliegue/` copia intacta del TP, sin incorporaciones del parcial | ✅ verificado ahora | `despliegue/` con `app/`, `migrations/`, `alembic.ini`, `main.py`, `seed.py`, `requirements.txt`, `env.example`, `README.md`, `.gitignore`; grep `movimiento_stock|AsignacionRol|UnitOfWork` en `despliegue/` = **0** |
| `docs/BASELINE_TP_CAP1a4.md` con SU-01/SU-07/SU-08/SU-09 | ✅ verificado ahora | Ambos documentos existen: `docs/BASELINE_TP_CAP1a4.md`, `docs/HANDOFF_BASELINE_TP_CAP1a4.md`; contenido confirmado por CHANGES.md y tareas 7.6 |
| Migraciones 0001/0002 conservadas | ✅ verificado ahora | `alembic history` lista `0ba1752f7c23` (0001) y `5f67a857f685` (0002) como primeras revisiones encadenadas |

## Notas menores (no bloquean C-01)

1. `parcial/README.md` — «Integrantes» con placeholders `(integrante 1)/(integrante 2)`. Pendiente de **C-22** (§12: nombres y apellidos), fuera del alcance de C-01.
2. `parcial/README.md` paso 4 conserva la nota histórica «todavía no hay migraciones propias» — desactualizada (hoy hay 4 revisiones). Ya documentada como limitación en tasks.md 1.4; la secuencia ejecutable no cambia.
3. Migraciones sin prefijo `0003_`/`0004_` (nombres descriptivos) — el glob literal del checklist §3 no matchea; naming decidido en C-04, no en C-01.
4. `health/__pycache__/` presente (artefacto de ejecución); el módulo fuente sigue siendo sólo `router.py`.
5. `app/core/errors.py` adicional al set del checklist §1 — creado por C-05; no es shim ni alias.
6. `pytest` instalado globalmente da `StarletteDeprecationWarning` sobre `httpx2` en TestClient — cosmético, no afecta verificación.

## Cierre

Todo ítem de C-01 verificable **sin mutación y sin servidor** pasó en esta auditoría. Los 7 WARN quedan
soportados por la evidencia registrada de la verificación 2026-11-07 en `tasks.md` del archivo, que
describe comandos, salidas y bases temporales con detalle creíble. Sin hallazgos que contradigan el
estado `[x]` de C-01 en `CHANGES.md`.
