# Spec Delta

## Purpose

Define el contrato observable de la imagen Docker que empaqueta el TP de los capítulos 1 a 4: con qué base se construye, cómo se ordenan las capas, con qué usuario corre, qué información nunca contiene, cómo arranca contra la base y cómo declara su salud, junto con la documentación y la evidencia que lo demuestran.

## ADDED Requirements

### Requirement: Imagen base Alpine de menos de 100 MB

La imagen del despliegue SHALL construirse desde `python:3.12-alpine`, cuya base SHALL medir menos de 100 MB en disco, y NO SHALL usar `python:3.12-slim` ni ninguna imagen que la reemplace.

#### Scenario: Inspección de la base

- **WHEN** se ejecuta `docker images` después del build
- **THEN** aparece `python:3.12-alpine` por debajo de los 100 MB y el `Dockerfile` parte de esa imagen

#### Scenario: Base distinta

- **WHEN** el `Dockerfile` declara un `FROM` distinto de `python:3.12-alpine`
- **THEN** el requisito se considera incumplido aunque la imagen construya

### Requirement: Dependencias instaladas antes de copiar el código

El `Dockerfile` SHALL copiar sólo `requirements.txt`, instalar con `pip install --no-cache-dir -r requirements.txt` y recién después copiar el resto del código, de modo que un cambio de código no invalide la capa de dependencias.

#### Scenario: Cambio de código sin reinstalar dependencias

- **WHEN** se modifica un archivo de `app/` o `main.py` y se reconstruye sin cambiar `requirements.txt`
- **THEN** el build reutiliza la capa de dependencias y no vuelve a descargar los paquetes

#### Scenario: Instalación sin compilador

- **WHEN** se construye la imagen desde cero sobre Alpine
- **THEN** las dependencias del `requirements.txt` se instalan sin compilar y sin agregar `build-base`, `gcc` ni otro compilador

### Requirement: Proceso sin privilegios

La imagen SHALL crear un usuario sin privilegios, ajustar el dueño del directorio de trabajo y activarlo con `USER`, de forma que el proceso de la aplicación NO SHALL ejecutarse como `root`.

#### Scenario: Identidad dentro del contenedor

- **WHEN** se ejecuta `docker exec <contenedor> id` con el contenedor en marcha
- **THEN** la salida muestra un usuario distinto de `root` (uid 0)

### Requirement: Sin secretos ni `.env` en el contexto de build y en la imagen

El `.dockerignore` SHALL excluir como mínimo `.env`, `.venv/`, `.git/` y `__pycache__/`. La imagen SHALL contener la aplicación y sus dependencias, pero NO SHALL contener archivos `.env` ni variables de entorno con la dirección o la contraseña de la base.

#### Scenario: Listado del contenido de la imagen

- **WHEN** se ejecuta `docker run --rm --entrypoint ls <imagen> -a /app`
- **THEN** la salida NO incluye `.env`, `.venv`, `.git` ni `__pycache__`

#### Scenario: Variables horneadas

- **WHEN** se ejecuta `docker run --rm --entrypoint env <imagen>` sin `--env-file`
- **THEN** la salida NO muestra `POSTGRES_PASSWORD` ni ninguna contraseña o URL de base con credenciales

#### Scenario: Configuración sólo en tiempo de ejecución

- **WHEN** la aplicación necesita la dirección de la base
- **THEN** la recibe del entorno inyectado al correr el contenedor, nunca del `Dockerfile` ni de un archivo copiado

### Requirement: Migraciones al arrancar y arranque fallido sin base

El contenedor SHALL ejecutar `alembic upgrade head` antes de levantar el servidor y, si la base no responde o falta configuración obligatoria, SHALL terminar con error sin quedar atendiendo peticiones.

#### Scenario: Base disponible

- **WHEN** el contenedor arranca con la configuración completa y la base responde
- **THEN** Alembic aplica las migraciones pendientes y después uvicorn queda atendiendo

#### Scenario: Migraciones ya aplicadas

- **WHEN** el contenedor se reinicia sobre una base ya migrada
- **THEN** `alembic upgrade head` no aplica nada nuevo y el servidor arranca igual

#### Scenario: Base inalcanzable

- **WHEN** el contenedor arranca y la base no responde
- **THEN** `alembic upgrade head` falla y el contenedor termina con código de salida distinto de cero

#### Scenario: Configuración obligatoria ausente

- **WHEN** se corre la imagen sin las variables de base que el TP exige y sin valores por defecto en el código
- **THEN** el contenedor no queda sirviendo y termina con error

### Requirement: Escucha en todas las interfaces

El servidor SHALL escuchar en `0.0.0.0:8000` dentro del contenedor y la imagen SHALL declarar `EXPOSE 8000`, para que el puerto publicado sea alcanzable desde fuera del contenedor.

#### Scenario: Acceso desde el host

- **WHEN** se publica el puerto con `-p <puerto>:8000`
- **THEN** una petición desde fuera del contenedor alcanza la API

#### Scenario: Escucha en loopback

- **WHEN** el comando de arranque usa `--host 127.0.0.1`
- **THEN** el requisito se considera incumplido porque el puerto publicado no responde

### Requirement: HEALTHCHECK contra `/health/ready` usando `127.0.0.1`

La imagen SHALL declarar un `HEALTHCHECK` que consulte `GET /health/ready` dentro del contenedor en `http://127.0.0.1:8000/health/ready` y SHALL usar `wget`, disponible en Alpine. El `HEALTHCHECK` NO SHALL usar `localhost`.

#### Scenario: Contenedor sano

- **WHEN** el servidor y la base responden
- **THEN** el `HEALTHCHECK` sale con éxito y `docker ps` muestra el contenedor como `healthy`

#### Scenario: Base caída

- **WHEN** el servidor está vivo pero `/health/ready` responde 503
- **THEN** el `HEALTHCHECK` falla y el contenedor queda `unhealthy` sin reiniciarse

#### Scenario: Uso de `localhost`

- **WHEN** el `HEALTHCHECK` apunta a `http://localhost:8000/...` en Alpine
- **THEN** el requisito se considera incumplido porque `wget` resuelve `::1` y uvicorn escucha IPv4

### Requirement: Contrato de configuración documentado sin valores reales

`despliegue/env.example` SHALL declarar la forma de las variables que la aplicación realmente lee —`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POOL_SIZE` y `SQL_ECHO`— sin valores reales, y SHALL documentar que la URL se deriva con driver `postgresql+asyncpg`.

#### Scenario: Variables del TP

- **WHEN** se compara `env.example` con el `Settings` del TP
- **THEN** aparecen todas las variables obligatorias y las opcionales, y ninguna con un secreto real

#### Scenario: Sólo `DATABASE_URL`

- **WHEN** el archivo de variables de ejecución define `DATABASE_URL` pero omite las variables `POSTGRES_*`
- **THEN** la aplicación no arranca, porque el TP deriva la dirección desde `POSTGRES_*` y no lee `DATABASE_URL`

### Requirement: Punto de entrada correcto del TP

El comando de arranque SHALL apuntar al módulo de aplicación que el TP expone realmente (`main:app`, con `main.py` en la raíz de `despliegue/`) y NO SHALL referenciar un paquete inexistente.

#### Scenario: Arranque del servidor

- **WHEN** el contenedor ejecuta el comando de arranque
- **THEN** uvicorn importa `main:app` y la API responde

#### Scenario: Ruta de módulo inexistente

- **WHEN** el comando apunta a `app.main:app` y no existe `app/main.py`
- **THEN** el arranque falla con error de importación y el contenedor no queda sirviendo

### Requirement: Correcciones al TP registradas en `DEPLOY.md`

Todo cambio necesario para que el TP arranque en el contenedor SHALL registrarse en `despliegue/DEPLOY.md` con su motivo. `DEPLOY.md` SHALL incluir, como mínimo, la base usada, los comandos de build y ejecución, el nombre del archivo de variables y la sección de cambios al TP.

#### Scenario: Cambio sin registro

- **WHEN** se modifica el TP o su configuración para que arranque en el contenedor
- **THEN** `DEPLOY.md` describe el cambio y por qué era necesario

#### Scenario: Sin cambios

- **WHEN** el TP arranca sin modificaciones
- **THEN** `DEPLOY.md` declara explícitamente que no hubo cambios

### Requirement: Evidencia ejecutable de D-01, D-06 y D-07

`despliegue/evidencia/` SHALL contener, para cada uno de D-01, D-06 y D-07, el comando ejecutado y su salida real. Sin evidencia, el caso correspondiente NO SHALL considerarse cumplido.

#### Scenario: D-01

- **WHEN** se revisa la evidencia de D-01
- **THEN** contiene la salida de `docker images` con la base Alpine por debajo de 100 MB

#### Scenario: D-06

- **WHEN** se revisa la evidencia de D-06
- **THEN** contiene la salida de `ls -a /app` sin `.env` y la de `env` sin credenciales

#### Scenario: D-07

- **WHEN** se revisa la evidencia de D-07
- **THEN** contiene la salida de `docker exec <contenedor> id` mostrando un usuario distinto de `root`

#### Scenario: Evidencia faltante

- **WHEN** falta el archivo de evidencia de uno de los tres casos
- **THEN** ese caso no suma y el change no puede darse por aceptado
