# Tasks — C-01 baseline-tp-y-fundacion

> Todo path de la aplicación es relativo a `parcial/`. Las tareas del grupo **7** están bloqueadas por un
> insumo externo (TP cap. 1-4) y **no** se ejecutan hasta que llegue. Las del grupos **1 a 6** se pueden
> implementar y verificar ya.

## 1. Esqueleto y dependencias (A — ejecutable ya)

- [x] 1.1 Crear `parcial/`, `parcial/app/`, `parcial/app/core/`, `parcial/app/modules/`, `parcial/app/modules/health/`, `parcial/migrations/`, `parcial/migrations/versions/` con `__init__.py` en `app/`, `app/core/` y `app/modules/` —**no** en `health/`, que debe contener sólo `router.py`— y verificar que la estructura existe: `Get-ChildItem -Recurse parcial | Select-Object FullName`.
- [x] 1.2 Escribir `parcial/requirements.txt` con los mínimos de la consigna (Python 3.12, `fastapi[standard]>=0.111`, `sqlmodel>=0.0.24`, `SQLAlchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `alembic>=1.13`, `pydantic-settings>=2.0`, `bcrypt>=4.0`, `PyJWT>=2.8`) y verificar en un venv limpio: `python -m venv .venv`, `pip install -r requirements.txt` sin errores.
- [x] 1.3 Escribir `parcial/env.example` (sin punto inicial) con las 13 variables y valores de ejemplo **no secretos**; escribir `.gitignore` con `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`. Verificar: `git check-ignore .env` devuelve `.env` y `git ls-files | Select-String "^\.env$"` no devuelve nada.
- [ ] 1.4 Escribir `parcial/README.md` con integrantes, requisitos y la puesta en marcha desde cero (`venv` → `pip install` → `.env` desde `env.example` → `alembic upgrade head` → `uvicorn main:app --reload`). Verificar: seguir los pasos literalmente en una carpeta limpia sin agregar nada que no esté escrito. — *No verificable aquí* (tramo final): el README está escrito y en una carpeta limpia se corrieron `python -m venv`, `pip install -r requirements.txt`, `import main` y `GET /health/live → 200`; los pasos 4-6 del README (`alembic upgrade head`, `ready → 200`) requieren un PostgreSQL que no existe en este entorno. **Comando pendiente**: en un entorno con base, repetir literalmente el README desde el paso 1.

## 2. Configuración fail-fast (A)

- [x] 2.1 Implementar `parcial/app/core/config.py` con `Settings` de `pydantic-settings` y las 13 variables de `CV-09`; `POSTGRES_PASSWORD` y `JWT_SECRET` como `SecretStr` **requeridos** (sin default); `database_url` como `@computed_field` construido con `sqlalchemy.engine.URL.create(drivername="postgresql+asyncpg", ...)` y `render_as_string(hide_password=False)`. Verificar: `python -c "from app.core.config import Settings; print(Settings().database_url)"` desde `parcial/` con `.env` completo imprime una URL que empieza con `postgresql+asyncpg://`.
- [x] 2.2 Resolver el `env_file` con una ruta absoluta derivada de `__file__` (`parents[2] / ".env"`) y exponer `get_settings()` con `@lru_cache`, invocado **sólo** desde el `lifespan` y `migrations/env.py`, nunca al importar. Verificar: `python -c "import main"` sin `.env` no falla por configuración y `grep -n "get_settings()" app main.py` no muestra llamadas a nivel de módulo.
- [x] 2.3 Verificar el fail-fast: renombrar `.env` a `.env.bak`, correr `uvicorn main:app` y confirmar que falla con error de validación de `pydantic-settings` (menciona `POSTGRES_PASSWORD` o `JWT_SECRET`) **antes** de escuchar; restaurar `.env`.
- [x] 2.4 Verificar el escapado de credenciales: con una contraseña de prueba que contenga `@`, `:` y `%`, comprobar que `Settings().database_url` sigue siendo parseable y que usuario/contraseña no se cortan. Verificación: `python -c "from app.core.config import Settings; from sqlalchemy.engine import make_url; print(make_url(Settings().database_url).password)"` devuelve la contraseña original completa.
- [x] 2.5 Dejar en `config.py` el comentario de contrato: `COOKIE_SECURE` se agrega en `C-11` junto con la cookie; los secretos no tienen default y no se registran en logs. Verificación: leer el archivo y confirmar que no hay ningún valor por defecto para `POSTGRES_PASSWORD` ni `JWT_SECRET`.

## 3. Ciclo de vida y sesión por petición (A)

- [x] 3.1 Implementar `parcial/app/core/database.py` con `crear_engine(settings)` (`pool_size=POOL_SIZE`, `echo=SQL_ECHO`), `crear_sessionmaker(engine)` (`expire_on_commit=False`) y `get_session(request)` que toma `request.app.state.sessionmaker`, entrega una sesión y la cierra en `finally`. Verificar: `grep -n "create_async_engine\|async_sessionmaker\|app.state\|finally\|close()" app/core/database.py` muestra las cuatro piezas y ninguna creación a nivel de módulo.
- [x] 3.2 Implementar `parcial/main.py` con `lifespan(app)`: `Settings()`, motor, fábrica de sesiones, `asyncio.Semaphore(BCRYPT_MAX_CONCURRENCY)` y `hash_ficticio` calculado una sola vez con `await asyncio.to_thread(...)`; guardar todo en `app.state`; `yield`; `await engine.dispose()` en el `finally`. Verificar: `grep -n "hash_ficticio\|dispose\|app.state\|to_thread\|Semaphore" main.py` muestra todas las piezas y el hash se calcula dentro del `lifespan`.
- [ ] 3.3 Verificar que importar no abre recursos: con `.env` ausente, `python -c "import main; print('ok')"` imprime `ok`; con `.env` presente, `python -c "import main"` no deja conexiones abiertas (comprobar en `pg_stat_activity` que no aparece una conexión nueva por el import). — *No verificable aquí*: sin PostgreSQL no hay `pg_stat_activity`. La mitad «importar no abre recursos» sí se verificó: `import main` sin `.env` imprime `ok` (exit 0), con `.env` no existe ningún `AsyncEngine` (`engines_al_importar=0`, `tiene_engine_global=False`). **Comando pendiente**: `SELECT count(*) FROM pg_stat_activity` antes y después de `python -c "import main"` contra una base real.
- [ ] 3.4 Verificar una sesión por petición: levantar `uvicorn main:app`, hacer dos `GET /health/ready` consecutivos y confirmar con `SQL_ECHO=true` que cada petición usa una conexión/sesión propia y que al terminar no queda una conexión retenida por la petición. Verificación: los dos `200` y el log de SQL de cada petición. — *No verificable aquí*: requiere PostgreSQL para el `200` y para el log de `SQL_ECHO`; sin base, las dos peticiones devuelven `503` antes de emitir SQL. **Comando pendiente**: con base y `SQL_ECHO=true`, dos `GET /health/ready` y revisar el log + `pg_stat_activity`.
- [ ] 3.5 Verificar el apagado: detener uvicorn con `Ctrl+C` y confirmar que el `finally` del `lifespan` corre `engine.dispose()` sin excepción y que las conexiones de la aplicación desaparecen de `pg_stat_activity`. Verificación: log de apagado limpio + consulta posterior. — *No verificable aquí*: `pg_stat_activity` no existe y `Ctrl+C` sobre uvicorn no se puede automatizar contra una base inexistente. El `dispose()` del `finally` se ejercitó con `TestClient` (pool con `checkedin()==0` tras el apagado) pero no contra el servidor. **Comando pendiente**: uvicorn con base, `Ctrl+C` y consulta posterior.

## 4. Sondas de salud (A)

- [x] 4.1 Implementar `parcial/app/modules/health/router.py` —**único archivo** del módulo, sin `__init__.py`— con `GET /health/live` (sin base, `200`) y `GET /health/ready` (`SELECT 1`; `200` si contesta, `503` con cuerpo fijo `{"status": "unavailable"}` si no). Verificar: `Get-ChildItem app/modules/health` muestra sólo `router.py`, y ambos handlers son `async def`.
- [x] 4.2 En `ready`, capturar la excepción de conexión, registrar la causa con `logging` del lado del servidor y no devolver texto del driver, la URL ni la traza. Verificar: forzar el fallo (puerto de base cerrado) y revisar que el `503` no contiene detalles internos.
- [x] 4.3 Registrar el router en `main.py` con `app.include_router(...)` en el grupo abierto. Verificar: `grep -n "include_router" main.py` muestra el registro de `health` y `GET /openapi.json` lista las dos rutas.
- [ ] 4.4 Verificar las dos sondas con la base operativa (`live` → `200`, `ready` → `200`) y con `POSTGRES_PORT` apuntando a un puerto cerrado (`live` → `200`, `ready` → `503`). Verificación: las cuatro respuestas con `curl`/`Invoke-RestMethod`. — *Verificado parcialmente*: `live → 200` (TestClient y uvicorn real) y puerto cerrado → `ready → 503 {"status":"unavailable"}` (sin detalles internos) están verificados; `ready → 200` con base operativa **no** es verificable sin PostgreSQL. **Comando pendiente**: con base arriba, `Invoke-RestMethod http://127.0.0.1:8000/health/ready` → `200`.

## 5. Alembic sin credenciales (A)

- [x] 5.1 Escribir `parcial/alembic.ini` con `script_location = migrations` y **sin** `sqlalchemy.url`. Verificar: `Select-String -Path alembic.ini -Pattern "sqlalchemy.url"` no devuelve una línea con valor (sólo puede aparecer un comentario).
- [x] 5.2 Implementar `parcial/migrations/env.py` con la plantilla asincrónica: `Settings()`, `create_async_engine(settings.database_url, poolclass=pool.NullPool)`, `connection.run_sync(...)`, `target_metadata = SQLModel.metadata` y el comentario de que `C-03`/`C-04` deben importar los modelos antes de autogenerar. Verificar: leer el archivo y confirmar que no hay URL hardcodeada ni lectura de `config.get_main_option("sqlalchemy.url")`.
- [ ] 5.3 Verificar contra una base vacía: `alembic current` y `alembic upgrade head` desde `parcial/` no fallan por configuración. Verificación: ambos comandos terminan con código 0 (sin migraciones propias todavía, el historial queda vacío). — *No verificable aquí*: `alembic history` (vacío) y `alembic upgrade head --sql` (modo offline) terminan en 0, lo que prueba que configuración y `Settings` se leen bien; `alembic current` y `upgrade head` online fallan **sólo al conectar** a `127.0.0.1:5432` (no hay PostgreSQL). **Comando pendiente**: con base vacía, `alembic current` y `alembic upgrade head` → exit 0.
- [x] 5.4 Verificar que no hay creación implícita de esquema: `grep -rn "create_all" parcial --include=*.py` vacío. Verificación: el comando no devuelve líneas.
- [x] 5.5 Dejar en `migrations/env.py` el comentario de la regla 9: toda migración autogenerada se lee antes de aplicarse y se corrige a mano si infiere mal un tipo o un índice. Verificación: el comentario existe y `C-04` lo va a heredar.

## 6. Verificación integral de la mitad (A)

- [x] 6.1 Verificar que todos los handlers son asincrónicos: `grep -rn "def " app/modules/*/router.py | grep -v "async def"` vacío. Verificación: el comando no devuelve líneas.
- [x] 6.2 Verificar la estructura de la consigna para lo que este change crea: `ls app/core`, `ls app/modules/health`, `ls migrations`, `ls migrations/versions`. Verificación: existen `config.py`, `database.py`, `health/router.py` (sólo ese archivo), `migrations/env.py` y `migrations/versions/`, sin alias.
- [x] 6.3 Verificar que no hay credenciales versionadas ni en `alembic.ini`, ni en `env.example`, ni en `README.md`, ni en el código. Verificación: `git log -p | Select-String -Pattern "password|secret|DATABASE_URL"` no muestra valores reales (sólo nombres de variables).
- [ ] 6.4 Correr literalmente la Aceptación de `C-01` en `docs/CHECKLIST_ENTREGA.md` (§0; §1: `main.py` con `lifespan`, `health` sólo `router.py`, `env.example`, `.gitignore`, `create_all` vacío; §2: los seis primeros; §10: handlers `async def`; §13 fila «Proyecto, configuración y ciclo de vida») y dejar la salida en el resumen de aplicación del change. Verificación: cada comando ejecutado y su salida pegada; si un comando no se puede correr, el ítem queda pendiente. — *Parcialmente verificable*: se corrieron los comandos que no necesitan base (paths, `create_all` vacío, `env.example`, `.gitignore`, `.env` ignorado, handlers `async def`, `include_router`, `config.py`, `database.py`, `main.py`, `alembic.ini`) y la salida quedó en «Verificación de aplicación (mitad A)»; quedan pendientes los ítems que exigen `seed.py`, las cuatro migraciones y PostgreSQL (§1 completo, §2 con base, §10 con `pytest`). **Comando pendiente**: aceptación completa sobre el proyecto con el TP adoptado (tarea 7.9).
- [ ] 6.5 Verificar el arranque completo desde una carpeta limpia: venv nuevo, `pip install -r requirements.txt`, `.env` desde `env.example`, `uvicorn main:app` y `GET /health/live` + `GET /health/ready` con `200`. Verificación: la secuencia corre tal como está escrita en `parcial/README.md`. — *No verificable aquí* (último paso): en una carpeta limpia se verificaron venv nuevo, `pip install -r requirements.txt`, `.env` desde `env.example`, `import main` y `live → 200`; falta `ready → 200` porque no hay PostgreSQL. **Comando pendiente**: repetir la secuencia con base operativa.

## 7. Baseline TP cap. 1-4 (B — BLOQUEADO)

> **Bloqueante externo `IN-BASE-01`/`IN-BASE-02`**: el TP cap. 1-4 no está en el repo. Nada de este grupo se
> ejecuta hasta recibirlo. **Desbloqueo**: repo o `.zip` del TP disponible, con `alembic history` ejecutable
> y las cuatro columnas heredadas confirmables contra `migrations/0001` y `0002`.

- [x] 7.1 BLOQUEADO: recibir y descomprimir el TP cap. 1-4 (código, `requirements.txt`, `alembic.ini`, `migrations/0001` y `0002`) en una carpeta temporal fuera de `parcial/`. — *Desbloqueo*: `IN-BASE-01` entregado. — *Verificación*: `alembic history` del TP lista dos revisiones y `Get-ChildItem` muestra el código de catálogo, clientes y ventas.
- [x] 7.2 BLOQUEADO: adoptar el TP en `parcial/` **sin reescribir su lógica**: conservar rutas, contratos y comportamiento; los cambios del parcial se agregan encima. — *Desbloqueo*: 7.1. — *Verificación*: el conjunto de rutas del TP está presente con el mismo método y path, y los casos heredados responden igual que en el original.
- [x] 7.3 BLOQUEADO: copiar el TP **intacto** a `despliegue/` como proyecto separado, sin ninguna incorporación del parcial. — *Desbloqueo*: 7.1. — *Verificación*: `grep -rn "movimiento_stock\|AsignacionRol\|UnitOfWork" despliegue/` vacío y el contenido coincide con el TP recibido.
- [x] 7.4 BLOQUEADO: reemplazar en `parcial/` el `alembic.ini` heredado por el de este change (sin `sqlalchemy.url`) y conservar `migrations/0001` y `0002` con sus revisiones y `down_revision` originales. — *Desbloqueo*: 7.1. — *Verificación*: `alembic history` lista las dos revisiones en orden y `Select-String -Path alembic.ini -Pattern "sqlalchemy.url"` no muestra valor.
- [x] 7.5 BLOQUEADO: comparar las migraciones `0001`/`0002` adoptadas con las originales y confirmar que son idénticas (sin ediciones). — *Desbloqueo*: 7.4. — *Verificación*: `Compare-Object` (o `git diff --no-index`) de cada archivo devuelve diferencia vacía.
- [x] 7.6 BLOQUEADO: inspeccionar el esquema heredado y escribir `docs/BASELINE_TP_CAP1a4.md` con el valor confirmado y la evidencia de `SU-01` (tipo de `id`), `SU-07` (`venta.usuario_id` o la columna que exista), `SU-08` (nombre del precio copiado en `renglon_venta`) y `SU-09` (revisiones y nombres de archivo de las migraciones). — *Desbloqueo*: 7.1 + `IN-BASE-02`. — *Verificación*: el documento tiene los cuatro supuestos con evidencia (archivo/línea/migración/consulta) y ninguno quedó como «probable».
- [x] 7.7 BLOQUEADO: verificar que el esquema heredado quedó intacto tras la adopción. — *Desbloqueo*: 7.2 y 7.4. — *Verificación*: `\dt` y `\d <tabla>` de catálogo, clientes y ventas contra el TP original: no falta, sobra ni se renombró ninguna columna; dinero y fechas conservan su tipo; `alembic upgrade head` sobre base vacía termina sin error.
- [x] 7.8 BLOQUEADO: confirmar que `despliegue/` sigue sin ninguna modificación del parcial y que su lógica no se tocó. — *Desbloqueo*: 7.3. — *Verificación*: comparación con el TP original sin diferencias de código; sólo se admiten los artefactos de despliegue que agregará `C-20`.
- [x] 7.9 BLOQUEADO: cerrar la Aceptación completa de `C-01` con el baseline adoptado (incluye volver a correr §0, §1, §2 y §10 sobre el proyecto ya completo) y recién entonces marcar `C-01` como `[x]` en `CHANGES.md`. — *Desbloqueo*: 7.1 a 7.8. — *Verificación*: todos los comandos de la Aceptación corren literalmente contra `parcial/` con el TP adoptado, y `docs/BASELINE_TP_CAP1a4.md` existe.

## Workflow follow-up

- **No archivar el change completo** hasta que el grupo 7 esté ejecutado; la mitad (A) puede mergearse y usarse como base de `C-02`/`C-03`.
- Cuando (A) esté verificada, avisar en el roadmap que `C-01` sigue en curso por el bloqueante externo y no marcar `[x]` en `CHANGES.md`.
- Al cerrar (B), archivar con `/opsx:archive` y actualizar `CHANGES.md`.

## Verificación de aplicación (mitad A)

**Fecha**: 2026-11-05
**Entorno**: Windows, Python 3.12.10, `parcial/.venv` (venv limpio), paquetes resueltos por `pip`:
`fastapi 0.162.0`, `sqlmodel 0.0.48`, `SQLAlchemy 2.1.8`, `asyncpg 0.32.0`, `alembic 1.20.1`,
`pydantic-settings 2.16.2`, `bcrypt 5.0.0`, `PyJWT 2.15.1`, `uvicorn 0.54.0`.
**Limitación**: no hay PostgreSQL, ni `psql`, ni `docker`, ni `pytest` instalados. Todo lo que exige una base
real quedó `[ ]` con el comando pendiente.

| Tarea | Comando corrido | Resultado |
|---|---|---|
| 1.1 | `Get-ChildItem -Recurse parcial -Directory` | Existen `app/`, `app/core/`, `app/modules/`, `app/modules/health/`, `migrations/`, `migrations/versions/` |
| 1.2 | `python -m venv .venv` + `.venv\Scripts\python.exe -m pip install -r requirements.txt` | `Successfully installed …` (sin errores) |
| 1.3 | `git check-ignore parcial/.env` / `git ls-files \| Select-String "^parcial/\.env$"` | `parcial/.env` / sin coincidencias |
| 1.4 | README + carpeta limpia: venv, `pip install`, `import main`, `TestClient` | venv + instalación + `live → 200`; falta `alembic upgrade head` y `ready → 200` (sin base) |
| 2.1 | `python -c "from app.core.config import Settings; print(Settings().database_url)"` | `postgresql+asyncpg://libreria:clave%40local%3Ase%25gura@127.0.0.1:5432/libreria` |
| 2.2 | `Rename .env` + `python -c "import main; print('import-ok')"`; `Select-String get_settings\(\)` | `import-ok`, exit 0; `get_settings()` sólo en la definición y dentro del `lifespan` |
| 2.3 | `.env` renombrado + `uvicorn main:app --port 8899` | exit 3, `pydantic_core.ValidationError … for Settings` con `POSTGRES_PASSWORD` y `JWT_SECRET`; nunca imprimió `Uvicorn running` |
| 2.4 | `make_url(Settings().database_url).password` | `clave@local:se%gura` (round-trip exacto, `driver=postgresql+asyncpg`) |
| 2.5 | Lectura de `config.py` + `repr(Settings())` | Sin defaults en los dos secretos; `SecretStr('**********')` y `database_url` fuera del `repr` |
| 3.1 | `Select-String "create_async_engine\|async_sessionmaker\|app.state\|finally\|close()" app/core/database.py` | Las cuatro piezas; `create_async_engine` sólo dentro de `crear_engine` |
| 3.2 | `Select-String "hash_ficticio\|dispose\|app.state\|to_thread\|Semaphore" main.py` + `TestClient` | Todo dentro del `lifespan`; tras arrancar: `hash_ficticio` (60 bytes), semáforo 4, `async_sessionmaker`; tras apagar: `pool.checkedin()==0` |
| 3.3 | `python -c "import main"` sin `.env`; conteo de `AsyncEngine` tras importar | `ok`, exit 0; `engines_al_importar=0`, `tiene_engine_global=False` (la mitad `pg_stat_activity` queda pendiente) |
| 3.4 | uvicorn real + dos `GET /health/ready` | Sin base: `503` en ambas; falta el `200` y el log SQL con `SQL_ECHO=true` |
| 3.5 | `TestClient` (arranque/apagado) | `dispose()` ejecutado sin excepción, pool en 0; falta `Ctrl+C` + `pg_stat_activity` |
| 4.1 | `Get-ChildItem app/modules/health` + revisión de handlers | Sólo `router.py`; `live` y `ready` son `async def` |
| 4.2 | `GET /health/ready` con puerto cerrado | `503` con cuerpo exacto `{"status":"unavailable"}`; log del servidor: «Sonda de disponibilidad fallida: la base no responde» (sin driver, URL ni traza) |
| 4.3 | `Select-String include_router main.py` + `GET /openapi.json` | `app.include_router(health_router)`; paths `['/health/live', '/health/ready']` |
| 4.4 | uvicorn real: 2×`live`, 2×`ready`; TestClient | `live[1]=200`, `live[2]=200`; `ready=503`; falta `ready → 200` (sin base) |
| 5.1 | `Select-String -Path alembic.ini -Pattern "sqlalchemy.url"` | Sin coincidencias (tampoco hay valor) |
| 5.2 | Lectura de `migrations/env.py` | `Settings()`, `create_async_engine(..., poolclass=pool.NullPool)`, `connection.run_sync`, `target_metadata = SQLModel.metadata`; sin URL hardcodeada ni `config.get_main_option` |
| 5.3 | `alembic --help`, `alembic history`, `alembic upgrade head --sql`, `alembic current` | `history` exit 0 (vacío) y `upgrade head --sql` exit 0 (`BEGIN; … COMMIT;`); `current` falla sólo al conectar a `127.0.0.1:5432` |
| 5.4 | `grep -rn "create_all" parcial --include=*.py` | Sin coincidencias |
| 5.5 | Lectura de `migrations/env.py` | Comentario de la regla 9 presente |
| 6.1 | `grep "def " app/modules/*/router.py \| grep -v "async def"` | Sin coincidencias |
| 6.2 | `ls app/core`, `ls app/modules/health`, `ls migrations`, `ls migrations/versions` | `config.py`, `database.py`, `__init__.py` / `router.py` / `env.py`, `versions/` / `.gitkeep` |
| 6.3 | `git log -p \| Select-String "password\|secret\|DATABASE_URL"`; búsqueda de valores del `.env` local | Sólo nombres de variables y texto de documentación; ninguna asignación de valor; sin valores del `.env` en archivos versionables |
| 6.4 | Aceptación §0, §1, §2, §10, §13 (comandos sin base) | Ver arriba; los ítems con `seed.py`, cuatro migraciones, `pytest` o base quedan pendientes |
| 6.5 | Carpeta limpia (`Temp\opencode\c01-limpia`): venv, `pip install`, `.env`, `TestClient` | `import-ok`, `live: 200`, `ready: 503 {"status":"unavailable"}`; falta `ready → 200` |

**Ítems no verificables en este entorno** (quedan `[ ]` con el comando pendiente en la tarea):
3.3 (`pg_stat_activity`), 3.4 (dos `200` con `SQL_ECHO`), 3.5 (`Ctrl+C` + `pg_stat_activity`), 4.4
(`ready → 200` con base), 5.3 (`alembic current` / `upgrade head` online), 1.4 (pasos 4-6 del README),
6.4 (aceptación completa, depende de `seed.py` y las cuatro migraciones), 6.5 (`ready → 200`).

**Estado de OpenSpec**:

```
Change: c-01-baseline-tp-y-fundacion
Schema: spec-driven
Progress: 4/4 artifacts complete

[x] proposal
[x] specs
[x] design
[x] tasks

All planning artifacts complete!
```

`openspec validate "c-01-baseline-tp-y-fundacion" --strict` → `Change 'c-01-baseline-tp-y-fundacion' is valid`.
