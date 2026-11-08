# Design

## Context

Ver `proposal.md` — Why. El estado que condiciona el diseño:

- `despliegue/` es una copia **intacta** del TP cap. 1-4: `main.py` está en la **raíz** del proyecto, no en `app/main.py`; el paquete `app/` contiene `core/` y `modules/`.
- `app/core/config.py` define `Settings` (pydantic-settings) con `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` y `POSTGRES_PORT` **obligatorios y sin default**; `POOL_SIZE=5` y `SQL_ECHO=false` son opcionales. La URL se **deriva** con `sqlalchemy.engine.URL.create(drivername="postgresql+asyncpg", …)`; **no existe** una variable `DATABASE_URL`.
- `app/modules/health/router.py` expone `GET /health/live` (sin base) y `GET /health/ready` (`SELECT 1`, 503 genérico si falla). IN-05 queda cerrada: la ruta que pide la imagen ya existe.
- `alembic.ini` tiene `script_location = migrations` y `prepend_sys_path = .`; `migrations/env.py` importa `app.core.config` y construye la URL desde `Settings`. Por lo tanto `alembic upgrade head` funciona con `WORKDIR /app`.
- `seed.py` vive en la raíz y lo usa C-21 para cargar datos iniciales dentro del contenedor: **no** puede quedar fuera de la imagen.
- No existen `Dockerfile` ni `.dockerignore`. `env.example` ya lista las variables del TP, pero sin explicar la URL derivada.
- Host de desarrollo: Windows + Docker Desktop; el build context es `despliegue/`, no la raíz del repo.

## Goals / Non-Goals

**Goals:**

- Una imagen reproducible en un servidor limpio que arranque el TP, aplique migraciones, corra sin root, no contenga secretos y quede `healthy`.
- Que cada requisito de `specs/imagen-contenedor/spec.md` tenga un comando de verificación ejecutable.
- Que las divergencias entre la documentación del roadmap/KB y el código real del TP queden explícitas y anotadas donde la corrección las busca (`DEPLOY.md`).

**Non-Goals:**

- Desplegar en el VPS, publicar URL, cargar datos iniciales y producir D-02…D-05 y D-08 (C-21).
- Cambiar cualquier archivo de lógica del TP (`main.py`, `app/`, `migrations/`, `alembic.ini`, `requirements.txt`, `seed.py`, `test/`).
- Docker Compose, CI, multi-stage build, imágenes propias de base o Postgres en el contenedor.
- Reutilizar esta imagen para `parcial/` (DD-15).

## Decisions

### D1 — Entrypoint `main:app`, no `app.main:app`

**Decisión**: `CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]`.

**Por qué**: el TP expone `despliegue/main.py`; `despliegue/app/` es un paquete sin `main.py`. `uvicorn app.main:app` fallaría con `ModuleNotFoundError` y el contenedor no quedaría sirviendo.

**Alternativas**: mover `main.py` a `app/main.py` y ajustar imports — rechazada: modifica la lógica/estructura del TP y rompe «tal como se entregó» (DD-15); un `sh -c "cd app && uvicorn main:app"` — rechazada: mueve el cwd y rompe `alembic.ini`, `migrations` y la resolución de `app.*`.

**Nota obligatoria**: la corrección se registra en `DEPLOY.md` §Cambios al TP, porque el texto del roadmap copiaba el entrypoint de `parcial/`.

### D2 — El contrato de configuración es `POSTGRES_*`, con la URL derivada documentada

**Decisión**: `env.example` y el `--env-file` del servidor usan `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POOL_SIZE`, `SQL_ECHO`; el comentario del archivo documenta que la URL resultante tiene la forma `postgresql+asyncpg://<usuario>:<clave>@<host>:<puerto>/<base>`.

**Por qué**: es el contrato que el código lee. El `Settings` tiene `extra="ignore"`, así que un `DATABASE_URL` en el entorno **se ignora en silencio** y, al faltar `POSTGRES_USER`/`POSTGRES_PASSWORD`, la app muere al construir `Settings` en el `lifespan`/`migrations/env.py`. Seguir literalmente la KB (sólo `DATABASE_URL`) produciría un contenedor muerto por una causa que el mensaje de error no atribuye a `DATABASE_URL`.

**Alternativas**: agregar un campo `DATABASE_URL` al `Settings` — rechazada (modifica código del TP); dejar `env.example` con `DATABASE_URL` y usarlo igual — rechazada (no arranca); documentar ambas formas — aceptable sólo como comentario, pero una variable inexistente invita al error, así que se documenta **sólo** la forma derivada.

**D-05 se conserva**: ninguna de las cinco variables obligatorias tiene default, de modo que sin configuración el contenedor termina con error. Lo que cambia respecto del texto del roadmap es el **nombre** de las variables, no el comportamiento.

### D3 — `HEALTHCHECK` con `127.0.0.1`, `wget`, y `start-period` de 30 s

**Decisión**:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1
```

**Por qué**: en Alpine no hay `curl`; `wget` resuelve `localhost` primero a `::1`, mientras uvicorn con `--host 0.0.0.0` escucha IPv4: con `localhost` el contenedor queda `unhealthy` aunque responda desde afuera. El `start-period` de 30 s cubre el `alembic upgrade head` inicial y la primera conexión a la base; con 10 s (valor del borrador de la KB) una base remota lenta puede marcar `unhealthy` antes de que uvicorn exista. `--start-period` sólo posterga el juicio de salud, no ejecuta nada.

**Alternativas**: `curl` — no está en Alpine; `wget` con `localhost` — la trampa de la consigna; `start-period=10s` — insuficiente para migraciones en frío.

**Consecuencia asumida**: si la base cae, el contenedor queda `unhealthy` pero **no** se reinicia (Docker no reinicia por health). La sonda distingue vivo de listo, no repara.

### D4 — Orden de capas y usuario sin privilegios siguiendo la plantilla de la KB

**Decisión**:

```dockerfile
FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN addgroup -S app && adduser -S -G app app && chown -R app:app /app
USER app
EXPOSE 8000
```

**Por qué**: la capa de dependencias se cachea mientras no cambie `requirements.txt`; `--no-cache-dir` no deja ruedas en la imagen; el `chown` posterior al `COPY` es necesario porque los archivos copiados pertenecen a `root` y el usuario `app` no podría escribir lo que necesite. `PYTHONDONTWRITEBYTECODE=1` evita que el proceso sin privilegios intente escribir `__pycache__` en `/app`.

**Alternativas**: `COPY --chown=app:app . .` — requiere crear el usuario antes del `COPY`, invierte el orden legible de la plantilla y no aporta; `USER` antes de `pip install` — impediría instalar en el site-packages del sistema.

**Nota**: las dependencias del stack (`asyncpg`, `pydantic-core`, etc.) se instalan en musl sin compilar; si el build pidiera un compilador, se trataría como cambio de alcance, no se agrega `build-base` en silencio.

### D5 — `.dockerignore` con el mínimo obligatorio y higiene, conservando lo que la app necesita

**Decisión**:

```
.env
.venv/
.git/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
test/
tests/
*.md
!README.md
```

**Por qué**: `.env`, `.venv`, `.git` y `__pycache__` son el mínimo de la consigna; excluir tests y cachés reduce contexto y capas. **No** se excluyen `requirements.txt`, `alembic.ini`, `migrations/`, `app/`, `main.py`, `seed.py` ni `env.example`: los primeros son necesarios para instalar y migrar, y `seed.py` lo necesita C-21 dentro del contenedor.

**Alternativas**: excluir `env.example` — innecesario: no tiene secretos y documenta el contrato dentro de la imagen; excluir `seed.py` — rompería la carga de datos iniciales del despliegue.

### D6 — `env.example` con la forma, nunca valores

**Decisión**: mantener el archivo existente con los nombres reales, valores de ejemplo evidentemente falsos (`cambiar_por_la_contrasena_local`) y un comentario que explique la URL derivada y el driver. No se agrega `DATABASE_URL`.

**Por qué**: cumple «la forma de `DATABASE_URL` (driver `postgresql+asyncpg`)» sin declarar una variable que la app no lee; cualquier valor real queda fuera del repo y del zip.

### D7 — `DEPLOY.md` nace en C-20, se completa en C-21

**Decisión**: C-20 crea el documento con: base usada, comandos de build/run completos, nombre del archivo de variables (sin contenido), sección **Cambios al TP** (D1 y D2) y una nota de que URL pública, fecha/hora y evidencia D-02…D-08 corresponden a C-21.

**Por qué**: el scope de C-20 exige «corregir y anotar en `DEPLOY.md`», y D-06/D-07 se demuestran sobre la imagen; esperar a C-21 dejaría la corrección sin registro y el change sin su nota. Crear el esqueleto evita reescribir el archivo después y no invade el alcance de C-21.

**Alternativa**: anotar las correcciones en un comentario del `Dockerfile` — rechazada: la corrección se busca en `DEPLOY.md`.

### D8 — Evidencia como texto reproducible, no captura

**Decisión**: `despliegue/evidencia/D-01.md`, `D-06.md`, `D-07.md` con el comando exacto y la salida pegada; las capturas de pantalla son opcionales.

**Por qué**: el texto se revisa y se repite; la consigna acepta texto de consola. Se generan con el contenedor `libreria` corriendo (`D-07`) y con `docker run --rm` para `D-01`/`D-06`.

**Nota**: `docker images` muestra el tamaño de la base y de la imagen final; D-01 exige que **la base** esté por debajo de 100 MB y que el `Dockerfile` parta de ella.

## Risks / Trade-offs

- **`localhost` en el `HEALTHCHECK`** → el contenedor queda `unhealthy` sin error visible. Mitigación: `127.0.0.1` literal, verificación con `docker exec libreria wget -qO- http://127.0.0.1:8000/health/live` y revisión del `Dockerfile` como ítem de aceptación.
- **`DATABASE_URL` en el archivo de variables** → la app no arranca por falta de `POSTGRES_*`. Mitigación: `env.example` documenta el contrato real, `DEPLOY.md` lo repite y D-05 se prueba sin variables.
- **`.env` local se cuela en la imagen** → secreto horneado para siempre. Mitigación: `.dockerignore` + D-06 (`ls -a /app`) y `env`; el `.env` además está en `.gitignore`.
- **Base lenta en el primer arranque** → `unhealthy` transitorio. Mitigación: `start-period=30s`; si la base no responde, el `CMD` falla y el contenedor muere (comportamiento deseado).
- **Alpine/musl sin ruedas** → build roto. Mitigación: build `--no-cache` desde cero en la aceptación; no se agrega compilador sin justificar.
- **Contexto de build equivocado** (`docker build .` desde la raíz) → se copia `parcial/` y el `.env` de otra carpeta. Mitigación: todos los comandos se ejecutan **dentro de `despliegue/`**, como ya hace su README.
- **`DEPLOY.md` incompleto** → C-21 lo completa; se marca explícitamente qué falta para no confundirlo con un despliegue terminado.

## Migration Plan

No hay migración de datos. El «rollback» es de imagen: conservar el tag anterior (`libreria:prev`) y volver a correrlo. Actualización futura: `docker build` → `docker rm -f` → `docker run`; la base vive fuera del contenedor. C-20 no publica en el VPS.

## UI Mockups

- Design system revision: no aplica (no hay `design-system/`).
- Decision: no (no UI) — 2026-11-08. El change sólo agrega artefactos de imagen, configuración y documentación; la API ya existe y no cambia ninguna pantalla, componente ni interacción.
- Approval: no aplica.
- Preview: no aplica.
- Visual verify: no aplica.

## Open Questions

- **Sincronización de la KB**: `11_despliegue_y_devops.md` y el texto de `CHANGES.md` hablan de `DATABASE_URL` como variable sin default, mientras el código deriva la URL desde `POSTGRES_*`. C-20 resuelve el artefacto (usa el contrato real y lo anota), pero la KB queda desalineada; corregirla es un change de documentación posterior, no parte de C-20.
- **Puerto público y base de la cátedra**: los define C-21; no cambian el `Dockerfile` (`EXPOSE 8000`, publicación `-p <puerto>:8000`).
