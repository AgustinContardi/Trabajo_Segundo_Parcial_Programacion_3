# app-foundation Specification

## Purpose
Define las condiciones mínimas para que la API arranque, se conecte a PostgreSQL con una sesión por
petición y exponga sondas de salud fiables, sin credenciales embebidas ni creación implícita del esquema.

## Requirements

### Requirement: Configuración completa y fail-fast

La aplicación SHALL leer del entorno las trece variables de configuración
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `JWT_SECRET`,
`ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`,
`LOGIN_VENTANA_SEG`, `POOL_SIZE`, `SQL_ECHO`) y SHALL negarse a arrancar si falta cualquiera de las
obligatorias.

#### Scenario: Arranque sin contraseña de base

- **WHEN** se inicia el proceso sin `POSTGRES_PASSWORD`
- **THEN** la validación de configuración falla y el servidor no queda escuchando peticiones

#### Scenario: Arranque sin secreto de firma

- **WHEN** se inicia el proceso sin `JWT_SECRET`
- **THEN** la validación de configuración falla y el servidor no queda escuchando peticiones

#### Scenario: Arranque con configuración completa

- **WHEN** las trece variables están presentes y son válidas
- **THEN** la aplicación arranca y queda disponible para atender peticiones

### Requirement: URL de base derivada con driver asincrónico

La aplicación SHALL construir la URL de conexión a partir de las variables sueltas, con el driver
`postgresql+asyncpg`, y SHALL exponerla como un valor derivado de sólo lectura.

#### Scenario: URL efectiva

- **WHEN** se consulta la configuración con `POSTGRES_USER=u`, `POSTGRES_PASSWORD=p`, `POSTGRES_HOST=h`,
  `POSTGRES_PORT=5432` y `POSTGRES_DB=d`
- **THEN** la URL resultante es `postgresql+asyncpg://u:p@h:5432/d`

#### Scenario: La URL no se configura a mano

- **WHEN** se revisan las variables de entorno aceptadas
- **THEN** no existe una variable de URL completa que reemplace a las variables sueltas

### Requirement: Recursos creados en el arranque y liberados al apagar

El motor de base de datos y la fábrica de sesiones SHALL crearse durante el arranque de la aplicación,
quedar disponibles para las peticiones y liberarse al apagar. No SHALL crearse al importar el módulo.

#### Scenario: Arranque

- **WHEN** la aplicación termina su arranque
- **THEN** el motor y la fábrica de sesiones están disponibles para atender peticiones

#### Scenario: Apagado

- **WHEN** la aplicación se apaga
- **THEN** el motor libera sus conexiones y no quedan recursos abiertos

#### Scenario: Importar sin arrancar

- **WHEN** se importa el módulo de la aplicación sin ejecutar el ciclo de arranque
- **THEN** no se abre ninguna conexión ni se crea ningún motor

### Requirement: Una sesión por petición

Cada petición SHALL recibir una sesión de base de datos propia, tomada de la fábrica creada en el
arranque, y esa sesión SHALL cerrarse al terminar la petición, incluso si la petición falla.

#### Scenario: Sesiones independientes

- **WHEN** se atienden dos peticiones consecutivas
- **THEN** cada una usa una sesión distinta

#### Scenario: Cierre ante error

- **WHEN** una petición lanza una excepción
- **THEN** su sesión se cierra igual y vuelve al pool

### Requirement: Sesiones sin expiración al confirmar

Las sesiones SHALL conservar los atributos de los objetos ya cargados después de confirmar, para que la
capa de servicios pueda leerlos al construir la respuesta.

#### Scenario: Lectura posterior al commit

- **WHEN** una operación confirma y luego lee un atributo de un objeto cargado en esa misma sesión
- **THEN** el atributo sigue disponible sin emitir una nueva consulta

### Requirement: Tamaño del pool configurable

El motor SHALL usar `POOL_SIZE` como tamaño del pool de conexiones.

#### Scenario: Pool según configuración

- **WHEN** `POOL_SIZE` vale 7
- **THEN** el motor se crea con un pool de 7 conexiones

### Requirement: Hash ficticio calculado una sola vez

La aplicación SHALL calcular un único hash ficticio durante el arranque y SHALL reutilizarlo durante toda
la vida del proceso, para que el login pueda responder en tiempo comparable exista o no el correo.

#### Scenario: Hash disponible tras el arranque

- **WHEN** la aplicación termina su arranque
- **THEN** el hash ficticio está disponible para las peticiones de autenticación

#### Scenario: Sin recálculo por petición

- **WHEN** se atienden varias peticiones que necesitan el hash ficticio
- **THEN** se usa el mismo valor calculado en el arranque y no se vuelve a calcular

### Requirement: Sonda de vida

La aplicación SHALL exponer `GET /health/live`, que responde `200` si el proceso está vivo y no consulta
la base de datos.

#### Scenario: Proceso vivo con base caída

- **WHEN** se llama a `GET /health/live` mientras la base no responde
- **THEN** la respuesta es `200`

### Requirement: Sonda de disponibilidad

La aplicación SHALL exponer `GET /health/ready`, que ejecuta `SELECT 1` y responde `200` sólo si la base
contesta; si no contesta, SHALL responder `503`.

#### Scenario: Base disponible

- **WHEN** se llama a `GET /health/ready` con la base operativa
- **THEN** la respuesta es `200`

#### Scenario: Base caída

- **WHEN** se llama a `GET /health/ready` con la base inaccesible
- **THEN** la respuesta es `503` y el cuerpo no expone detalles internos de la conexión

### Requirement: Configuración de migraciones sin credenciales

La configuración de Alembic SHALL obtener la URL de la base desde la configuración de la aplicación y no
SHALL contener credenciales ni una URL completa en el archivo de configuración versionado.

#### Scenario: Archivo de configuración limpio

- **WHEN** se inspecciona `alembic.ini`
- **THEN** no contiene `sqlalchemy.url` con usuario, contraseña o nombre de base

#### Scenario: Migraciones con la configuración de la aplicación

- **WHEN** se ejecuta un comando de Alembic con un entorno válido
- **THEN** la URL usada es la derivada de las variables de entorno de la aplicación

### Requirement: Secretos fuera del repositorio

El proyecto SHALL incluir un `env.example` sin punto inicial, con todas las variables y sin valores
secretos, y SHALL ignorar el archivo `.env` real en el control de versiones.

#### Scenario: Ejemplo sin secretos

- **WHEN** se revisa `env.example`
- **THEN** contiene todas las variables necesarias y ningún valor de contraseña o clave real

#### Scenario: `.env` no versionado

- **WHEN** existe un `.env` local
- **THEN** el control de versiones lo ignora y no aparece entre los archivos del proyecto

### Requirement: El esquema no se crea desde la aplicación

La aplicación no SHALL crear ni modificar tablas al arrancar. El esquema SHALL existir únicamente por
migraciones aplicadas.

#### Scenario: Arranque contra base vacía

- **WHEN** la aplicación arranca contra una base sin tablas
- **THEN** no crea ninguna tabla y falla sólo si una ruta que requiere datos se ejecuta

#### Scenario: Sin creación implícita

- **WHEN** se busca la operación de creación automática de esquema en el código de la aplicación
- **THEN** no aparece ninguna invocación

### Requirement: Estructura de directorios obligatoria

El proyecto SHALL respetar exactamente los paths de la consigna: `main.py` en la raíz de `parcial/`,
`app/core/` transversal, `app/modules/health/` con sólo `router.py` y `migrations/` con `env.py` y
`versions/`.

#### Scenario: Paths exactos

- **WHEN** se listan los directorios del proyecto
- **THEN** existen `app/core`, `app/modules/health`, `migrations/env.py` y `migrations/versions`, sin alias
  ni módulos intermedios

#### Scenario: Health mínimo

- **WHEN** se lista `app/modules/health`
- **THEN** el único archivo es `router.py`

### Requirement: Handlers asincrónicos

Todos los handlers HTTP SHALL declararse como `async def` y no SHALL ejecutar llamadas bloqueantes en el
bucle de eventos.

#### Scenario: Revisión de handlers

- **WHEN** se inspeccionan las rutas declaradas
- **THEN** todas están implementadas con funciones asincrónicas
