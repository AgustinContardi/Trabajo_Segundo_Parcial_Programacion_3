# Despliegue — imagen Docker del TP capítulos 1 a 4

- **URL pública**: <https://libreria.enzogiaquinta.me>
- **Puesto en línea**: **2026-11-08** (UTC-3). La venta 4 quedó registrada a las
  **17:26:19 UTC-3**, lo que confirma el servicio ya operativo; la evidencia
  D-01…D-07 se registró a las 18:46 UTC-3.
- **Verificación de cierre de C-21**: **2026-11-08 19:08 UTC-3**, revisada y
  reconfirmada a las **19:20 UTC-3** (`/health/ready` 200 y `/libros/` 200).
- **Runtime principal**: EasyPanel, proyecto `grupo-acgs`, app `libreria-api`,
  puerto **8000**, con PostgreSQL 16 en el mismo proyecto.

Imagen reproducible de `despliegue/` (el TP de los capítulos 1 a 4, «la
librería») para el criterio «Contenedor: la imagen» (11 %) y «Despliegue en el
VPS» (7 %). Se empaqueta el TP **tal como se entregó** más los artefactos de
despliegue: `Dockerfile`, `.dockerignore`, `env.example`, `DEPLOY.md` y
`evidencia/`. `parcial/` no usa esta imagen (`DD-15`).

> **Estado de la evidencia.** El despliegue real se hizo en el VPS con EasyPanel
> y las salidas están en `despliegue/evidencia/`: **D-01, D-02, D-03, D-04,
> D-05, D-06, D-07 y D-08** tienen comando y salida real, o la excepción
> documentada en el caso de D-08. El build fue el build limpio de EasyPanel desde
> GitHub (build path `despliegue/`, Dockerfile del repo); no se capturó el log
> crudo del builder, pero la imagen resultante quedó `running | healthy` y el
> `Dockerfile` copia `requirements.txt` antes del código.

> **Actualización de la Evaluación Global (2026-11-10).** `main.py` suma
> `CORSMiddleware` (`allow_origins=["*"]`, `allow_credentials=False`) para permitir
> el desarrollo local del frontend desde otro origen. En producción Nginx publica
> front y API bajo el mismo origen y el middleware no interviene. No cambia ningún
> endpoint, esquema ni migración. El resto de este documento sigue vigente.

## Qué queda dentro de la imagen

| Pieza | Por qué está en la imagen |
|---|---|
| `main.py` | entrypoint real (`main:app`); está en la raíz de `despliegue/` |
| `app/` | paquete de la aplicación (`core/` + `modules/`) |
| `migrations/` + `alembic.ini` | `alembic upgrade head` corre en cada arranque |
| `requirements.txt` | se instala con `pip install --no-cache-dir` |
| `seed.py` | carga los datos iniciales dentro del contenedor, nunca durante el build |
| `env.example` | documenta el contrato dentro de la imagen; no tiene secretos |

Fuera de la imagen, por `.dockerignore`: `.env`, `.env.*`, `.venv/`, `.git/`,
`.gitignore`, `__pycache__/`, `*.py[cod]`, cachés de test/lint, `test/`,
`tests/` y `*.md` (salvo `README.md`).

## Imagen base

`python:3.12-alpine`, **por debajo de 100 MB**. Es la base que exige D-01 y la
que fija la consigna; no se usa `-slim` ni ninguna imagen que la reemplace. Las
dependencias del stack (`asyncpg`, `pydantic-core`, el resto del
`requirements.txt`) tienen ruedas para musl: **no hace falta ningún compilador**
y no se agrega `build-base` ni `gcc`.

## Dónde se construye (elección y justificación)

**Producción: EasyPanel, desde GitHub.** EasyPanel construye la imagen en el VPS
a partir del repositorio y del `Dockerfile` versionado, con **build path
`despliegue/`**. La app es `grupo-acgs/libreria-api`; el contenedor tiene un
nombre generado por EasyPanel y se localiza con el filtro `name=libreria-api`:

```sh
CID=$(docker ps --filter name=libreria-api --filter status=running -q | head -n1)
```

Se eligió así porque la imagen queda atada al repositorio (cada push se puede
redesplegar sin copiar archivos a mano), se usa el mismo `Dockerfile` que se
versiona y el health y el reinicio quedan gestionados por EasyPanel. No hay log
crudo del builder: la evidencia es la imagen resultante `running | healthy`, el
`Dockerfile` versionado y `alembic current` en head (D-02).

**Camino equivalente sin Compose.** El mismo `Dockerfile` se puede construir y
correr a mano; es el comando que pide la consigna y permite reproducir el
despliegue en otro host. **No es el runtime actual.**

### Build local reproducible

Todos los comandos se corren **dentro de `despliegue/`**, igual que el
`README.md` del TP. Construir desde la raíz del repo copiaría `parcial/` y los
`.env` de otras carpetas.

```powershell
cd despliegue
docker build -t libreria .
```

Para la corrida de aceptación (build desde cero, sin caché):

```powershell
docker build --no-cache -t libreria .
```

El log debe mostrar primero `requirements.txt` y `pip install`, y recién
después `COPY . .`. Un cambio de código sin cambios en `requirements.txt`
reutiliza la capa de dependencias (`CACHED`).

## Archivo de variables

**Nombre**: `libreria.env`.

**Ubicación**: **fuera del repo** (por ejemplo
`C:\Users\<usuario>\libreria.env` en Windows o `/home/<usuario>/libreria.env`
en el VPS). No se versiona, no se copia a la imagen y no se pasa con `-e` en la
línea de comandos.

En EasyPanel, las mismas variables se cargan en la configuración de entorno de
la app `libreria-api`; `libreria.env` es el archivo equivalente para el camino
`docker run`. En ningún caso se publica su contenido: sólo se documenta el
nombre o la ruta.

**Contenido**: las siete variables de `despliegue/env.example` —
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`,
`POSTGRES_PORT`, `POOL_SIZE`, `SQL_ECHO`— con los valores reales del servidor.
Las cinco `POSTGRES_*` son obligatorias; `POOL_SIZE` y `SQL_ECHO` son
opcionales. La forma de ejemplo está en `env.example`; acá no se repite ningún
valor real.

La aplicación **deriva** la URL de conexión:

```
postgresql+asyncpg://<usuario>:<clave>@<host>:<puerto>/<base>
```

No se declara una cadena de conexión completa (ver «Cambios al TP», punto 2).

## Ejecutar

```powershell
docker run -d --name libreria -p 8000:8000 --restart unless-stopped --env-file C:\ruta\fuera\del\repo\libreria.env libreria
```

En producción **no se corre este comando a mano**: el contenedor lo gestiona
EasyPanel (`libreria-api`, puerto 8000). El bloque anterior es el comando
literal de la consigna, completo y **sin Docker Compose**; sirve como camino
equivalente y reproducible en otro host, no como runtime actual. En C-21 **no se
ejecutó este comando**: la prueba se hizo por equivalencia con el contenedor de
EasyPanel (D-04).

- `--name libreria`: nombre del contenedor para el camino manual. El de EasyPanel
  se llama `libreria-api`.
- `-p <puerto>:8000`: el servidor escucha en `0.0.0.0:8000` dentro del
  contenedor y la imagen declara `EXPOSE 8000`.
- `--restart unless-stopped`: vuelve a levantar si el proceso o el host se
  reinician, salvo que se lo detenga a propósito.
- `--env-file <archivo>`: el nombre/ruta del archivo fuera del repo
  (`libreria.env`); nunca su contenido en la línea de comandos.
- Si la base corre **en el mismo servidor** que el contenedor, agregar
  `--add-host=host.docker.internal:host-gateway` y usar
  `POSTGRES_HOST=host.docker.internal` en `libreria.env`. Dentro del contenedor,
  `127.0.0.1` es el propio contenedor.

Comprobar el arranque en el camino manual:

```powershell
docker ps                              # NAME libreria, STATUS Up ... (healthy)
docker logs libreria                   # alembic upgrade head y luego uvicorn
docker exec libreria id                # usuario `app`, uid != 0
docker exec libreria wget -qO- http://127.0.0.1:8000/health/ready
```

El `HEALTHCHECK` tiene `--start-period=30s` porque el `CMD` aplica las
migraciones antes de levantar uvicorn: con `--no-cache` y una base remota, el
primer `healthy` puede tardar.

En el runtime de EasyPanel, el contenedor se localiza por nombre:

```sh
CID=$(docker ps --filter name=libreria-api --filter status=running -q | head -n1)
docker inspect "$CID" --format '{{.State.Status}} | {{if .State.Health}}{{.State.Health.Status}}{{end}}'
docker exec "$CID" python -m alembic current
curl -s -o /dev/null -w 'health=%{http_code}\n' https://libreria.enzogiaquinta.me/health/ready
```

## Cambios al TP

El TP se conserva **sin reescribir su lógica**: no se modificó ninguna línea de
`main.py`, `app/`, `migrations/`, `alembic.ini`, `requirements.txt` ni
`seed.py`. Lo que cambia respecto del texto del roadmap y de la KB es el
contenido de los artefactos de despliegue, por dos motivos concretos.

### 1. Entrypoint: `main:app`, no `app.main:app`

El TP expone `despliegue/main.py` en la **raíz** del proyecto. `despliegue/app/`
es un paquete (`core/`, `modules/`) **sin** `main.py`. El borrador de la KB
copiaba `uvicorn app.main:app`, tomado de `parcial/`; con ese comando el
contenedor moriría con `ModuleNotFoundError: No module named 'app.main'` antes
de atender la primera petición.

- Comando correcto: `CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]`.
- Se mantiene `WORKDIR /app` (donde se copia el código) para que `alembic.ini`
  (`script_location = migrations`, `prepend_sys_path = .`) y los imports `app.*`
  sigan resolviendo.

### 2. Contrato de variables: `POSTGRES_*`, no una cadena de conexión

`app/core/config.py` define `Settings` (pydantic-settings) con
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` y
`POSTGRES_PORT` **obligatorios y sin default**, más `POOL_SIZE=5` y
`SQL_ECHO=false`. La URL se **deriva** con `URL.create(drivername=
"postgresql+asyncpg", …)`; el código **no lee** una variable de cadena de
conexión completa, y `Settings` tiene `extra="ignore"`, así que una variable de
ese tipo en el entorno se descarta en silencio.

Consecuencia: un `--env-file` que sólo defina una cadena de conexión deja el
contenedor muerto, y el mensaje de error no la nombra —habla de campos
faltantes—, lo que hace difícil encontrar la causa. Por eso `env.example`
declara únicamente las variables `POSTGRES_*` y documenta la URL derivada como
comentario, sin declararla.

**D-05 se conserva**: ninguna de las cinco obligatorias tiene valor por defecto,
de modo que sin configuración el contenedor termina con error. Lo que cambia
respecto del texto del roadmap es el **nombre** de las variables, no el
comportamiento. La prueba de D-05 se hace corriendo la imagen **sin** las
variables `POSTGRES_*`.

### 3. Ruta de salud: no hubo nada que corregir

`IN-05` quedó cerrada al revisar el TP: `GET /health/live` y `GET /health/ready`
ya existen en `app/modules/health/router.py`, y `/health/ready` ejecuta
`SELECT 1` y devuelve 503 con un cuerpo genérico si la base no responde. El
`HEALTHCHECK` consulta esa ruta, así que **no se modificó el health router**.

## Evidencia D-01…D-08

| Caso | Qué demuestra | Evidencia |
|---|---|---|
| **D-01** | `docker images`: base Alpine < 100 MB y la imagen del proyecto | [`evidencia/D-01.md`](evidencia/D-01.md) |
| **D-02** | Contenedor `running` y `healthy` con Alembic en head | [`evidencia/D-02.md`](evidencia/D-02.md) |
| **D-03** | Desde afuera, en la URL pública: `/health/ready`, `/libros/`, `POST /ventas/` | [`evidencia/D-03.md`](evidencia/D-03.md) |
| **D-04** | Persistencia tras reinicio: vuelve `healthy`, datos y `alembic_version` intactos; **equivalencia parcial** (no se corrió el `docker run` literal) | [`evidencia/D-04.md`](evidencia/D-04.md) |
| **D-05** | Sin las variables `POSTGRES_*` obligatorias el contenedor **no queda sirviendo** | [`evidencia/D-05.md`](evidencia/D-05.md) |
| **D-06** | `ls -a /app` sin `.env` y `env` sin contraseñas ni cadenas de conexión | [`evidencia/D-06.md`](evidencia/D-06.md) |
| **D-07** | `docker exec libreria-api id`: usuario distinto de root | [`evidencia/D-07.md`](evidencia/D-07.md) |
| **D-08** | Aviso del comprobante en segundo plano: **excepción documentada**; pertenece a `parcial/` (C-10), no al TP cap. 1–4 | [`evidencia/D-08.md`](evidencia/D-08.md) |

C-20 dejó el `Dockerfile` y el `.dockerignore` que hacen posibles D-01, D-06 y
D-07 —base Alpine, `.env`/`.venv`/`.git`/`__pycache__` excluidos, usuario `app`
sin privilegios— y la documentación de las correcciones. **D-01…D-07 quedaron
demostrados en el VPS** con EasyPanel; la salida real está en
`despliegue/evidencia/`. El build fue el build limpio de EasyPanel desde GitHub
(build path `despliegue/`); no se capturó el log crudo del builder, pero la
imagen resultante quedó healthy y el `Dockerfile` instala `requirements.txt`
antes de copiar el código.

**D-04 no usa el `docker run` literal.** La prueba se hizo reiniciando el
contenedor que gestiona EasyPanel (`docker restart "$CID"`), no con
`docker rm -f` + `docker run` ni con un contenedor one-off. Demuestra la
persistencia y que las migraciones no se repiten; no demuestra el reemplazo
completo del contenedor. La diferencia queda marcada en `D-04.md`.

**D-08 es una excepción documentada.** El TP cap. 1–4 no tiene
`BackgroundTasks` ni emite el aviso del comprobante; agregarlo sería cambiar su
lógica. La captura real del proyecto completo está en
`parcial/evidencia/c-10-backgroundtasks.txt`, donde el aviso aparece **después**
de la respuesta `POST /ventas/` 201. `D-08.md` cita esa captura y explica por
qué no se ejecuta en el contenedor de `despliegue/`.

## Actualización y rollback

La secuencia es **build → reemplazo → verificación**. La base vive **fuera** del
contenedor: reemplazar la imagen no toca los datos y `alembic upgrade head`
vuelve a correr en cada arranque (en una base ya migrada no aplica nada, porque
la versión está en `alembic_version`). Es lo que demuestra D-04.

**Producción: EasyPanel.**

1. **Build**: push al repositorio; EasyPanel reconstruye desde GitHub con build
   path `despliegue/`.
2. **Reemplazo**: restart/recreate de la app `libreria-api` desde EasyPanel (o
   redeploy de la revisión nueva). No se toca la base.
3. **Verificación**: ejecutar los comandos de «Comprobar el arranque» sobre el
   `CID` de `libreria-api`, y desde afuera `GET /health/ready`, `GET /libros/` y
   `POST /ventas/`. La evidencia de referencia es D-04.

**Camino manual equivalente** (sin Compose; no es el runtime actual):

```powershell
# 1) conservar la imagen que está corriendo
docker tag libreria libreria:prev

# 2) construir la nueva
cd despliegue
docker build -t libreria .

# 3) reemplazar el contenedor
docker rm -f libreria
docker run -d --name libreria -p 8000:8000 --restart unless-stopped --env-file <archivo> libreria
```

**Rollback**: en EasyPanel, volver a la revisión anterior; en el camino manual,
repetir el paso 3 con `libreria:prev`. Nunca `--no-cache` en caliente sobre el
único tag sin haber guardado `libreria:prev`.

**Datos iniciales**: en una base **vacía**, una vez que el contenedor está
`healthy`, cargar `seed.py` dentro de él (`docker exec <contenedor> python seed.py`),
nunca durante el build. No repetir el seed sobre la base en línea: duplicaría o
haría fallar los datos que ya existen.

## Problemas frecuentes

| Síntoma | Causa | Arreglo |
|---|---|---|
| Contenedor `unhealthy` aunque `wget` responde desde el host | El `HEALTHCHECK` usa `localhost`: `wget` lo resuelve a `::1` y uvicorn escucha IPv4 | Usar `127.0.0.1` literal (ya está en el `Dockerfile`) |
| `Connection refused` a la base con `POSTGRES_HOST=127.0.0.1` | Dentro del contenedor, `127.0.0.1` es el contenedor | Poner la dirección del servidor, o `host.docker.internal` + `--add-host` |
| El contenedor muere al arrancar y el error habla de campos faltantes | El archivo de variables define sólo una cadena de conexión | Usar las siete variables de `env.example` (`POSTGRES_*`) |
| `ModuleNotFoundError: No module named 'app.main'` | Se usó el entrypoint de `parcial/` | `uvicorn main:app` |
| Aparece un `.env` dentro de `/app` | Faltaba `.env` en `.dockerignore` | Ya está excluido; reconstruir con `--no-cache` |
| `docker build` desde la raíz del repo | Contexto equivocado: copia `parcial/` | Construir dentro de `despliegue/` |
