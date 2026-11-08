# Spec Delta
## Purpose
Define el contrato observable del despliegue del TP de los capítulos 1 a 4 en el VPS: cómo se construye y se corre la imagen sin Docker Compose, de dónde toma la configuración, cómo se verifican los datos y las ventas desde afuera, qué garantiza la actualización y qué documentación y evidencia lo demuestran.

## ADDED Requirements
### Requirement: URL pública atendiendo el TP
El despliegue SHALL estar accesible en una URL pública declarada en `DEPLOY.md` y esa URL SHALL responder `GET /health/ready` con 200, `GET /libros/` con 200 y datos cargados, y `POST /ventas/` con 201.

#### Scenario: Salud desde afuera del VPS
- **WHEN** se consulta `GET <URL pública>/health/ready` desde fuera del servidor
- **THEN** la respuesta es 200 con el cuerpo de salud

#### Scenario: Catálogo con datos iniciales
- **WHEN** se consulta `GET <URL pública>/libros/` desde fuera del servidor
- **THEN** la respuesta es 200 e incluye los libros cargados por los datos iniciales

#### Scenario: Venta real desde afuera
- **WHEN** se envía `POST <URL pública>/ventas/` con un cliente y un renglón válidos
- **THEN** la respuesta es 201, cada precio está copiado del libro y el total coincide con la suma de los renglones

#### Scenario: URL caída
- **WHEN** alguna de las tres verificaciones falla o la URL no responde
- **THEN** el despliegue no se considera operativo y la evidencia lo registra como fallo

### Requirement: Ejecución con `docker run` sin Docker Compose
El despliegue SHALL correr la imagen con `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file <archivo> libreria`, sin Docker Compose ni un Postgres dentro del contenedor. Si el runtime real es un orquestador externo, `DEPLOY.md` SHALL declararlo y conservar el `docker run` equivalente completo.

#### Scenario: Comando documentado
- **WHEN** se lee `DEPLOY.md`
- **THEN** aparece el `docker run` completo con `--name`, `-p <puerto>:8000`, `--restart unless-stopped` y `--env-file`, y no aparece Docker Compose

#### Scenario: Ejecución equivalente verificada
- **WHEN** el contenedor lo gestiona EasyPanel y se verifica su estado
- **THEN** queda `running` y `healthy`, sin un `docker run` paralelo; la evidencia declara la equivalencia

#### Scenario: Runtime orquestado
- **WHEN** el contenedor lo gestiona EasyPanel en lugar de un `docker run` manual
- **THEN** `DEPLOY.md` lo declara como runtime principal, indica el nombre del contenedor y el puerto, y conserva el `docker run` equivalente como camino reproducible

### Requirement: Configuración en un archivo fuera del repositorio y de la imagen
La configuración de ejecución SHALL entregarse con `--env-file` desde un archivo que vive en el servidor, fuera del repositorio y de la imagen. `DEPLOY.md` SHALL indicar su **nombre o ruta** y NO SHALL reproducir su contenido ni valores reales.

#### Scenario: Archivo externo
- **WHEN** se revisa el repositorio y la imagen
- **THEN** no existe el archivo de variables de producción ni sus valores

#### Scenario: Nombre sin contenido
- **WHEN** se lee `DEPLOY.md`
- **THEN** figura el nombre del archivo de variables y ninguna contraseña, usuario real o cadena de conexión completa

#### Scenario: Variables reales del TP
- **WHEN** se compara el archivo de variables con el `Settings` del TP
- **THEN** contiene `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` y, opcionalmente, `POOL_SIZE` y `SQL_ECHO`; la URL `postgresql+asyncpg` se deriva de ellas

### Requirement: La dirección de la base no es el loopback del contenedor
Ninguna variable de dirección de base del archivo de ejecución SHALL usar `localhost` ni `127.0.0.1` cuando la base corre fuera del contenedor. Si la base está en el host Linux, SHALL usarse `host.docker.internal` junto con `--add-host=host.docker.internal:host-gateway`, o la dirección que provea la cátedra.

#### Scenario: Base alcanzable desde el contenedor
- **WHEN** el contenedor arranca con el archivo de variables real
- **THEN** la aplicación conecta y `/health/ready` responde 200

#### Scenario: Loopback declarado
- **WHEN** el archivo de variables apunta la base a `localhost` o `127.0.0.1` desde dentro del contenedor
- **THEN** el requisito se considera incumplido aunque el servidor responda desde el host

### Requirement: Datos iniciales cargados dentro del contenedor
Los datos iniciales SHALL cargarse ejecutando el comando del README del TP **dentro** del contenedor en marcha y SHALL verificarse desde afuera, no dentro.

#### Scenario: Carga dentro del contenedor
- **WHEN** el contenedor está `healthy` y se ejecuta el comando de datos iniciales del README con `docker exec`
- **THEN** la carga termina sin error y no se ejecuta durante el build

#### Scenario: Verificación desde afuera
- **WHEN** se consulta `/libros/` desde fuera del VPS después de la carga
- **THEN** la respuesta lista los datos iniciales

### Requirement: Persistencia y actualización sin pérdida de datos
Reemplazar el contenedor, con `docker rm -f` + `docker run` o con restart/recreate de EasyPanel, SHALL conservar los datos, porque la base vive fuera de él. La actualización SHALL ser construir la imagen, reemplazar el contenedor y volver a verificar, y `alembic upgrade head` NO SHALL volver a aplicar migraciones ya registradas.

#### Scenario: Reemplazo del contenedor
- **WHEN** se reemplaza el contenedor con `docker rm -f` + el mismo `docker run`, o con restart/recreate de EasyPanel
- **THEN** el contenedor vuelve a `healthy`, los libros y ventas anteriores siguen existiendo y la versión de `alembic_version` no cambia

#### Scenario: Datos dentro del contenedor
- **WHEN** la actualización depende de un volumen del contenedor para conservar datos
- **THEN** el requisito se considera incumplido: el estado debe vivir en la base del servidor

#### Scenario: Procedimiento documentado
- **WHEN** se lee `DEPLOY.md`
- **THEN** describe la secuencia build -> reemplazo (`docker rm -f` + `docker run` o restart/recreate de EasyPanel) -> verificación, y aclara que los datos no se pierden

### Requirement: `DEPLOY.md` con el contenido obligatorio
`DESPLIEGUE/DEPLOY.md` —en `despliegue/DEPLOY.md`— SHALL declarar URL pública, día y hora del despliegue, elección y justificación de dónde se construye la imagen, comandos `docker build` y `docker run` completos, cambios al TP con su motivo y procedimiento de actualización.

#### Scenario: Revisión del documento
- **WHEN** se lee `despliegue/DEPLOY.md`
- **THEN** están los cinco contenidos obligatorios: URL, fecha y hora, build/run completos con el nombre del archivo de variables sin su contenido, cambios al TP y actualización

#### Scenario: Construcción sin justificar
- **WHEN** el documento no indica si la imagen se construyó en el servidor o fuera y por qué
- **THEN** el requisito se considera incumplido

### Requirement: Evidencia real de D-01 a D-07
`despliegue/evidencia/` SHALL contener un archivo por caso D-01 a D-07 con el comando ejecutado y su salida real, y esa salida SHALL corresponder al despliegue que está en línea.

#### Scenario: Caso con salida real
- **WHEN** se revisa el archivo de un caso D-01 a D-07
- **THEN** contiene comando y salida, y la salida no es un ejemplo ni una plantilla

#### Scenario: Evidencia desactualizada
- **WHEN** la salida de un caso no coincide con el contenedor o la URL que corre hoy
- **THEN** el archivo se corrige o se vuelve a ejecutar el comando antes de cerrar el change

### Requirement: D-08 demostrado o excepción documentada
`despliegue/evidencia/D-08.md` SHALL existir. Si la aplicación desplegada emite el aviso del comprobante en segundo plano, SHALL mostrar en `docker logs` el aviso **después** de la línea de la respuesta. Si el TP cap. 1–4 no emite ese aviso, el archivo SHALL documentar la excepción, citar la evidencia de `parcial/` (C-10) y explicar por qué no se ejecuta en el contenedor de `despliegue/`.

#### Scenario: Aviso en segundo plano
- **WHEN** se registra una venta y se revisan los logs del contenedor
- **THEN** el aviso del comprobante aparece después de la línea `POST /ventas/` con su código

#### Scenario: Funcionalidad ausente en el TP
- **WHEN** el TP cap. 1–4 no tiene `BackgroundTasks` ni emite el aviso
- **THEN** `D-08.md` declara la excepción, cita la captura de `parcial/evidencia/c-10-backgroundtasks.txt` y explica que el caso pertenece al proyecto completo, sin agregar lógica nueva a `despliegue/`

#### Scenario: Archivo ausente
- **WHEN** no existe `despliegue/evidencia/D-08.md`
- **THEN** el requisito se considera incumplido

### Requirement: Despliegue sostenido en línea
El despliegue SHALL permanecer en línea hasta que se publiquen las notas, y el cierre del change NO SHALL detenerlo, borrarlo ni cambiar su URL.

#### Scenario: Verificación posterior
- **WHEN** se consulta la URL pública después de archivar el change
- **THEN** `/health/ready` sigue respondiendo 200

#### Scenario: Baja del despliegue
- **WHEN** el contenedor o el servicio se detiene antes de la corrección
- **THEN** el criterio «Despliegue en el VPS» queda expuesto a evaluarse sólo por documentación y evidencia

### Requirement: El TP conserva su lógica
C-21 NO SHALL modificar `despliegue/main.py`, `despliegue/app/`, `despliegue/migrations/`, `despliegue/alembic.ini`, `despliegue/requirements.txt` ni `despliegue/seed.py`; sólo SHALL agregar o ajustar artefactos de despliegue y documentación.

#### Scenario: Revisión del diff
- **WHEN** se compara `despliegue/` con la entrega del TP cap. 1–4
- **THEN** no hay cambios de lógica, y cualquier defecto propio corregido está anotado en `DEPLOY.md`

#### Scenario: Lógica nueva para D-08
- **WHEN** se agrega `BackgroundTasks` a `despliegue/` para fabricar el aviso
- **THEN** el requisito se considera incumplido
