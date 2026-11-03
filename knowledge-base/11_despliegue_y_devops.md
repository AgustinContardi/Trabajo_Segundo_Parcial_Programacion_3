# Despliegue y DevOps

> **18 % de la nota**: 11 % «Contenedor: la imagen» + 7 % «Despliegue en el VPS». Es el bloque más
> caro después de Repositorios y Unit of Work, y el único que se corrige **sobre un sistema en línea**,
> no sobre el código.

## Regla de oro: son dos proyectos distintos

| Carpeta del `.zip` | Qué contiene | Qué **no** contiene |
|---|---|---|
| `parcial/` | El proyecto ampliado: capítulos 5 y 6 completos, **sin** el despliegue | Nada de Docker; ninguna carpeta de despliegue |
| `despliegue/` | El TP de los capítulos 1 a 4 **tal como se entregó**, + `Dockerfile` + `.dockerignore` + `env.example` + `DEPLOY.md` + `evidencia/` | **Ninguna** de las modificaciones del parcial (ni roles, ni `movimiento_stock`, ni UoW) |

«Se empaqueta el TP de los capítulos 1 a 4, tal como se entregó —la librería con su catálogo, sus
clientes y sus ventas, **sin los cambios de este parcial**—. Se le agregan al TP sólo el `Dockerfile` y
el `.dockerignore`, y su lógica no se toca» (Ejercicio 9).

**Consecuencia práctica**: el `Dockerfile` de `despliegue/` **no** se reutiliza en `parcial/`. Si el
código nuevo se copia a la imagen del despliegue, se rompe la consigna y probablemente D-02, porque las
migraciones y las rutas no son las mismas.

**Excepción prevista**: «Si el TP no arranca en el contenedor por un defecto propio (por ejemplo, una
ruta de salud que no responde como pedía su consigna), se corrige y se anota en `DEPLOY.md`».

## La imagen (11 %)

### Requisitos que mira la corrección

| Requisito | Detalle y por qué |
|---|---|
| Base `python:3.12-alpine` | Medida con Docker 29.2 el 2/11/2026: **74,7 MB** en disco. `python:3.12-slim` ocupa **180 MB** y **no cumple**. Cada MB se paga en disco y en tiempo de descarga en cada despliegue, y cada paquete del sistema es superficie de ataque |
| Dependencias antes que el código | Copiar e instalar `requirements.txt` con `--no-cache-dir` **antes** de copiar el código: mientras las dependencias no cambien, esa capa sale de la caché y un cambio de código no reinstala todo |
| Sin root | Se crea un usuario sin privilegios y se lo activa con `USER`. Si vulneran la aplicación, no son dueños del contenedor |
| Sin secretos | `.dockerignore` excluye `.env`, `.venv`, `.git` y `__pycache__`. Ni la dirección de la base ni su contraseña aparecen en el `Dockerfile`. **Lo que se hornea en una capa queda ahí para siempre, aunque una capa posterior lo borre** |
| Migraciones al arrancar | `alembic upgrade head` y después uvicorn. Si la base no responde, Alembic falla y el contenedor **termina con error**: una aplicación que no llega a su base no debería quedar atendiendo |
| `0.0.0.0` | Dentro de un contenedor, `127.0.0.1` sólo se alcanza desde el propio contenedor y el puerto publicado nunca respondería |
| `HEALTHCHECK` | Sobre `GET /health/ready`. Sin Compose, es la propia imagen la que dice cuándo está sana y `docker ps` lo muestra |

**Alpine y musl**: Alpine usa musl en lugar de glibc, y eso suele romper paquetes que se compilan al
instalarse. Se verificó que las dependencias del stack del TP (`asyncpg`, `pydantic-core` y el resto
del `requirements.txt`) se instalan **sin compilar nada**, así que **no hace falta instalar ningún
compilador** (ni `build-base`, ni `gcc`). Si se agregara un paquete con ruedas sólo para glibc, la
imagen crecería y habría que justificarlo.

### `Dockerfile` de referencia

> Borrador derivado de la consigna. El grupo debe ajustarlo al **nombre real de la app y del archivo de
> migraciones del TP cap 1-4** y verificar el `HEALTHCHECK` contra la ruta que ese TP expone.

```dockerfile
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) dependencias primero: la capa se cachea mientras no cambie requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) código después: un cambio de código no reinstala dependencias
COPY . .

# 3) usuario sin privilegios
RUN addgroup -S app && adduser -S -G app app && chown -R app:app /app
USER app

EXPOSE 8000

# 4) migraciones y arranque. Si la base no responde, esto falla y el contenedor muere.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# 5) salud: se consulta la app DENTRO del contenedor.
#    wget viene en Alpine; curl NO.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1
```

Notas de por qué cada línea:

- `CMD` en forma `sh -c` para poder encadenar `alembic` y `uvicorn`; si se prefiere `ENTRYPOINT`, el
  efecto es el mismo.
- `--no-cache-dir` evita dejar las ruedas descargadas dentro de la imagen.
- `chown` después de copiar: si se copia como root y no se ajusta el dueño, el usuario `app` no puede
  escribir lo que necesite.

### `.dockerignore`

```
.env
.venv/
__pycache__/
*.pyc
.git/
.gitignore
.pytest_cache/
.ruff_cache/
tests/
test/
*.md
!README.md
```

Mínimo exigido por la consigna: **`.env`, `.venv`, `.git` y `__pycache__`**. Todo lo demás es higiene
(menos contexto de build, menos capas, menos filtración).

### Las dos trampas que la consigna marca en mayúscula

**1. LA BASE NO ESTÁ EN LOCALHOST.**

Dentro de un contenedor, `localhost` es el propio contenedor, no el servidor. Una `DATABASE_URL` con
`localhost` falla con «Connection refused» **aunque PostgreSQL esté funcionando**. Si la base corre
directamente en el servidor:

```bash
docker run ... --add-host=host.docker.internal:host-gateway ... libreria
```

y en el `--env-file`:

```
DATABASE_URL=postgresql+asyncpg://usuario:clave@host.docker.internal:5432/base
```

En Linux, `host.docker.internal` hay que habilitarlo con `--add-host=host.docker.internal:host-gateway`.
Si la cátedra entrega otra dirección, se usa esa.

**2. EL HEALTHCHECK Y LOCALHOST.**

Dentro de una imagen Alpine **no hay `curl`**; `wget`, que sí viene, resuelve `localhost` primero a
**`::1` (IPv6)**, y uvicorn con `--host 0.0.0.0` escucha **sólo IPv4**. Un `HEALTHCHECK` con
`http://localhost:8000/...` falla con «Connection refused» aunque el servidor responda perfectamente
desde afuera, y el contenedor queda `unhealthy` sin que nada parezca roto.

- **La dirección que sirve es `127.0.0.1`.**
- Comprobación manual: `docker exec libreria wget -qO- http://127.0.0.1:8000/health/live`.

## Cómo se corre

```bash
docker build -t libreria .

docker run -d --name libreria \
  -p <puerto>:8000 \
  --restart unless-stopped \
  --env-file <archivo-de-variables> \
  libreria
```

| Flag | Para qué |
|---|---|
| `-p <puerto>:8000` | Publica **sólo la aplicación**, en el puerto que asigna la cátedra |
| `--restart unless-stopped` | Docker vuelve a levantar el contenedor si termina: por ejemplo si el servidor se reinicia, o si la base todavía no respondía cuando arrancó |
| `--env-file <archivo>` | Entrega la configuración desde un archivo que vive **en el servidor**, fuera del repositorio y de la imagen |
| `--add-host=host.docker.internal:host-gateway` | Sólo si la base corre en el host y el sistema es Linux |

**Contenido del `--env-file`** (nunca versionado):

```
DATABASE_URL=postgresql+asyncpg://<usuario>:<clave>@<host>:5432/<base>
SQL_ECHO=false
```

`SQL_ECHO=false` deja de escribir cada consulta en el registro. **`DATABASE_URL` no tiene default en el
TP**: sin ella, el contenedor no queda sirviendo (D-05).

### Sin Docker Compose

No se usa Compose: **la base de datos no forma parte del paquete**, porque el servidor ya tiene
PostgreSQL. La imagen contiene **una** aplicación; el estado vive fuera.

## Despliegue en el VPS (7 %)

| Paso | Detalle |
|---|---|
| 1. Acceso | Datos de acceso y base **que provee la cátedra** |
| 2. Imagen | Se construye **en el servidor** o se construye en otro lado y se lleva. **El grupo elige y lo documenta** en `DEPLOY.md` |
| 3. Correr | `docker run` con el `--env-file` del servidor |
| 4. Datos iniciales | Una vez arriba, se cargan ejecutando **dentro del contenedor** el comando de datos iniciales que indica el **README del TP**: `docker exec libreria …` |
| 5. Verificar desde afuera | `GET /health/ready`, `GET /libros/`, `POST /ventas/` (D-03) |
| 6. Sostener | El despliegue **sigue en línea hasta que se publiquen las notas**, porque la corrección lo prueba |
| 7. Documentar | `DEPLOY.md` + `evidencia/` |

### `DEPLOY.md` — contenido obligatorio

1. **URL pública** donde se accede al sistema.
2. **Día y hora** del despliegue.
3. **Comandos `docker build` y `docker run` completos**, con el **nombre** del archivo de variables y
   **sin su contenido**.
4. **Cualquier cambio** hecho al TP para que corra en el contenedor (con su motivo).
5. **Cómo se actualiza la aplicación**: se construye la imagen de nuevo, se **elimina** el contenedor y
   se lo **vuelve a correr**. «Los datos no se pierden, porque viven en la base del servidor y no en el
   contenedor».

Plantilla mínima:

````markdown
# Despliegue — TP Librería (capítulos 1 a 4)

- URL pública: http://<host>:<puerto>
- Fecha y hora del despliegue: 2026-11-__ __:__ (UTC-3)
- Imagen base: python:3.12-alpine (<74,7 MB)
- Construcción: en el servidor | en la máquina del grupo y transferida (elegir y justificar)

## Construcción y ejecución
```bash
docker build -t libreria .
docker run -d --name libreria -p 8000:8000 --restart unless-stopped \
  --env-file /home/<usuario>/libreria.env libreria
```

## Archivo de variables
`/home/<usuario>/libreria.env` (no se versiona). Variables: `DATABASE_URL`, `SQL_ECHO`.

## Cambios al TP
- (ninguno | descripción del defecto propio corregido y por qué)

## Actualización
```bash
docker build -t libreria .
docker rm -f libreria
docker run -d --name libreria -p 8000:8000 --restart unless-stopped \
  --env-file /home/<usuario>/libreria.env libreria
```
Los datos sobreviven: están en la base del servidor.

## Evidencia
Ver `evidencia/` (D-01 … D-08).
````

### `evidencia/` — qué se guarda

Un archivo por caso D, con **el comando y la salida** (captura de pantalla o texto de consola). Sin
evidencia, el caso no suma: «los casos D que no se puedan comprobar no suman».

## Casos D — tabla de verificación

| Caso | Qué se demuestra | Comando / acción | Resultado esperado |
|---|---|---|---|
| **D-01** | `docker images` con la imagen base y la del proyecto | `docker images` | `python:3.12-alpine` **por debajo de los 100 MB** y el `Dockerfile` parte de ella |
| **D-02** | Servidor limpio: build y run | `docker build …` · `docker run …` · `docker ps` | Contenedor en estado **`healthy`**; en `docker logs`, las migraciones del TP aplicadas al arrancar |
| **D-03** | Desde **afuera** del VPS, en la URL pública | `GET /health/ready` · `GET /libros/` (con datos iniciales cargados) · `POST /ventas/` con el cuerpo de ejemplo del TP | 200 · 200 con la lista de libros · **201** con los precios copiados de cada libro y el total calculado |
| **D-04** | Persistencia y reinicio | `docker rm -f libreria` y el mismo `docker run` otra vez | Vuelve a `healthy`; **los datos siguen** (la base no vive en el contenedor); **las migraciones no se repiten** |
| **D-05** | Sin `DATABASE_URL` | correr la imagen sin esa variable | El contenedor **no queda sirviendo**: termina con error, porque el TP no trae ninguna dirección por defecto |
| **D-06** | Contenido de la imagen | `docker run --rm --entrypoint ls <imagen> -a /app` · `docker run --rm --entrypoint env <imagen>` | **No hay `.env`**; `env` **no muestra** `DATABASE_URL` ni ninguna contraseña |
| **D-07** | Usuario del proceso | `docker exec libreria id` | **No es root** |
| **D-08** | Aviso en segundo plano | La venta registrada en D-03 | El aviso del comprobante aparece en `docker logs libreria` **después** de la línea de la respuesta |

**Trampa de D-04**: «las migraciones no se repiten» no significa que no se ejecute
`alembic upgrade head` —se ejecuta en cada arranque—, sino que **no hay nada que aplicar**: la versión
ya está en `alembic_version`. Si el `CMD` hiciera `downgrade`/`create_all`, el caso fallaría.

**Trampa de D-05**: si el TP cap 1-4 tuviera una `DATABASE_URL` con default en el código, el contenedor
arrancaría igual y el caso falla. Es una corrección de una línea y va anotada en `DEPLOY.md`.

## El `.zip` de entrega

**Nombre**: `Parcial_Cap1a6_<NombreDelGrupo>.zip` — uno por grupo, lo sube **un solo integrante** al
campus. La fecha límite se publica en el campus.

```
Parcial_Cap1a6_<Grupo>.zip
├── parcial/
│   ├── main.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── env.example            ← sin punto inicial, sin secretos
│   ├── alembic.ini            ← sin credenciales
│   ├── app/ …                 ← core + modules (6 capas)
│   ├── migrations/            ← 4 versiones
│   ├── test/                  ← .http + solo_agregado.sql
│   ├── README.md              ← integrantes + puesta en marcha desde cero
│   └── evidencia/             ← C-15 (consultas) y C-14 (psql)
└── despliegue/
    ├── (el TP cap 1-4 tal como se entregó)
    ├── Dockerfile
    ├── .dockerignore
    ├── env.example            ← la FORMA de DATABASE_URL, sin valores reales
    ├── DEPLOY.md
    └── evidencia/             ← D-01 … D-08
```

**El `.zip` NO lleva**:

- `.venv/` (se reconstruye con `requirements.txt`),
- `__pycache__/` (lo genera Python solo),
- **el archivo `.env`**,
- en **ninguna** de las dos carpetas del proyecto.

**Sobre `.git`**: si se incluye la carpeta, **su historial también se revisa**. Una contraseña que
alguna vez se subió y se borró después **sigue estando en el historial**, y en ese caso se pide además
cambiarla. Recomendación: no incluir `.git`, y si se incluye, correr `git log -p` buscando secretos.

### README de `parcial/` — contenido obligatorio

Nombres y apellidos de los integrantes, y los pasos para levantarlo **en la máquina del grupo desde
cero**:

1. entorno virtual,
2. dependencias,
3. `.env` con **cómo generar la clave de firma**,
4. `alembic upgrade head`,
5. `python seed.py`,
6. arranque del servidor.

## Rúbrica — dónde se gana y dónde se pierde

| Criterio | Peso | Qué se mira |
|---|---|---|
| Contenedor: la imagen | **11 %** | Imagen base `python:3.12-alpine`, capas en orden, usuario sin privilegios, sin secretos, migraciones al arrancar, `HEALTHCHECK`, `docker run` con `--env-file` |
| Despliegue en el VPS | **7 %** | El TP cap 1-4 en línea en la URL declarada, `DEPLOY.md` completo, los casos D con su evidencia |

### Condiciones que anulan la corrección

> «Un proyecto que no levanta, que no crea su esquema con `alembic upgrade head` sobre una base vacía o
> que contiene **credenciales reales** en el repositorio, en la imagen o en el zip **no se corrige hasta
> que se subsane**.»

Si el despliegue no está accesible en el momento de la corrección, el criterio se evalúa **sólo** sobre
`DEPLOY.md` y `evidencia/`, y los casos D que no se puedan comprobar **no suman**.

## Checklist de despliegue (previo a entregar)

- [ ] `docker images` muestra `python:3.12-alpine` < 100 MB y el `Dockerfile` parte de esa imagen.
- [ ] `docker build` funciona **desde cero**, sin caché previa (`--no-cache` una vez para verificar).
- [ ] El contenedor arranca, aplica migraciones y queda **`healthy`**.
- [ ] `docker exec libreria id` → **no root**.
- [ ] `docker run --rm --entrypoint env <imagen>` **no** muestra `DATABASE_URL` ni contraseñas.
- [ ] `docker run --rm --entrypoint ls <imagen> -a /app` **no** muestra `.env`.
- [ ] El `HEALTHCHECK` usa **`127.0.0.1`**, no `localhost`.
- [ ] Sin `DATABASE_URL`, el contenedor **muere** (D-05).
- [ ] `docker rm -f` + `docker run` → datos intactos, migraciones no repetidas (D-04).
- [ ] Desde **afuera**, la URL pública responde `/health/ready`, `/libros/` y `POST /ventas/` (D-03).
- [ ] El aviso del comprobante aparece en `docker logs` después de la respuesta (D-08).
- [ ] `DEPLOY.md` con URL, fecha/hora, comandos completos (con el **nombre** del archivo, sin su
      contenido), cambios al TP y procedimiento de actualización.
- [ ] `evidencia/` con las ocho salidas de D-01…D-08.
- [ ] El despliegue **sigue en línea** hasta que se publiquen las notas.
- [ ] El `.zip` tiene `parcial/` y `despliegue/`, sin `.venv`, `__pycache__` ni `.env`.
- [ ] Ninguna credencial real en el repositorio, en la imagen, en el zip **ni en el historial de git**.
