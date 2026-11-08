# Despliegue — imagen Docker del TP capítulos 1 a 4

Imagen reproducible de `despliegue/` (el TP de los capítulos 1 a 4, «la
librería») para el criterio «Contenedor: la imagen» (11 % de la rúbrica). Se
empaqueta el TP **tal como se entregó** más los artefactos de despliegue:
`Dockerfile`, `.dockerignore`, `env.example`, `DEPLOY.md` y `evidencia/`.
`parcial/` no usa esta imagen (`DD-15`).

> **Estado de la evidencia.** En C-20 quedan escritos el `Dockerfile`, el
> `.dockerignore`, el `env.example` y este documento. El build, la ejecución y
> la evidencia de **D-01, D-06 y D-07** se producen en el VPS durante **C-21**,
> porque la máquina de desarrollo no tiene Docker instalado. Por eso
> `evidencia/` todavía no existe y los comandos de abajo figuran como
> procedimiento, no como salida ejecutada. C-21 los corre y pega el resultado
> real en `despliegue/evidencia/`.

## Qué queda dentro de la imagen

| Pieza | Por qué está en la imagen |
|---|---|
| `main.py` | entrypoint real (`main:app`); está en la raíz de `despliegue/` |
| `app/` | paquete de la aplicación (`core/` + `modules/`) |
| `migrations/` + `alembic.ini` | `alembic upgrade head` corre en cada arranque |
| `requirements.txt` | se instala con `pip install --no-cache-dir` |
| `seed.py` | lo usa C-21 para cargar los datos iniciales dentro del contenedor |
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

## Contexto de build

Todos los comandos se corren **dentro de `despliegue/`**, igual que el
`README.md` del TP. Construir desde la raíz del repo copiaría `parcial/` y los
`.env` de otras carpetas.

## Construir

```powershell
cd despliegue
docker build -t libreria:local .
```

Para la corrida de aceptación (build desde cero, sin caché):

```powershell
docker build --no-cache -t libreria:local .
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
docker run -d --name libreria `
  -p 8000:8000 `
  --env-file C:\ruta\fuera\del\repo\libreria.env `
  libreria:local
```

- `-p <puerto>:8000`: el servidor escucha en `0.0.0.0:8000` dentro del
  contenedor y la imagen declara `EXPOSE 8000`.
- Si la base corre **en el mismo servidor** que el contenedor, agregar
  `--add-host=host.docker.internal:host-gateway` y usar
  `POSTGRES_HOST=host.docker.internal` en `libreria.env`. Dentro del contenedor,
  `127.0.0.1` es el propio contenedor.

Comprobar el arranque:

```powershell
docker ps                              # NAME libreria, STATUS Up ... (healthy)
docker logs libreria                   # alembic upgrade head y luego uvicorn
docker exec libreria id                # usuario `app`, uid != 0
docker exec libreria wget -qO- http://127.0.0.1:8000/health/ready
```

El `HEALTHCHECK` tiene `--start-period=30s` porque el `CMD` aplica las
migraciones antes de levantar uvicorn: con `--no-cache` y una base remota, el
primer `healthy` puede tardar.

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

## Evidencia: qué cubre C-20 y qué queda para C-21

| Caso | Qué demuestra | Cuándo |
|---|---|---|
| **D-01** | `docker images`: base Alpine < 100 MB y la imagen del proyecto | C-21 (VPS) |
| **D-02** | Servidor limpio: build, run y contenedor `healthy` con migraciones aplicadas | C-21 (VPS) |
| **D-03** | Desde afuera, en la URL pública: `/health/ready`, `/libros/`, `POST /ventas/` | C-21 (VPS) |
| **D-04** | Persistencia y reinicio: `docker rm -f` + `docker run`, los datos siguen | C-21 (VPS) |
| **D-05** | Sin las variables `POSTGRES_*` obligatorias el contenedor **no queda sirviendo** | C-21 (VPS) |
| **D-06** | `ls -a /app` sin `.env` y `env` sin contraseñas ni cadenas de conexión | C-21 (VPS) |
| **D-07** | `docker exec libreria id`: usuario distinto de root | C-21 (VPS) |
| **D-08** | Aviso del comprobante en `docker logs` después de la respuesta | C-21 (VPS) |

C-20 deja el `Dockerfile` y el `.dockerignore` que hacen posibles D-01, D-06 y
D-07 —base Alpine, `.env`/`.venv`/`.git`/`__pycache__` excluidos, usuario `app`
sin privilegios— y la documentación de las correcciones. **D-01, D-06 y D-07 no
están demostrados todavía**: sin Docker no hay salida real y, según la
consigna, un caso D sin evidencia no suma. La URL pública, la fecha/hora y
D-02…D-05 y D-08 son de C-21.

## Actualización y rollback

La base vive **fuera** del contenedor: reemplazar la imagen no toca los datos y
`alembic upgrade head` vuelve a correr en cada arranque (en una base ya migrada
no aplica nada, porque la versión está en `alembic_version`).

```powershell
# 1) conservar la imagen que está corriendo
docker tag libreria:local libreria:prev

# 2) construir la nueva
cd despliegue
docker build -t libreria:local .

# 3) reemplazar el contenedor
docker rm -f libreria
docker run -d --name libreria -p 8000:8000 --env-file <archivo> libreria:local
```

Rollback: repetir el paso 3 con `libreria:prev`. Nunca `--no-cache` en caliente
sobre el único tag sin haber guardado `libreria:prev`.

Datos iniciales (C-21): una vez que el contenedor está `healthy`, cargar
`seed.py` dentro de él (`docker exec libreria python seed.py`), no en el build.

## Problemas frecuentes

| Síntoma | Causa | Arreglo |
|---|---|---|
| Contenedor `unhealthy` aunque `wget` responde desde el host | El `HEALTHCHECK` usa `localhost`: `wget` lo resuelve a `::1` y uvicorn escucha IPv4 | Usar `127.0.0.1` literal (ya está en el `Dockerfile`) |
| `Connection refused` a la base con `POSTGRES_HOST=127.0.0.1` | Dentro del contenedor, `127.0.0.1` es el contenedor | Poner la dirección del servidor, o `host.docker.internal` + `--add-host` |
| El contenedor muere al arrancar y el error habla de campos faltantes | El archivo de variables define sólo una cadena de conexión | Usar las siete variables de `env.example` (`POSTGRES_*`) |
| `ModuleNotFoundError: No module named 'app.main'` | Se usó el entrypoint de `parcial/` | `uvicorn main:app` |
| Aparece un `.env` dentro de `/app` | Faltaba `.env` en `.dockerignore` | Ya está excluido; reconstruir con `--no-cache` |
| `docker build` desde la raíz del repo | Contexto equivocado: copia `parcial/` | Construir dentro de `despliegue/` |
