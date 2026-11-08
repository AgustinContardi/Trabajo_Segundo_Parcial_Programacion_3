# Proposal

## Why

El 11 % de la rúbrica se corrige sobre la imagen, y `despliegue/` —la copia intacta del TP de los capítulos 1 a 4— todavía no tiene `Dockerfile` ni `.dockerignore`. Sin una imagen reproducible desde `python:3.12-alpine`, sin root, sin secretos, con migraciones al arrancar y con un `HEALTHCHECK` que consulta `127.0.0.1` (nunca `localhost`), el criterio «Contenedor: la imagen» queda sin material y los casos D-01, D-06 y D-07 no se pueden demostrar.

## What Changes

- **Nuevo** `despliegue/Dockerfile` sobre `python:3.12-alpine`: dependencias (`requirements.txt` con `pip install --no-cache-dir`) antes de copiar el código, usuario sin privilegios (`addgroup`/`adduser` + `USER`), `EXPOSE 8000`, `CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]` y `HEALTHCHECK` con `wget -qO- http://127.0.0.1:8000/health/ready || exit 1`.
  - **Corrección al texto del roadmap**: el entrypoint del TP es `despliegue/main.py`, no `app/main.py`; `uvicorn app.main:app` terminaría en `ModuleNotFoundError`. Se usa `uvicorn main:app` y se anota en `DEPLOY.md`.
- **Nuevo** `despliegue/.dockerignore`: `.env`, `.venv/`, `.git/`, `__pycache__/`, `*.pyc`, cachés de test/lint, documentación y `test/`/`tests/`; se conservan `requirements.txt`, `alembic.ini`, `migrations/`, `app/`, `main.py`, `seed.py` y `env.example`.
- **Ajuste** de `despliegue/env.example` a la **forma real** del contrato del TP: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POOL_SIZE`, `SQL_ECHO`, sin valores reales y con la forma de la URL derivada `postgresql+asyncpg://…` documentada como comentario.
  - **Corrección al texto del roadmap / KB 11**: el `Settings` del TP no lee `DATABASE_URL`; deriva la URL desde `POSTGRES_*` con `URL.create`. Un `--env-file` con sólo `DATABASE_URL` dejaría el contenedor muerto por falta de `POSTGRES_USER`/`POSTGRES_PASSWORD`. D-05 se mantiene porque ninguna de esas variables tiene default.
- **Nuevo** `despliegue/DEPLOY.md` (borrador de la parte de imagen): base, comandos de build/run, nombre del archivo de variables y sección **«Cambios al TP»** con las dos correcciones anteriores y la verificación de la ruta de salud (`/health/ready` existe, IN-05 no requiere cambios). C-21 completa URL pública, fecha/hora y despliegue en el VPS.
- **Nuevo** `despliegue/evidencia/` con D-01, D-06 y D-07 (comando + salida real): `docker images` con la base por debajo de 100 MB, `ls -a /app` sin `.env` y `env` sin credenciales, `docker exec libreria id` sin root.
- **Verificación**: build desde cero con `--no-cache` una vez; el contenedor debe quedar `healthy` con una base accesible y morir con error si la base no responde.

**No cambia**: ninguna línea de código del TP (`main.py`, `app/`, `migrations/`, `alembic.ini`, `requirements.txt`, `seed.py`, `test/`), ni `parcial/`, ni el health router.

## Capabilities

### New Capabilities

- `imagen-contenedor`: comportamiento exigible a la imagen del TP cap. 1-4 —base Alpine, capas dependencias-antes-que-código, usuario sin privilegios, ausencia de secretos en la imagen y en el build context, migraciones al arrancar como condición de vida, escucha en `0.0.0.0` y `HEALTHCHECK` sobre `/health/ready` vía `127.0.0.1`— junto con la documentación y la evidencia de D-01, D-06 y D-07.

### Modified Capabilities

- Ninguna. `legacy-baseline` ya exige que `despliegue/` sea una copia intacta del TP y que sólo se le agreguen artefactos de despliegue; agregar `Dockerfile`, `.dockerignore`, `DEPLOY.md` y `evidencia/` no cambia ese requisito.

## Impact

- **Archivos nuevos**: `despliegue/Dockerfile`, `despliegue/.dockerignore`, `despliegue/DEPLOY.md`, `despliegue/evidencia/D-01.md`, `D-06.md`, `D-07.md`.
- **Archivo ajustado**: `despliegue/env.example` (sólo comentarios/forma; sigue sin secretos).
- **Sin impacto en código**: no se toca `despliegue/app/`, `despliegue/main.py`, `despliegue/migrations/` ni `parcial/`.
- **Dependencias externas**: Docker (build y run) y una PostgreSQL 16 alcanzable para que el contenedor quede `healthy`; sin Docker no hay evidencia ejecutable y el change no se puede aceptar.
- **Habilita**: C-21 (VPS, `DEPLOY.md` completo y D-01…D-08).
