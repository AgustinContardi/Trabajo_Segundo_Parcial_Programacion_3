# entrega-final Specification

## Purpose
Define la forma y el contenido del artefacto que se entrega al campus: un único `.zip` con
`parcial/` y `despliegue/`, dos READMEs que identifican al grupo y permiten levantarlo desde cero,
una corrida limpia del checklist y una autoevaluación trazable contra la rúbrica.

## Requirements

### Requirement: Nombre y forma del archivo de entrega

La entrega SHALL ser un único archivo llamado `Parcial_Cap1a6_AURA.zip`, subido por un solo
integrante, y su raíz SHALL contener exactamente las carpetas `parcial/` y `despliegue/`.

#### Scenario: Nombre exacto
- **WHEN** se inspecciona el archivo que se sube al campus
- **THEN** su nombre es `Parcial_Cap1a6_AURA.zip`

#### Scenario: Sólo dos carpetas en la raíz
- **WHEN** se listan las entradas de primer nivel del zip
- **THEN** aparecen únicamente `parcial/` y `despliegue/`, sin carpeta contenedora adicional

#### Scenario: Falta una carpeta
- **WHEN** la extracción no produce `parcial/` o no produce `despliegue/`
- **THEN** la entrega no cumple el formato y no se considera lista

### Requirement: Contenido de `parcial/`

`parcial/` SHALL incluir el código fuente, `requirements.txt`, `env.example`, `alembic.ini`,
`migrations/`, `test/`, `README.md` y `evidencia/`. `evidencia/` SHALL incluir las tres capturas
críticas: C-10 (`BackgroundTasks`), C-14 (`solo_agregado`) y C-15 (consultas con 2 y 4 renglones).

#### Scenario: Árbol esperado
- **WHEN** se listan `parcial/` y `parcial/evidencia/`
- **THEN** aparecen los archivos y carpetas obligatorios y las tres capturas críticas

#### Scenario: Evidencia faltante
- **WHEN** falta alguna de las tres capturas críticas
- **THEN** el requisito se considera incumplido aunque el código esté completo

### Requirement: Contenido de `despliegue/`

`despliegue/` SHALL incluir el TP de los capítulos 1 a 4 tal como se entregó, más `Dockerfile`,
`.dockerignore`, `env.example` con la forma de las variables y sin valores, `DEPLOY.md` y
`evidencia/` con D-01…D-08. No SHALL incluir cambios del parcial en su lógica.

#### Scenario: Árbol esperado
- **WHEN** se listan `despliegue/` y `despliegue/evidencia/`
- **THEN** aparecen el `Dockerfile`, `.dockerignore`, los dos documentos y los ocho archivos D

#### Scenario: Lógica del parcial filtrada
- **WHEN** se compara `despliegue/app/` con la entrega del TP de los capítulos 1 a 4
- **THEN** la lógica es la del TP y sólo se agregaron los archivos de despliegue

### Requirement: Exclusiones del zip

El zip no SHALL contener `.venv/`, `__pycache__/`, archivos `*.pyc`, `.pytest_cache/`,
`.ruff_cache/` ni `.env` en ninguna de las dos carpetas. Tampoco SHALL contener `.git/`; si se
incluyera, su historial no podría contener credenciales reales.

#### Scenario: Auditoría de artefactos prohibidos
- **WHEN** se recorre el contenido extraído con `Get-ChildItem -Recurse -Force`
- **THEN** no aparece `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.env` ni `.git`

#### Scenario: `.env` local existe pero no viaja
- **WHEN** el working tree tiene un `.env` ignorado y se arma el zip desde el commit
- **THEN** el archivo no aparece en el zip

### Requirement: READMEs con grupo, integrantes y puesta en marcha

`parcial/README.md` y `despliegue/README.md` SHALL declarar el grupo **AURA** y los integrantes
Enzo Giaquinta, Agustin Contardi, Fernando Torrez, Ramiro Salcedo e Ignacio Sanchez, con nombre y
apellido. `parcial/README.md` SHALL describir la puesta en marcha desde cero: entorno virtual,
dependencias, `.env` con cómo generar la clave de firma, `alembic upgrade head`, `python seed.py`
y arranque del servidor.

#### Scenario: Identificación del grupo
- **WHEN** se lee cualquiera de los dos READMEs
- **THEN** figuran el grupo AURA y los cinco integrantes, sin placeholders

#### Scenario: Puesta en marcha completa
- **WHEN** se siguen los pasos de `parcial/README.md` en una máquina sin entorno previo
- **THEN** las migraciones, el seed y el arranque se ejecutan en ese orden sin pasos faltantes

#### Scenario: Semilla destructiva advertida
- **WHEN** se lee el paso de `python seed.py`
- **THEN** el README advierte que el seed vacía la base antes de cargar los datos

### Requirement: Corrida limpia del checklist

La entrega SHALL verificarse ejecutando `docs/CHECKLIST_ENTREGA.md` sobre una copia limpia, con
base vacía, esquema creado sólo por `alembic upgrade head`, seed, arranque y las pruebas. La
corrida SHALL registrar fecha, versiones reales de Python y PostgreSQL, comandos y resultados. Toda
sustitución de versión y todo ítem no ejecutado SHALL declararse como tal.

#### Scenario: Base vacía y esquema por Alembic
- **WHEN** se levanta la copia limpia contra una base recién creada
- **THEN** `alembic upgrade head` crea el esquema y no se usa `create_all`

#### Scenario: Sustitución de versiones documentada
- **WHEN** la corrida usa Python o PostgreSQL distintos de 3.12 y 16
- **THEN** el registro indica las versiones usadas, el motivo y la verificación compensatoria

#### Scenario: Ítem no ejecutado
- **WHEN** un ítem del checklist no se puede correr
- **THEN** la autoevaluación lo marca como no verificado y lo enumera, sin darlo por cumplido

### Requirement: Autoevaluación contra la rúbrica

`parcial/evidencia/autoevaluacion.md` SHALL contener los 10 criterios de la rúbrica con su peso, la
evidencia concreta de cada uno y su estado de verificación, más un bloque sobre las condiciones
que anulan la corrección: el proyecto levanta, el esquema sale de Alembic sobre base vacía y no hay
credenciales reales en el repositorio, la imagen ni el zip.

#### Scenario: Diez criterios presentes
- **WHEN** se lee `parcial/evidencia/autoevaluacion.md`
- **THEN** están los 10 criterios con peso y evidencia, y el bloque de condiciones nulas

#### Scenario: Verificación honesta
- **WHEN** un criterio no se comprobó con un comando o una salida real
- **THEN** figura como no verificado y no se marca cumplido

### Requirement: Zip trazable a un commit limpio

El zip SHALL generarse desde el commit final, con `git status --short` vacío, y SHALL registrarse
su SHA-256. La extracción SHALL verificarse en una carpeta temporal y el resultado SHALL coincidir
con el contenido del commit. Después de generar el zip no SHALL modificarse su contenido.

#### Scenario: Árbol limpio antes de comprimir
- **WHEN** se ejecuta `git status --short` antes de generar el zip
- **THEN** la salida está vacía y el zip se genera desde `HEAD`

#### Scenario: Extracción verificada
- **WHEN** se extrae el zip en una carpeta temporal
- **THEN** el árbol coincide con el commit y pasa la auditoría de exclusiones

#### Scenario: Historial sin credenciales
- **WHEN** se revisa el historial de git y el contenido del zip
- **THEN** no aparece ninguna credencial real
