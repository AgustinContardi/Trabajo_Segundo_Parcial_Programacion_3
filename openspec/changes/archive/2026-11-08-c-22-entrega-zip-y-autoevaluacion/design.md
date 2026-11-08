# Design

## Context

Ver `proposal.md` — Why. El estado que condiciona el diseño:

- C-01…C-21 están archivados y `openspec list --json` está vacío. El proyecto, la imagen y el
  despliegue en `https://libreria.enzogiaquinta.me` ya existen; C-22 sólo empaqueta y verifica.
- `parcial/` tiene el proyecto completo con cinco migraciones, `seed.py`, `test/` y
  `parcial/evidencia/` con las tres capturas críticas. `despliegue/` tiene D-01…D-08 y `DEPLOY.md`.
- Los dos READMEs existen, pero tienen placeholders de dos integrantes y `parcial/README.md` no
  incluye `python seed.py`.
- En el working tree hay `.env` en `parcial/` y en `despliegue/`, `parcial/__pycache__/` y
  `parcial/.pytest_cache/`; todos están ignorados por git. El zip no puede armarse con una copia
  ingenua de las carpetas.
- La máquina local tiene Python 3.13.2 y PostgreSQL 17.11; la consigna pide 3.12 y 16. Docker no
  está instalado localmente, pero sí en el VPS que ya corre el despliegue.
- `docs/CHECKLIST_ENTREGA.md` tiene 200 líneas y ~136 ítems; §12 y §13 son la aceptación de C-22.
- `docs/Parcial_Cap1a6_Consigna.pdf` p. 23-24 fija la rúbrica, el nombre del zip, las dos carpetas
  y las condiciones que anulan la corrección. `knowledge-base/10_preguntas_abiertas.md` IN-04
  confirma las dos carpetas.

## Goals / Non-Goals

**Goals:**

- Producir un zip que la cátedra pueda extraer y correr sin pasos ocultos, y que no incluya nada
  prohibido por la consigna.
- Dejar por escrito, con evidencia verificable, qué se corrió, con qué versiones y qué queda
  pendiente.
- Que el zip sea reconstruible desde un commit limpio y que su contenido coincida con ese commit.

**Non-Goals:**

- No cambiar código, migraciones, tests, modelos ni la lógica de `parcial/` o `despliegue/`.
- No re-desplegar, reiniciar ni modificar el servicio del VPS.
- No reescribir el historial de git ni incluir `.git` en el zip.
- No subir el archivo al campus (lo hace un integrante) ni hacer `commit`/`push` sin autorización.
- No crear ninguna pantalla ni componente visual.

## Decisions

### D1 — Nombre, raíz y forma del zip

**Decisión**: `Parcial_Cap1a6_AURA.zip`, con exactamente dos entradas de primer nivel: `parcial/` y
`despliegue/`. Sin carpeta contenedora, sin archivos sueltos en la raíz.

**Por qué**: la consigna p. 1 y p. 24 fijan `Parcial_Cap1a6_<NombreDelGrupo>.zip`; IN-04 confirma
que son dos proyectos distintos y no uno. El grupo es **AURA**.

**Alternativas**: `Parcial_Cap1a6_AURA/` como carpeta raíz — rechazada: agrega un nivel que la
consigna no pide y complica la corrección; un zip por carpeta — rechazado: la entrega es una sola.

### D2 — Fuente del zip: `git archive HEAD`, no una copia del working tree

**Decisión**: generar el zip con `git archive --format=zip --output=<fuera del repo> HEAD parcial
despliegue` sobre el commit final. El zip contiene sólo archivos versionados y con la ruta exacta
del commit.

**Por qué**: elimina por construcción `.env`, `.venv`, `__pycache__`, `.pytest_cache` y cualquier
archivo no versionado, y garantiza que lo que se entrega es lo que se revisó. Una copia con
`robocopy` depende de que la lista de exclusiones esté completa; `git archive` no.

**Alternativas**: `Compress-Archive` sobre las carpetas — rechazada: puede incluir artefactos
ignorados y permite que el zip no coincida con `HEAD`; `git archive` del índice — no existe como
opción estable.

### D3 — Exclusiones y auditoría del contenido

**Decisión**: además de lo que `git archive` ya garantiza, auditar el zip extraído con
`Get-ChildItem -Recurse -Force` y fallar si aparece `.venv`, `__pycache__`, `*.pyc`,
`.pytest_cache`, `.ruff_cache`, `.env` o `.git`. `.gitignore` y `.dockerignore` sí se incluyen:
son parte del proyecto y no contienen secretos.

**Por qué**: la consigna nombra explícitamente `.venv`, `__pycache__` y `.env`; los cachés son
ruido que también conviene sacar. `git archive` no incluye `.git`, así que la revisión del
historial se hace en el repositorio, no dentro del zip.

**Alternativas**: incluir `.git` y revisar su historial — rechazada por KB 11: un secreto borrado
sigue en el historial y obliga a rotarlo; no incluir `.git` elimina esa superficie.

### D4 — Bloque de integrantes y puesta en marcha en los READMEs

**Decisión**: en `parcial/README.md` y `despliegue/README.md`, reemplazar los placeholders por este
bloque, idéntico en ambos:

```md
## Integrantes

Grupo **AURA**

- Enzo Giaquinta
- Agustin Contardi
- Fernando Torrez
- Ramiro Salcedo
- Ignacio Sanchez
```

En `parcial/README.md`, la puesta en marcha queda en este orden: entorno virtual, dependencias,
`.env` desde `env.example` con generación de la clave de firma, `alembic upgrade head`,
`python seed.py` y arranque con `uvicorn`. El paso del seed advierte que **vacía la base** antes de
cargar los datos. `despliegue/README.md` conserva sus pasos actuales; sólo cambia el bloque de
integrantes.

**Por qué**: la consigna pide nombres y apellidos y los seis pasos desde cero, incluido el seed;
hoy el README salta del `alembic upgrade head` al servidor. La advertencia evita que un evaluador
pierda datos por correr el seed sobre una base ya cargada.

**Alternativas**: un `CONTRIBUTORS.md` aparte — rechazada: la consigna pide los nombres en el
README; un solo README compartido — rechazada: cada carpeta se corrige por separado.

### D5 — Corrida limpia: local completa + paridad 3.12/16 en contenedor

**Decisión**: la corrida completa de `docs/CHECKLIST_ENTREGA.md` se hace en una carpeta temporal
limpia de esta máquina, con Python 3.13.2 y PostgreSQL 17.11, y se registra la sustitución respecto
de 3.12/16. Como verificación compensatoria, si el VPS está accesible, se corre en contenedores
`python:3.12` y `postgres:16` la secuencia sensible a la versión: `alembic upgrade head` sobre base
vacía, `downgrade base`/`upgrade head`, `python seed.py`, `pytest` y `/health/ready`. Si el VPS no
está accesible, esa verificación se marca **no ejecutada** y queda como riesgo residual explícito.

**Por qué**: la corrida completa incluye los `.http` con REST Client y la revisión visual de
evidencia, que necesitan la máquina local y no se pueden hacer por SSH dentro de un contenedor.
La paridad en contenedor cubre lo que sí depende del intérprete y del motor: migraciones, driver,
seed y suite. Declarar la diferencia es más honesto que afirmar una corrida 3.12/16 que no ocurrió.

**Alternativas**: correr todo dentro de `python:3.12` en el VPS — rechazada: los `.http` y la
inspección de archivos no son viables en esa sesión; comprar/instalar Docker local — fuera de
alcance y no hace falta para el objetivo.

### D6 — Evidencia de la corrida: transcript afuera, resumen adentro

**Decisión**: el transcript completo (fecha, versiones, comandos, salidas y fallos) se guarda en
`docs/auditoria-final/c-22-clean-room.md` y no entra al zip. El resumen verificable, con los 10
criterios, vive en `parcial/evidencia/autoevaluacion.md` y sí entra. El commit final, el SHA-256 y
la ruta del zip se registran en `%USERPROFILE%\Entrega-Parcial\ENTREGA.md`, junto al archivo y
fuera del repositorio, para no ensuciar el árbol después del commit.

**Por qué**: si el transcript se agregara después de correr el checklist, el zip cambiaría y lo
probado dejaría de ser lo entregado; si se agregara antes, la corrida no podría citar su propio
resultado. Separar transcript (afuera) de resumen (adentro) rompe el círculo sin inventar nada.

**Alternativas**: meter el transcript en el zip y volver a comprimir — rechazada: el zip final
tendría un transcript que describe un zip anterior; no incluir evidencia de la corrida — rechazada:
la consigna pide registrar lo que no se pudo correr.

### D7 — Autoevaluación: 10 criterios, estados binarios y condiciones nulas

**Decisión**: `parcial/evidencia/autoevaluacion.md` tendrá una tabla con los 10 criterios de §13,
su peso, la evidencia concreta (archivo o comando) y `Verificado: sí/no`. Sólo se marca `sí` si hay
salida real o archivo verificable. Debajo, un bloque con las tres condiciones que anulan la
corrección y su comprobación: levanta, esquema por Alembic sobre base vacía, sin credenciales
reales en repo/imagen/zip.

**Por qué**: la rúbrica es criterio por criterio y la frase de cierre del checklist exige haber
corrido lo que se afirma. Un estado binario evita el “parcialmente” que no se puede defender.

**Alternativas**: una tabla con porcentaje estimado — rechazada: la nota la pone la cátedra; marcar
todo `sí` por confianza — rechazada: contradice la evidencia y la governance crítica.

### D8 — Orden de cierre: validar → documentar → commit → zip → extraer → humo

**Decisión**: el orden es: (1) contenido final en READMEs y evidencia; (2) corrida limpia y
autoevaluación; (3) `openspec validate --strict`, marcar `[C-22]` y archivar; (4) commit final con
autorización explícita; (5) `git archive` a una ruta externa; (6) extraer en carpeta temporal y
auditar; (7) humo sobre lo extraído (base vacía, migraciones, seed, arranque, salud); (8) SHA-256 y
nota externa. Si algo falla después del commit, se corrige y se repite desde (4); nunca se parchea
el zip.

**Por qué**: el zip tiene que salir del commit final y no puede cambiar después de verificarse.
Validar antes de commitear evita commits de corrección; extraer y correr el humo después demuestra
que el archivo —no sólo el working tree— funciona.

**Alternativas**: comprimir primero y commitear después — rechazada: el zip podría no coincidir con
ningún commit; commitear el zip — rechazada: el repositorio ya contiene todo y el zip se duplica.

### D9 — Dónde se guarda el zip

**Decisión**: el archivo final se guarda fuera del repositorio, en
`%USERPROFILE%\Entrega-Parcial\Parcial_Cap1a6_AURA.zip`, y se registra su SHA-256. El archivo no se
versiona ni se agrega al `.gitignore`; simplemente vive fuera del árbol.

**Por qué**: guardarlo en la raíz ensucia `git status` justo después de exigir un árbol limpio y
puede entrar en un zip futuro por accidente. Fuera del repo no hay ambigüedad.

**Alternativas**: `dist/` dentro del repo con una entrada de `.gitignore` — rechazada: obliga a
tocar `.gitignore` y deja el artefacto dentro del árbol; dejarlo sólo en Descargas — rechazada:
ruta menos estable para documentar.

### D10 — Higiene de secretos

**Decisión**: revisar `parcial/env.example` y `despliegue/env.example` para que sólo tengan
placeholders; confirmar con `git check-ignore -v` que los `.env` están ignorados y con
`git ls-files` que ninguno está versionado; escanear el árbol y el historial con patrones de
contraseña, `JWT_SECRET`, cadenas `postgresql+asyncpg://` con credenciales y claves privadas.
Cualquier hallazgo real bloquea el zip hasta corregirlo o rotarlo.

**Por qué**: una credencial real en el repo, la imagen o el zip es una condición que anula la
corrección, sin importar el resto. El `.env` local no viaja por `git archive`, pero el historial y
los ejemplos sí se revisan.

**Alternativas**: confiar sólo en `.gitignore` — rechazada: no cubre el historial ni los ejemplos;
borrar `.env` antes de comprimir — innecesario y arriesgado: `git archive` ya los excluye.

### D11 — Sin interfaz de usuario

**Decisión**: `Decision: no (no UI)`. C-22 no crea pantallas, componentes, layouts ni estilos; el
README y la evidencia son Markdown, no una interfaz.

**Por qué**: el flujo de diseño global sólo aplica a cambios visuales; forzar un mockup acá sería
trabajo sin valor para la entrega.

## Risks / Trade-offs

- **Python 3.13.2/PostgreSQL 17.11 local contra 3.12/16 pedidos** → corrida completa local con
  sustitución documentada y paridad en contenedores `python:3.12`/`postgres:16` para migraciones,
  seed, pytest y salud. Si el VPS no responde, se marca como no ejecutada y queda como riesgo.
- **`.env`, `.venv` y cachés presentes en el working tree** → el zip sale de `git archive HEAD`, no
  de una copia; además se audita el extraído y se falla si aparece un artefacto prohibido.
- **Credenciales en el historial** → escaneo de `git log -p --all` y de los archivos actuales; un
  hallazgo real bloquea la entrega. No se incluye `.git` en el zip.
- **Autoevaluación optimista** → cada fila exige archivo o comando; lo no corrido se marca `no` y
  se enumera. La frase de cierre del checklist se aplica literalmente.
- **Zip que no coincide con el commit** → `git archive HEAD`, comparación del árbol extraído con
  `git ls-tree` y SHA-256 registrado; cualquier cambio posterior obliga a repetir el circuito.
- **Transcript dentro del zip invalida lo probado** → el transcript vive en
  `docs/auditoria-final/`; el zip sólo lleva el resumen de autoevaluación.
- **Commit sin autorización** → el paso de commit se bloquea hasta que el usuario lo pida
  explícitamente; el resto del trabajo queda en el working tree.

## Migration Plan

No hay migración de datos ni de esquema. El “despliegue” de este change es documental:

1. Actualizar READMEs y evidencia; correr el checklist en limpio.
2. Validar y archivar el change; commit final con autorización.
3. Generar el zip desde `HEAD`; extraer, auditar y correr el humo.
4. Guardar el zip fuera del repo y registrar commit + SHA-256.
5. Rollback: si la auditoría falla, se descarta el zip, se corrige el contenido, se repite el
   commit y se regenera; el repo anterior no se toca.

## Open Questions

Ninguna que cambie el alcance. Queda pendiente para la ejecución confirmar si el VPS acepta la
corrida en contenedores `python:3.12`/`postgres:16`; en cualquier caso el resultado se registra y
no altera las decisiones.
