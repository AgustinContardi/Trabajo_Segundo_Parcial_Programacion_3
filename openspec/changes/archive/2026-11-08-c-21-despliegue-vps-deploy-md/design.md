# Design
## Context
Ver `proposal.md` — Why. El estado que condiciona el diseño:

- El despliegue **ya está operativo** en `https://libreria.enzogiaquinta.me`: EasyPanel, proyecto `grupo-acgs`, app `libreria-api`, PostgreSQL 16 en el mismo proyecto. `/health/ready` 200, `/libros/` 200 y `POST /ventas/` 201 ya se probaron desde afuera.
- El contenedor de EasyPanel se llama `libreria-api` (no `libreria`) y publica el puerto 8000. `docker ps` filtrado por `libreria-api` es la forma de inspeccionarlo.
- El `Settings` del TP lee `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POOL_SIZE` y `SQL_ECHO`; **no lee `DATABASE_URL`**. La KB 11 y el texto de `CHANGES.md` hablan de `DATABASE_URL`: divergencia conocida, ya anotada por C-20.
- `despliegue/evidencia/` tiene D-01…D-07 con salida real del VPS. `D-08` no existe.
- `despliegue/` es el TP cap. 1–4 **sin** `BackgroundTasks`; el aviso del comprobante vive en `parcial/` y su captura está en `parcial/evidencia/c-10-backgroundtasks.txt` (el aviso aparece después de la línea `POST /ventas/ 201 Created`).
- El usuario tiene acceso SSH de sólo lectura/evidencial al VPS. No se versiona ningún valor real.
- `despliegue/DEPLOY.md` ya tiene build/run, contrato de variables, cambios al TP, actualización y la tabla de qué cubre C-20; le faltan URL pública, día y hora, justificación de dónde se construye y el procedimiento de actualización cerrado para producción.

## Goals / Non-Goals
**Goals:**

- Cerrar el 7 % del despliegue con lo que la corrección busca: URL viva verificada desde afuera, `DEPLOY.md` completo y D-01…D-08 en `despliegue/evidencia/`.
- Demostrar D-02 con el contenedor actual y D-04 por equivalencia del reinicio controlado de EasyPanel, sin poner en riesgo el despliegue principal.
- Dejar D-08 resuelto de forma honesta: evidencia del aviso en el proyecto completo o excepción documentada, nunca lógica inventada en el TP.

**Non-Goals:**

- Cambiar la imagen, el `Dockerfile`, el `.dockerignore`, `env.example` o la lógica del TP.
- Reemplazar EasyPanel por Docker plano como runtime principal.
- Tocar `parcial/`, migraciones, tests o `despliegue/app/`.
- Hacer `commit` o `push`.

## Decisions
### D1 — Fuente de verdad del despliegue: EasyPanel en la URL pública
**Decisión**: el despliegue que se corrige es el de EasyPanel (`https://libreria.enzogiaquinta.me`, app `grupo-acgs/libreria-api`, puerto 8000). `DEPLOY.md` lo declara como runtime principal y conserva el `docker run` literal como camino equivalente y reproducible.

**Por qué**: es el sistema que ya responde desde afuera y el que la cátedra va a probar. Ocultarlo para fingir un `docker run` manual sería documentación falsa; ignorar el `docker run` que pide la consigna dejaría el requisito sin demostrar. Se documentan ambos y se distingue cuál es el principal.

**Alternativas**: migrar todo a `docker run` manual — rechazada: implica bajar el servicio en línea y perder el build desde GitHub y el health gestionado; documentar sólo EasyPanel — rechazada: incumple el texto explícito de §11.

### D2 - D-04: equivalencia EasyPanel (sin one-off)
**Decisión**: no se ejecuta un contenedor one-off ni el `docker run` literal en paralelo. D-04 se demuestra con el reinicio controlado del contenedor que gestiona EasyPanel (`docker restart "$CID"` sobre `libreria-api`) y la verificación de que vuelve `healthy`, `alembic current` sigue en `5f67a857f685 (head)` y los datos de referencia (por ejemplo libro 4 con stock 2) persisten. `DEPLOY.md` registra explícitamente que el comando literal de la consigna no se corrió y que D-04 se cumple por equivalencia, marcado como parcial en la evidencia.
**Por qué**: el usuario indicó que el despliegue es solo por EasyPanel. Bajar el servicio para un `docker run` manual agrega riesgo sin mejorar la nota; la persistencia y la no repetición de migraciones se pueden demostrar con el reinicio del contenedor real. La equivalencia es parcial: no incluye un recreate completo ni el comando literal.
**Riesgo**: el evaluador puede pedir el `docker run` textual. Mitigación: `DEPLOY.md` conserva el comando literal copiable y explica la equivalencia; `D-04.md` marca la diferencia.

### D3 — D-08: excepción documentada con la evidencia de `parcial/` (opción a)
**Decisión**: `despliegue/evidencia/D-08.md` documenta que el aviso del comprobante pertenece a `parcial/` (C-10) y cita `parcial/evidencia/c-10-backgroundtasks.txt`, donde el aviso aparece **después** de la línea de respuesta. El archivo explica por qué no se ejecuta en el contenedor del TP cap. 1–4.

**Por qué**: la consigna pide D-08 sobre el despliegue, pero el TP cap. 1–4 se entrega «tal como se entregó» y no tiene `BackgroundTasks`. Agregarlo sería cambiar la lógica del TP para fabricar una evidencia, exactamente lo que la regla dura 16 y la separación `parcial/`/`despliegue/` prohíben. La captura existente demuestra el orden real en el proyecto completo (cap. 5–6), que es donde la funcionalidad existe.

**Alternativas**:
- (b) agregar `BackgroundTasks` a `despliegue/app/` — rechazada: modifica el TP y rompe «su lógica no se toca»; además exigiría recompilar y redesplegar para una captura.
- (c) declarar D-08 «no aplicable» sin citar evidencia — más débil: no demuestra el orden en ningún lado.
- (a) con cita — elegida: deja el caso rastreable, sin tocar código.

**Consecuencia asumida**: si la cátedra exige el aviso dentro del contenedor de `despliegue/`, el caso no suma; queda mitigado por la captura de `parcial/` y por la explicación de la separación. El usuario puede cambiar a (c) si prefiere no citar `parcial/`; se registraría en el mismo archivo.

### D4 — Contrato de variables: `POSTGRES_*`, no `DATABASE_URL`
**Decisión**: `DEPLOY.md` documenta el archivo de variables con las siete `POSTGRES_*` y la URL derivada `postgresql+asyncpg://…` como comentario. No se declara `DATABASE_URL`.

**Por qué**: es lo que el código lee. Un `--env-file` con sólo `DATABASE_URL` deja el contenedor muerto por campos faltantes (D-05 ya lo demostró). La verificación de §11 «la `DATABASE_URL` no usa `localhost`» se satisface en sustancia: `POSTGRES_HOST` no es loopback y el arranque conecta desde el contenedor.

**Alternativa**: agregar `DATABASE_URL` al `Settings` — rechazada: cambia el TP.

### D5 — Construcción: EasyPanel desde GitHub, build path `despliegue/`
**Decisión**: `DEPLOY.md` declara que la imagen se construye **en el servidor** por EasyPanel desde el repositorio de GitHub, con build path `despliegue/`; y además deja el `docker build -t libreria .` local como camino reproducible.

**Por qué**: es lo que realmente pasó y lo que mantiene la imagen actualizada con cada push. La consigna permite construir en el servidor o afuera, pero exige elegir y justificarlo.

**Nota de honestidad**: no hay log crudo del builder de EasyPanel; la evidencia es la imagen resultante `running | healthy`, el `Dockerfile` versionado y `alembic current` en head. Se dice así, sin inventar un log.

### D6 — Evidencia: revisar D-01…D-07 contra el estado actual
**Decisión**: cada archivo de D-01 a D-07 se relee y se vuelve a ejecutar su comando si la salida no coincide con el contenedor de hoy. Los archivos conservan formato `# D-0N — título`, fecha, host, comandos y salida.

**Por qué**: el contenedor cambió de nombre (`libreria-api`) y la base ya tiene ventas de prueba; una evidencia que cita un contenedor que no existe deja de ser verificable.

### D7 — `DEPLOY.md` como documento único de despliegue
**Decisión**: completar el documento existente, sin crear otro: URL, fecha y hora (UTC-3), topología EasyPanel, build elegido, build/run literales con el nombre del archivo, cambios al TP, actualización/rollback, problemas frecuentes y tabla de evidencia. Se elimina la nota que decía «D-08 queda para C-21» una vez resuelto.

**Por qué**: la corrección busca un solo `DEPLOY.md` con todo. Un anexo aparte se pierde.

## Risks / Trade-offs
- **D-04 sin comando literal** -> el evaluador puede exigir el `docker run`. Mitigación: `DEPLOY.md` conserva el comando copiable y `D-04.md` declara la equivalencia EasyPanel; no se inventa una corrida.
- **El restart de EasyPanel no demuestra el comando literal** -> D-04 queda parcial. Mitigación: registrar la diferencia explícita y no afirmar que se corrió `docker run`.
- **D-08 no suma en la corrección** → se pierde un ítem del 7 %. Mitigación: excepción documentada con captura real de `parcial/`; no se toca el TP.
- **Publicar valores reales al completar `DEPLOY.md`** → condición que anula la corrección. Mitigación: sólo el **nombre/ruta** del archivo; revisión final con `Select-String` buscando `password`, `POSTGRES_PASSWORD=`, cadenas de conexión.
- **Bajar el despliegue por error al probar** -> el criterio se evalúa sólo por documentación. Mitigación: sólo se hace el reinicio controlado controlado de D-04; no se crean contenedores paralelos.
- **Evidencia desactualizada** → el caso no es verificable. Mitigación: revisión archivo por archivo contra el contenedor actual.
- **Divergencia de la KB (`DATABASE_URL`)** → un lector futuro usa la variable equivocada. Mitigación: `DEPLOY.md` documenta el contrato real; corregir la KB queda para un change de documentación aparte.

## Evidence plan
| Caso | Acción en C-21 | Resultado que se archiva |
| --- | --- | --- |
| D-01 | Releer y, si hace falta, `docker images` en el VPS | base Alpine < 100 MB + imagen del proyecto |
| D-02 | Releer el contenedor actual y su `alembic current` | `running | healthy` + revisión de Alembic |
| D-03 | `curl` desde fuera del VPS a `/health/ready`, `/libros/` y `POST /ventas/` | 200, 200 con datos, 201 con precios y total |
| D-04 | Reinicio del contenedor gestionado por EasyPanel (`docker restart`; sin recreate ni one-off); datos y `alembic_version` | vuelve `healthy`, datos intactos, misma revisión; equivalencia parcial documentada |
| D-05 | Releer; si hace falta, correr sin `POSTGRES_*` | `ValidationError` + `Exited (1)` |
| D-06 | Releer `ls -a /app` y `env` | sin `.env` ni credenciales |
| D-07 | Releer `docker exec libreria-api id` | `uid=100(app)` |
| D-08 | Crear `D-08.md` con la excepción y la cita a `parcial/` | aviso después de la respuesta en `parcial/`, explicación de la separación |

## Migration Plan
No hay migración de datos ni de esquema. El cambio es documental y de evidencia. Rollback: el reinicio controlado no crea contenedores paralelos; el despliegue principal no se toca. `libreria-api` sigue en línea; no se detiene al archivar el change.

## UI Mockups
- Design system revision: no aplica (no existe `design-system/`).
- Decision: no (no UI) — 2026-11-08. El change no agrega ni modifica pantallas, componentes, estilos ni interacciones; sólo documentación y evidencia de un despliegue ya existente.
- Approval: no aplica.
- Preview: no aplica.
- Visual verify: no aplica.

## Open Questions
- Ninguna bloqueante. D-08 queda en la opción (a) confirmada por el usuario: excepción documentada citando `parcial/`.
- D-04 se documenta por equivalencia EasyPanel; no se ejecuta un one-off.
