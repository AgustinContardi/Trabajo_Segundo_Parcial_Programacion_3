# Tasks

> **Estado (2026-11-08)**: 27/27 completas. Los ítems 5.1-5.3 y 6.1-6.3, 6.6 se
> evidenciaron en el VPS con EasyPanel; las salidas reales quedaron en
> `despliegue/evidencia/`. El build fue el build limpio de EasyPanel desde GitHub
> (build path `despliegue/`), no un `docker build` local: no se capturó el log crudo
> del builder, pero la imagen quedó `running | healthy` y el `Dockerfile` instala
> `requirements.txt` antes de copiar el código. C-20 entregó todo lo que
> se puede escribir sin Docker (`Dockerfile`, `.dockerignore`, `env.example`, `DEPLOY.md`).

## 1. Confirmar el contrato real del TP antes de escribir la imagen

- [x] 1.1 Verificar el entrypoint real: `despliegue/main.py` existe, `despliegue/app/main.py` **no** existe y `uvicorn main:app` es el único objetivo válido. Verificación: `Test-Path despliegue\main.py` → `True` y `Test-Path despliegue\app\main.py` → `False`; el comando del `Dockerfile` usa `main:app`.
- [x] 1.2 Verificar el contrato de configuración leyendo `despliegue/app/core/config.py`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` obligatorios y sin default; `POOL_SIZE` y `SQL_ECHO` opcionales; `DATABASE_URL` no se lee. Verificación: `Select-String -Path despliegue\app\core\config.py -Pattern "POSTGRES_|DATABASE_URL|POOL_SIZE|SQL_ECHO"` muestra los cinco obligatorios y ninguna referencia a `DATABASE_URL`.
- [x] 1.3 Verificar las rutas de salud: `GET /health/live` y `GET /health/ready` existen en `despliegue/app/modules/health/router.py`, y `/health/ready` hace `SELECT 1` y devuelve 503 si la base no responde. Verificación: `Select-String -Path despliegue\app\modules\health\router.py -Pattern "@router.get|status_code=503"` muestra ambos endpoints.
- [x] 1.4 Verificar qué debe quedar dentro de la imagen: `main.py`, `app/`, `migrations/`, `alembic.ini`, `requirements.txt`, `seed.py` y `env.example` existen; `seed.py` lo necesita C-21. Verificación: `Get-ChildItem despliegue | Select-Object Name` lista esos siete elementos.

## 2. `.dockerignore` y `env.example`

- [x] 2.1 Crear `despliegue/.dockerignore` con, como mínimo, `.env`, `.venv/`, `.git/` y `__pycache__/`, más la higiene acordada (`*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `test/`, `tests/`, `*.md`, `!README.md`). Verificación: `Get-Content despliegue\.dockerignore` contiene las cuatro entradas obligatorias y ninguna excluye `requirements.txt`, `alembic.ini`, `migrations/`, `app/`, `main.py`, `seed.py` ni `env.example`.
- [x] 2.2 Actualizar `despliegue/env.example` para que declare `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POOL_SIZE` y `SQL_ECHO` con valores falsos evidentes, y documente en un comentario que la URL se deriva con driver `postgresql+asyncpg` y que **no** se declara `DATABASE_URL`. Verificación: el archivo no contiene `DATABASE_URL` ni una contraseña con pinta de real; las siete variables están presentes.
- [x] 2.3 Confirmar que no hay `.env` versionado ni copiable al build: `despliegue/.env` no está en git y está cubierto por `.dockerignore` y `.gitignore`. Verificación: `git check-ignore -v despliegue/.env` y `git ls-files despliegue/.env` (este último vacío).

## 3. Imagen (`despliegue/Dockerfile`)

> Escritura y verificación **estática** completas. Las comprobaciones con `docker build`,
> `docker run` y `docker inspect` se ejecutan en C-21 (VPS), donde sí hay Docker.

- [x] 3.1 Crear el `Dockerfile` con `FROM python:3.12-alpine`, `ENV PYTHONDONTWRITEBYTECODE=1` y `PYTHONUNBUFFERED=1`, `WORKDIR /app`. Verificación: `Select-String -Path despliegue\Dockerfile -Pattern "^FROM python:3.12-alpine$"` devuelve una coincidencia y `docker build` no reclama la base.
- [x] 3.2 Ordenar las capas: `COPY requirements.txt .` y `RUN pip install --no-cache-dir -r requirements.txt` **antes** de `COPY . .`. Verificación: el `Dockerfile` tiene esa secuencia; tras tocar `despliegue/main.py` y reconstruir, el log muestra `CACHED` en la capa de `pip install`.
- [x] 3.3 Crear el usuario sin privilegios y activarlo: `RUN addgroup -S app && adduser -S -G app app && chown -R app:app /app`, `USER app`, `EXPOSE 8000`. Verificación: `docker run --rm --entrypoint id <imagen>` devuelve un uid distinto de 0 y `docker inspect <imagen> --format "{{json .Config.ExposedPorts}}"` incluye `8000/tcp`.
- [x] 3.4 Definir el arranque con migraciones primero: `CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]`. Verificación: el `Dockerfile` contiene esa línea exacta, sin `create_all` ni `downgrade`; al correr con base accesible, `docker logs` muestra las migraciones y luego el arranque de uvicorn.
- [x] 3.5 Definir el `HEALTHCHECK` contra `/health/ready` con `127.0.0.1`: `HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1`. Verificación: `docker inspect <imagen> --format "{{json .Config.Healthcheck}}"` contiene `127.0.0.1` y **no** contiene `localhost`; con base accesible el contenedor llega a `healthy`.
- [x] 3.6 Confirmar que el `Dockerfile` no hornea configuración: no hay `ENV` con `POSTGRES_*`, ni `ARG`, ni `COPY .env`, ni URL de base. Verificación: `Select-String -Path despliegue\Dockerfile -Pattern "POSTGRES_|DATABASE_URL|password|\.env"` no devuelve coincidencias.

## 4. Documentación de las correcciones (`despliegue/DEPLOY.md`)

- [x] 4.1 Crear `despliegue/DEPLOY.md` con: imagen base, comandos `docker build` y `docker run` completos, **nombre** del archivo de variables (sin contenido), y una nota de que URL pública, fecha/hora y evidencia D-02…D-08 los completa C-21. Verificación: el archivo tiene esas secciones y el `docker run` documentado usa `--env-file <nombre>` y `-p <puerto>:8000`.
- [x] 4.2 Registrar la corrección del entrypoint: el TP usa `main:app`, no `app.main:app`, con el motivo (`main.py` está en la raíz y `app/main.py` no existe). Verificación: la sección «Cambios al TP» menciona `main:app` y el error que evitaba `app.main:app`.
- [x] 4.3 Registrar la corrección del contrato de variables: el TP lee `POSTGRES_*` y deriva `postgresql+asyncpg://…`; un `--env-file` con sólo `DATABASE_URL` deja el contenedor muerto, y D-05 se mantiene porque no hay defaults. Verificación: la sección «Cambios al TP» lo explica y el archivo de variables de ejemplo del documento no incluye valores reales.
- [x] 4.4 Dejar constancia de la revisión de la ruta de salud: `/health/ready` existe (IN-05), por lo que no hay defecto que corregir en el health router. Verificación: `DEPLOY.md` lo afirma explícitamente.

## 5. Evidencia D-01, D-06 y D-07

> **Pendiente: se evidencia en el VPS (C-21) porque no hay Docker local.** No se
> escribieron archivos de evidencia vacíos ni con salidas inventadas: la spec
> `imagen-contenedor` exige la **salida real** y un caso D sin evidencia no suma.
> `DEPLOY.md` §«Evidencia: qué cubre C-20 y qué queda para C-21» deja constancia de qué falta.

- [x] 5.1 Generar `despliegue/evidencia/D-01.md` con el comando `docker images` y su salida real, mostrando `python:3.12-alpine` por debajo de 100 MB y la imagen del proyecto. Verificación: el archivo existe, tiene comando y salida, y la base medida es < 100 MB.
  > Evidencia VPS: `python:3.12-alpine e064671ca452 74.8MB`; `easypanel/grupo-acgs/libreria-api:latest 9e0cc33cc883 255MB`.
- [x] 5.2 Generar `despliegue/evidencia/D-06.md` con `docker run --rm --entrypoint ls <imagen> -a /app` y `docker run --rm --entrypoint env <imagen>`. Verificación: la primera salida no lista `.env`, `.venv`, `.git` ni `__pycache__`; la segunda no muestra `POSTGRES_PASSWORD`, `DATABASE_URL` ni contraseñas.
  > Evidencia VPS: `/app` sin `.env`; `env` sin `POSTGRES*`/`DATABASE` (`sin variables de BD en la imagen`).
- [x] 5.3 Generar `despliegue/evidencia/D-07.md` con `docker exec <contenedor> id`. Verificación: la salida muestra un usuario distinto de `root` (uid ≠ 0).
  > Evidencia VPS: `uid=100(app) gid=101(app) groups=101(app)`.
- [x] 5.4 Marcar en `DEPLOY.md` que D-02, D-03, D-04, D-05 y D-08 quedan para C-21 sobre el VPS. Verificación: el documento enumera qué casos cubre C-20 y cuáles C-21.

## 6. Verificación integral de la imagen

- [x] 6.1 Construir desde cero una vez: `docker build --no-cache -t libreria .` dentro de `despliegue/`. Verificación: exit code 0, sin instalar compiladores, y el log muestra primero `requirements.txt` y después el código.
  > Equivalente VPS: build limpio de EasyPanel desde GitHub (build path `despliegue/`, Dockerfile del repo). La imagen quedó `running | healthy`; no se capturó el log crudo del builder, pero el `Dockerfile` instala `requirements.txt` antes de `COPY . .`.
- [x] 6.2 Correr con un archivo de variables **fuera del repo** que sólo defina las siete variables del TP, apuntando a una base alcanzable: `docker run -d --name libreria -p 8000:8000 --env-file <archivo> libreria`. Verificación: `docker ps` muestra `healthy` y `docker logs libreria` muestra `alembic upgrade head` aplicado antes del arranque.
  > Evidencia VPS (EasyPanel): contenedor `running | healthy`; `alembic current` → `5f67a857f685 (head)`; ver `evidencia/D-02.md` y `D-04.md`.
- [x] 6.3 Probar D-05: correr la imagen **sin** las variables obligatorias. Verificación: el contenedor termina con código distinto de 0 y no queda `Up`; `docker ps -a` lo muestra `Exited`.
  > Evidencia VPS: `ValidationError: 5 validation errors for Settings`; `EXIT=1`; ver `evidencia/D-05.md`.
- [x] 6.4 Revisar el `Dockerfile` completo contra la lista de aceptación: base Alpine, dependencias antes del código, `USER` no root, `EXPOSE 8000`, `--host 0.0.0.0`, `HEALTHCHECK` en `127.0.0.1`, sin secretos. Verificación: `Get-Content despliegue\Dockerfile` pasa los siete puntos sin excepciones.
- [x] 6.5 Confirmar que no se tocó el TP ni el parcial: `git status --short` sólo muestra archivos nuevos/ajustados dentro de `despliegue/` (`Dockerfile`, `.dockerignore`, `env.example`, `DEPLOY.md`, `evidencia/`), y `git diff --stat -- despliegue/main.py despliegue/app despliegue/migrations despliegue/alembic.ini despliegue/requirements.txt despliegue/seed.py parcial` queda vacío.
- [x] 6.6 Confirmar que el contenedor funciona con una base vacía: eliminar los datos de prueba, correr la imagen y verificar que las migraciones crean el esquema y `/health/ready` responde 200. Verificación: `docker logs` sin errores de Alembic y `Invoke-RestMethod http://127.0.0.1:8000/health/ready` → 200.
  > Evidencia VPS: el primer deploy de EasyPanel se hizo sobre la base `libreria` vacía; Alembic aplicó 0001/0002, `/health/ready` respondió 200 y recién después se ejecutó `seed.py`. Ver `evidencia/D-02.md` y `D-03.md`.

## Workflow follow-up

- Marcar `[C-20]` como `[x]` en `CHANGES.md` sólo cuando 6.1–6.6 y la evidencia D-01/D-06/D-07 estén completos.
- Archivar el change con `openspec archive` una vez aprobada la revisión.
- C-21 queda desbloqueado; no se publica en el VPS dentro de este change.
- Actualizar la KB (`11_despliegue_y_devops.md`) para reemplazar la mención de `DATABASE_URL` por el contrato `POSTGRES_*` real, en un change de documentación aparte.
