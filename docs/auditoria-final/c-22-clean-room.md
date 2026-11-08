# Auditoría final — C-22 corrida limpia

- **Fecha de la corrida**: 2026-11-08
- **Commit de partida**: `00111072e0a117abf6bd25885420edfc09190f79`
- **Sistema operativo**: Windows 11 (`Microsoft Windows NT 10.0.26300.0`)
- **Python local**: `3.13.2`
- **PostgreSQL local**: `17.11` en `127.0.0.1:5432` (usuario `libreria`)
- **Docker local**: no instalado (`docker --version` → comando no reconocido)
- **Alcance**: corrida limpia de §12 y de los ítems de §2, §3, §7 y §8 que
  dependen de una base vacía; en la continuación del 2026-11-08 se ejecutaron
  los cinco `.http` reales (5.10), se recorrió §0–§10 sección por sección (5.11)
  y se verificó la paridad Python 3.12 / PostgreSQL 16 en el VPS (5.14).
  No se re-ejecutaron literalmente los 136 ítems: §0–§10 tienen un registro por
  sección y §11–§13 se reutilizan de C-20/C-21/C-22. Lo no ejecutado se marca
  **no ejecutado** más abajo.
- **Fuera del alcance**: generar el `.zip`, commit, push, archivar el change y
  tocar el despliegue público. Nada de eso se hizo en esta corrida.

## 1. Entorno temporal

La corrida se hizo en una copia fuera del repositorio,
`<TEMP>\c22-cleanroom-20261108`, creada con `robocopy /E` excluyendo `.venv`,
`__pycache__`, `.pytest_cache`, `.ruff_cache` y `.env`.

```text
robocopy parcial    <TEMP>\c22-cleanroom-20261108\parcial    /E /XD .venv __pycache__ .pytest_cache .ruff_cache /XF .env
robocopy despliegue <TEMP>\c22-cleanroom-20261108\despliegue /E /XD .venv __pycache__ .pytest_cache .ruff_cache /XF .env
```

Resultado: `robocopy parcial=1 despliegue=1` (códigos de éxito de robocopy: se
copiaron archivos). Auditoría inmediata de la copia antes de instalar nada:

```text
no forbidden artifacts in copy
```

Comparación con lo versionado (`git ls-files parcial despliegue`):

```text
tracked files: 207
missing in copy: 0
extra untracked project files in copy: 0
```

La base exclusiva se creó vacía y no se tocó `libreria`:

```text
CREATE DATABASE
No se encontró ninguna relación.   # \dt antes de migrar
```

## 2. Dependencias y `.env` descartable

```text
python -m venv <TEMP>\c22-cleanroom-20261108\parcial\.venv
python -m pip install -r requirements.txt        -> exit 0
python -m pip install pytest pytest-asyncio httpx -> exit 0
```

Versiones efectivamente instaladas en la copia:

```text
alembic==1.20.1
asyncpg==0.32.0
bcrypt==5.0.0
fastapi==0.162.2
httpx==0.28.1
pydantic-settings==2.16.2
PyJWT==2.15.1
pytest==9.2.0
pytest-asyncio==1.4.1.post1
SQLAlchemy==2.1.8
sqlmodel==0.0.48
```

El `.env` se generó a partir de `env.example` con `POSTGRES_DB=parcial_c22_clean`,
la contraseña local descartable y un `JWT_SECRET` nuevo. El archivo quedó sólo en
la copia temporal; sus valores no se reproducen en este documento y no se
copiaron al repositorio.

Revisión de los ejemplos y de la higiene de secretos:

```text
parcial/env.example:
  POSTGRES_PASSWORD=<placeholder>
  JWT_SECRET=<placeholder>
despliegue/env.example:
  POSTGRES_PASSWORD=<placeholder>
  DATABASE_URL documentada como forma: postgresql+asyncpg://<usuario>:<clave>@...
git check-ignore -v parcial\.env despliegue\.env -> ambos ignorados por su .gitignore
git ls-files | Select-String '(^|/)\.env$' -> sin resultados
git grep de credenciales -> sólo placeholders y ejemplos de documentación
git log -p --all -> sólo placeholders y ejemplos; sin credenciales reales
despliegue/.dockerignore -> excluye .env, .venv, .git y __pycache__
```


## 3. Migraciones (base vacía)

```text
alembic history
c8d2dea5529f -> 5229054e2bcc (head), 0005 now() reales en los defaults de fecha
dd4a0e5e9cf7 -> c8d2dea5529f, 0004 append only (movimiento_stock)
5f67a857f685 -> dd4a0e5e9cf7, acceso y stock
0ba1752f7c23 -> 5f67a857f685, 0002 add genero
<base> -> 0ba1752f7c23, 0001 initial tp baseline
```

```text
alembic upgrade head   -> exit 0 (0001, 0002, 0003, 0004, 0005)
alembic current        -> 5229054e2bcc (head), exit 0
alembic check          -> "No new upgrade operations detected.", exit 0
alembic downgrade base -> exit 0 (0005, 0004, 0003, 0002, 0001)
alembic upgrade head   -> exit 0 (ciclo completo)
```

Catálogo de la base recién migrada:

```text
tablas: 15                        # 14 de dominio + alembic_version
FK sin índice: (sin filas)
columnas NUMERIC: libro.precio, renglon_venta.precio_unitario, venta.total
columnas timestamptz: asignacion_rol.desde, asignacion_rol.revocada_en,
  asignacion_rol.vence_en, evento_seguridad.cuando, intento_acceso.cuando,
  libro.borrado_en, movimiento_stock.cuando, venta.fecha
índices únicos parciales: uq_asignacion_rol_abierta, uq_libro_isbn_vigente
trigger: trg_movimiento_stock_no_modificable
defaults now(): asignacion_rol.desde, evento_seguridad.cuando,
  intento_acceso.cuando, movimiento_stock.cuando, venta.fecha
```

## 4. Seed e idempotencia

```text
python seed.py   # corrida 1 -> exit 0
python seed.py   # corrida 2 -> exit 0
```

Las dos corridas imprimieron exactamente los mismos conteos:

```text
usuario: 5          asignacion_rol: 5      editorial: 3       genero: 3
autor: 6            libro: 5                cliente: 3         perfil_cliente: 1
venta: 1            renglon_venta: 2        movimiento_stock: 7
evento_seguridad: 1 venta 1: total 69000.00
```

Controles posteriores a la segunda corrida:

```text
alembic_version: 5229054e2bcc            # el seed no toca la versión
libros 1–5 stock: 10 5 8 3 1
venta 1 total: 69000.00; renglones: 2; movimientos: 7
evento: SISTEMA / Carga de los datos iniciales
invariante libro.stock = SUM(movimiento_stock.cantidad): 0 violaciones
```

## 5. Suite de pruebas

```text
python -m pytest -q
472 passed, 1 skipped, 6 warnings in 145.97s (exit 0)
```

El único `skip` es `tests/test_seed_ejecucion.py`, que exige `SEED_E2E=1` porque
vacía la base. Se corrió aparte para cubrirlo:

```text
$env:SEED_E2E=1; python -m pytest -q tests/test_seed_ejecucion.py
1 passed in 5.32s (exit 0)
```

## 6. Arranque y salud

```text
uvicorn main:app --host 127.0.0.1 --port 8123
GET /health/live  -> 200 {"status":"ok"}
GET /health/ready -> 200 {"status":"ok"}
```

El proceso se detuvo al terminar; el puerto 8123 quedó libre. No quedó ningún
`uvicorn` en ejecución.

## 7. Formato de entrega (§12) y verificaciones puntuales

### §12 — estructura de la copia

```text
Raíz: parcial/, despliegue/                       # dos carpetas, sin contenedora
parcial/: main.py, seed.py, requirements.txt, env.example, alembic.ini,
          README.md, app/, migrations/ (5 versiones), test/, evidencia/
parcial/evidencia/: c-10-backgroundtasks.txt, c-14_solo_agregado.txt,
                    c-15_consultas_2y4.txt        # las tres capturas críticas
despliegue/: Dockerfile, .dockerignore, env.example, DEPLOY.md, README.md,
             app/, main.py, migrations/, evidencia/
despliegue/evidencia/: D-01.md … D-08.md           # 8 archivos
```

Auditoría de artefactos prohibidos en la copia **antes** de instalar el entorno:

```text
no forbidden artifacts in copy
```

`git ls-files parcial despliegue` no trackea `.env`, `.venv`, `__pycache__`,
`.pytest_cache`, `.ruff_cache` ni `*.pyc` (`tracked forbidden: 0`). Los
artefactos que aparecen en la copia después de instalar son generados por la
propia corrida y no están versionados; el zip futuro sale de `git archive`.

El nombre `Parcial_Cap1a6_AURA.zip` **no se verificó**: el zip no existe todavía
y su generación queda para la fase autorizada.

### §12 — READMEs

Ambos READMEs contienen el bloque:

```md
## Integrantes

Grupo **AURA**

- Enzo Giaquinta
- Agustin Contardi
- Fernando Torrez
- Ramiro Salcedo
- Ignacio Sanchez
```

No quedan `_(integrante` ni la nota de “pendiente hasta C-22”. `parcial/README.md`
tiene la secuencia venv → dependencias → `.env` con generación de la clave de
firma → `alembic upgrade head` → `python seed.py` (con la advertencia de que
**vacía la base**) → `uvicorn` → salud. `despliegue/README.md` conserva sus pasos;
sólo cambió el bloque de integrantes.

### §2 — configuración

```text
Settings: 13 variables (POSTGRES_*, JWT_SECRET, TTL, bcrypt, login, pool, echo)
database_url: postgresql+asyncpg://<usuario>:<password>@127.0.0.1:5432/parcial_c22_clean
sin .env: Settings() -> exit 1, 6 validation errors (5 POSTGRES_* + JWT_SECRET)
motor/sessionmaker: sólo en lifespan de main.py; engine.dispose() en el finally
alembic.ini: no contiene sqlalchemy.url; la URL sale de Settings en migrations/env.py
```

### §3 — migraciones y modelo

Ya detallado en §3 de este documento: cinco revisiones, ciclo completo, sin
drift, 15 tablas, FKs indexadas, dinero `NUMERIC`, fechas nuevas `timestamptz`,
dos índices únicos parciales, trigger de sólo agregado y `now()` en los cinco
defaults.

### §7 — capas y transacciones

```text
commit() en repository.py: 0
UnitOfWork(...) construido en service.py: 0
unit_of_work.py por módulo: 7 (todos salvo health)
PATCH /ventas: 0 en ventas/router.py
selectinload: sólo en repository.py (la única mención fuera es el docstring de main.py)
```

Excepción declarada y ya documentada en C-11: `app/modules/usuarios/service.py`
recibe un `async_sessionmaker` para escribir `intento_acceso` en transacción
propia (DD-05). No es una violación nueva ni se introdujo en C-22.

### §8 — ventas, stock y catálogo

```text
No existe PATCH /ventas.
Seed: venta 1 total 69000.00, 2 renglones, 7 movimientos, evento SISTEMA.
Invariante de stock: 0 violaciones después de cada seed.
Suite: 472 passed; cubre venta 201/409/422, rollback sin escrituras,
reposición, baja lógica de libros, PATCH parcial y paginación.
```

En la corrida limpia original los casos `.http` no se re-ejecutaron; en la
continuación 5.10 sí se corrieron los cinco archivos (ver §11): `auth` 12/12,
`registro` 7/7, `roles` 28/28, `libros` 25/25 y `ventas` 19/19. La pasada con
la GUI de VS Code REST Client no se hizo; se usó `httpyac` como runner HTTP
real sobre copias de compatibilidad.

### §11 — despliegue (sólo lectura)

```text
GET https://libreria.enzogiaquinta.me/health/live  -> 200
GET https://libreria.enzogiaquinta.me/health/ready -> 200
GET https://libreria.enzogiaquinta.me/libros/      -> 200 (catálogo con datos)
```

`despliegue/DEPLOY.md` declara URL pública, fecha/hora, `docker build` y
`docker run` con `--env-file` (nombre/ruta, sin contenido). Están D-01…D-08; se
revisaron D-01, D-03 y D-06. No se reconstruyó la imagen de despliegue ni se
modificó el servicio público; la paridad 3.12/16 se corrió aparte con recursos
temporales en el VPS (§13).

## 8. Sustitución de versiones

| Requisito | Usado en esta corrida | Estado |
|---|---|---|
| Python 3.12 | Python 3.13.2 local; **Python 3.12.16 en el VPS** | **verificado** (5.14) |
| PostgreSQL 16 | PostgreSQL 17.11 local; **PostgreSQL 16.15 en el VPS** | **verificado** (5.14) |

Motivo de la sustitución local: es el entorno disponible en la máquina. La
verificación compensatoria se ejecutó el 2026-11-08 en el VPS con
`python:3.12-alpine` y `postgres:16-alpine`; el detalle y la limpieza están en
§13. La corrida local sigue siendo 3.13.2/17.11 y así se declara.

## 9. No ejecutado

| Ítem | Motivo |
|---|---|
| Recorrido literal de los 136 ítems | §0–§10 se recorrieron por sección (ver §12); §11–§13 se reutilizan de C-20/C-21/C-22. No se ejecutó el comando de cada ítem. |
| Pasada con la GUI de VS Code REST Client | Se usó `httpyac` 6.16.7 como runner HTTP real sobre copias de compatibilidad (5.10); no se abrió la GUI. |
| Comparación de tiempos de C-04 | No se midió de nuevo; se reutiliza C-18 y la suite. |
| Reinicio del contador de intentos tras un login correcto | Cubierto por la suite; no se aisló en 5.10. |
| Conteo de SELECT de C-15 | Se reutiliza `parcial/evidencia/c-15_consultas_2y4.txt`; en 5.10 solo se re-ejecutaron los contratos 201/200. |
| Re-ejecución de la imagen (`D-01`, `D-02`, `D-05`, `D-06`, `D-07`) | Docker local ausente; se revisó la evidencia archivada. La paridad 3.12/16 del VPS no reconstruye la imagen de `despliegue/`. |
| Nombre y contenido del `.zip` final | El zip no se genera en esta fase. |
| `POST /ventas/` contra la URL pública | Prueba destructiva; no se repitió. Se usa D-03/D-08. |

## 10. Limpieza

Al cerrar la corrida limpia: se detuvo `uvicorn`, se eliminó la carpeta temporal
de la corrida y se borró la base `parcial_c22_clean`. La base `libreria` no se tocó.

En la continuación 5.10 (2026-11-08): se detuvo `uvicorn`, el puerto 8000 quedó
libre, no quedaron procesos del servidor y se restauró el seed canónico en
`libreria` (5 usuarios, 5 roles, 5 libros, 3 clientes, venta 1 con 69000.00).

En la continuación 5.14: se eliminaron los contenedores `c22-app` y `c22-pg`,
la red `c22net` y `/tmp/c22-parity`. El despliegue existente
(`grupo-acgs_libreria-api`) siguió `Up (healthy)` y la URL pública respondió
200 después de la limpieza.

## 11. 5.10 — ejecución real de los `.http`

Runner: `npx --yes httpyac` 6.16.7 sobre copias de compatibilidad en
`<TEMP>\c22-http`, fuera del repositorio. Antes de cada archivo se corrió
`python seed.py` desde `parcial/`; al terminar se sembró de nuevo y se detuvo
`uvicorn`. Los `.http` versionados no se editaron.

| Archivo | Requests HTTP | Resultado |
|---|---:|---|
| `auth.http` | 12 | **12/12**: C-03 200 + cookie HttpOnly, C-03.2/3 401, C-04.1/2 401 con el mismo cuerpo, C-05 401×5, sexto 429 con `Retry-After: 59957`, logout 200 con `Max-Age=0`. |
| `registro.http` | 7 | **7/7**: C-02.1 201, C-02.2/3 409, C-02.4/5/6 422, C-02.7 201. |
| `roles.http` | 28 | **28/28**: C-06.1 401, C-06.2 403, C-06.3 201, C-06.4 200, C-06.5 403, C-06.6 200, C-07 revocación y vencimiento 403, C-07.7/8 422, C-08 409, C-09 403→200. |
| `libros.http` | 25 | **25/25**: C-01.1 422, C-16.1…8, C-13.1…13; sin 500. |
| `ventas.http` | 19 | **19/19**: C-10 201/201/200, C-11 409, C-12 409/409/201+204/409, C-16.1…6 422, C-15 201/200. |

Transformaciones registradas:

1. Las referencias REST Client `{{nombre.response.headers.Set-Cookie}}` y
   `{{nombre.response.body.$.id}}` se reemplazaron por globales de httpyac
   (`{{$global.cookie_nombre}}`, `{{$global.nombre_id}}`) llenadas por un
   bloque de respuesta después del request nombrado. No cambió método, URL,
   cabeceras ni cuerpos.
2. `roles.http` C-06.6 usa en el archivo versionado
   `Cookie: {{login_ana.response.headers.Set-Cookie}}` (corregido el 2026-11-08).
   La copia solo traduce esa referencia a `{{$global.cookie_login_ana}}`; no
   cambia el contenido de la petición.
3. `roles.http` C-07.11 conservó `@vence_en_corto = {{$datetime iso8601 1 m}}`
   y la copia insertó `await sleep(62000)` después de `login_ana_rol`. La
   misma cookie dio 200 antes y 403 después del vencimiento; no hizo falta
   un flujo httpx aparte.
Evidencia cruda: `parcial/test/evidencia/c22-http-{auth,registro,roles,libros,ventas}.txt`;
resumen y transformaciones: `parcial/test/evidencia/c22-http-resumen.md`.
Los JWT de `Set-Cookie` se reemplazaron por `<jwt-redacted>` al guardar.
Controles SQL: `c22-http-sql-controls.txt` (4 ventas, 9 renglones, 15
movimientos; invariante 0 filas) y `c22-http-c14-solo-agregado.txt` (UPDATE y
DELETE rechazados; 15 filas intactas). El aviso de `BackgroundTasks` quedó en
`c22-http-backgroundtasks.txt`.

## 12. 5.11 — recorrido §0–§10 sección por sección

Comandos re-ejecutados el 2026-11-08 sobre `libreria`: greps estáticos,
`alembic history/current/check`, `psql` (catálogo, defaults, tipos, FKs,
invariante), `python -m pytest -q` (472 passed, 1 skipped) y `app.openapi()`.
La salida completa está en `parcial/test/evidencia/c22-checklist-0-10.txt`.
Lo que se reutiliza se indica en la columna de evidencia.

| Sección | Resultado | Evidencia | Nota |
|---|---|---|---|
| §0 Reglas no negociables | **pasa** | `git grep` de `UnitOfWork(` en servicios, `async with` en routers, `password_hash` en schemas, `selectinload` fuera de `repository.py`, `commit()` en repositorios y `create_all`; `create_all` solo aparece en el README. | Sin violaciones; `app/core/errors.py` es un archivo adicional permitido. La numeración `CV-*` quedó alineada por `fix-auditoria-final`. |
| §1 Estructura | **pasa** | Listado de `app/core` (7+`errors.py`), 8 módulos, `health` solo `router.py`, 5 migraciones, `test/` con `.http`+`.sql`, `tests/` solo pytest, `env.example`, `.env` ignorado y no trackeado, `seed.py` ejecutado. | `__pycache__` existe en disco pero no está trackeado. |
| §2 Configuración | **pasa** | `Settings` con 14 campos (los 13 del checklist + `COOKIE_SECURE`), `database_url` `postgresql+asyncpg`, `POSTGRES_PASSWORD`/`JWT_SECRET` requeridos, motor/sessionmaker solo en `lifespan` y `app.state`, `alembic.ini` sin URL. | El fail-fast sin `.env` ya está en §2 de la corrida limpia. `.env` no se versiona. |
| §3 Migraciones | **pasa** | `alembic history`: 5 revisiones; `current` = `5229054e2bcc (head)`; `check` = «No new upgrade operations detected.»; 5 defaults `now()`; 0 FKs sin índice; `uq_asignacion_rol_abierta` y `uq_libro_isbn_vigente`. | El FAIL anterior de defaults congelados quedó corregido por la migración 0005. |
| §4 Modelo de datos | **pasa** | 15 tablas; seed 5 usuarios/5 roles/5 libros/3 clientes/venta 1 69000.00/2 renglones/7 movimientos/evento `SISTEMA`; invariante `stock = SUM(movimiento_stock.cantidad)` → 0 filas; `NUMERIC` y `timestamptz` en las columnas nuevas. | `asignacion_rol` tiene 7 columnas (el «8» del checklist es error de conteo); la unicidad doble de `cliente.usuario_id` es inofensiva. |
| §5 Autenticación | **pasa** | `auth.http` 12/12; cookie HttpOnly/`SameSite=Lax`/`Max-Age=1800`; cuerpo sin token; 401 sin cookie y con Bearer; 429 con `Retry-After`; 72 bytes → 422; logout con `Max-Age=0`; C-09 misma cookie 200; `bcrypt` con `to_thread` + semáforo. | La comparación de tiempos de C-04 y el reinicio del contador no se aislaron hoy; se reutilizan C-18 y la suite. |
| §6 Autorización | **pasa** | `roles_vigentes` en `dependencies.py` y `AsignacionRol` en `usuarios/repository.py`; `/ventas/{venta_id}` solo `get`, sin `requiere_rol`; `openapi` publica `/mis-ventas` y no `/ventas/mis-ventas`; C-07 revocación y vencimiento 403; C-08 409; C-06.6 200. | C-06.6 usa la plantilla versionada de la cookie de Ana; la copia solo traduce la referencia a global (ver §11); respondió 200. |
| §7 Capas y transacciones | **pasa** | 0 `commit()` en repositorios, 0 `UnitOfWork(` en servicios; 3 referencias a `async_sessionmaker[AsyncSession]` solo en `usuarios/service.py` (excepción declarada DD-05 para `intento_acceso`), 7 `unit_of_work.py` de módulo; C-11 409 con invariante en 0. | La atomicidad de las tres filas del registro (C-02.3 → 409) está cubierta por la suite de C-19; no se repitió el `count(*)` en esta corrida. La atribución del actor del movimiento quedó corregida por `fix-auditoria-final`. |
| §8 Ventas, stock y catálogo | **pasa** | `ventas.http` 19/19; `libros.http` 25/25; sin `PATCH /ventas`; campos extra 422; stock insuficiente 409; baja 204 y segundo DELETE 404; re-alta 201 y duplicado vigente 409; venta vieja conserva el título; seed coherente. | El conteo de SELECT de C-15 se reutiliza de `c-15_consultas_2y4.txt`; hoy solo se re-ejecutaron 201/200. |
| §9 Errores y paginación | **pasa** | C-16: envoltorio `{items,total,page,size,pages}`, `size=500` 422, página 4 de 3 422, filtro con `total` correcto, `' OR '1'='1` vacío, PATCH parcial y `stock` 422; sin 500 en C-01/C-02; `extra="forbid"` y `exclude_unset` presentes. | El `ORDER BY` de `ventas_de` quedó corregido por `fix-auditoria-final`. |
| §10 Pruebas | **pasa** | Los cinco `.http` se corrieron hoy (C-01…C-16, salvo C-14 SQL); C-14 con `solo_agregado.sql` (2 errores, 15 filas); log de `BackgroundTasks`; `pytest -q` **472 passed, 1 skipped** local y en VPS 3.12/16; handlers de ruta `async` (los 5 `def` que aparecen son helpers `_to_*`/`_ip_de`). | No se usó la GUI REST Client (se usó httpyac, runner HTTP real). C-15 conteo y C-04 tiempos se reutilizan, declarado en §9 y §11. |

No hay secciones en `falla` ni en `no ejecutado` dentro de §0–§10. El registro
es por sección: no se afirma haber ejecutado literalmente los 136 comandos.

## 13. 5.14 — paridad Python 3.12 / PostgreSQL 16 en el VPS

VPS `srv1930369` (`root@179.199.131.190`), Docker 29.7.1. Se usaron solo
recursos nuevos `c22-*`; no se tocó ningún contenedor `grupo-acgs_*` ni el
despliegue público.

```text
git clone --depth 1 https://github.com/AgustinContardi/Trabajo_Segundo_Parcial_Programacion_3.git /tmp/c22-parity/repo
HEAD 00111072e0a117abf6bd25885420edfc09190f79   # coincide con el HEAD local
tracked_files 453
```

Contenedores: `c22-pg` = `postgres:16-alpine` → **PostgreSQL 16.15**;
`c22-app` = `python:3.12-alpine` → **Python 3.12.16**. Red `c22net`; el
`.env` temporal se creó con contraseña y `JWT_SECRET` aleatorios, `600`, y se
eliminó con la carpeta. `BCRYPT_ROUNDS=4`, `COOKIE_SECURE=false`.

```text
alembic upgrade head -> 0001, 0002, 0003, 0004, 0005 (exit 0)
alembic current      -> 5229054e2bcc (head)
python seed.py       -> 5 usuarios, 5 roles, 3 editoriales, 3 géneros, 6 autores,
                        5 libros, 3 clientes, 1 perfil, venta 1 69000.00, 2 renglones,
                        7 movimientos, 1 evento
python -m pytest -q  -> 472 passed, 1 skipped, 6 warnings in 27.67s
GET /health/live     -> 200 {"status":"ok"}
GET /health/ready    -> 200 {"status":"ok"}
```

Versiones instaladas: `fastapi 0.162.2`, `sqlmodel 0.0.48`, `SQLAlchemy 2.1.8`, `asyncpg 0.32.0`, `bcrypt 5.0.0`.

Nota de configuración: el primer intento puso `COOKIE_SECURE=false` como
variable de entorno del contenedor y la suite dio **471 passed, 1 failed**
(`test_cookie_secure_defaults_to_protected_value`, que afirma el default
protegido cuando no hay variable). Con `COOKIE_SECURE=true` fallaron 97
pruebas porque las cookies `Secure` no viajan por HTTP. La corrida válida
dejó `COOKIE_SECURE=false` en `/app/.env` (igual que el `.env` local), sin
la variable en el entorno del proceso: **472 passed, 1 skipped**. Las dos
corridas fallidas quedan registradas, no ocultas.

Limpieza verificada: `c22-app`/`c22-pg` eliminados, `c22net` eliminada,
`/tmp/c22-parity` eliminado; `grupo-acgs_libreria-api` siguió `Up (healthy)`
y `GET https://libreria.enzogiaquinta.me/health/ready` → **200**.
