# Tasks

## 1. Confirmar el punto de partida

- [x] 1.1 Confirmar que no hay changes abiertos y que C-18, C-19 y C-21 están archivados: `openspec list --json` (vacío) y `Get-ChildItem openspec\changes\archive -Name`. Verificación: no hay dependencias pendientes de C-22.
- [x] 1.2 Registrar el commit de partida y el estado del árbol: `git rev-parse HEAD` y `git status --short`. Verificación: el hash queda anotado para el encabezado del transcript de la corrida limpia y el árbol sólo tiene cambios esperados de C-22 (todavía ninguno).
- [x] 1.3 Confirmar la evidencia existente: `Get-ChildItem parcial\evidencia` (C-10, C-14, C-15) y `Get-ChildItem despliegue\evidencia` (D-01…D-08). Verificación: los 3 + 8 archivos existen y no están vacíos.
- [x] 1.4 Registrar las versiones reales: `python --version` (3.13.2), `psql --version` (17.11) y el estado de Docker local (`docker --version`, ausente). Verificación: las tres salidas quedan en el transcript de la corrida limpia.
- [x] 1.5 Confirmar que no hay `.env` versionado: `git ls-files | Select-String -Pattern '(^|/)\.env$'` (vacío) y `git check-ignore -v parcial\.env despliegue\.env`. Verificación: ambos `.env` están ignorados y ninguno aparece en `git ls-files`.
- [x] 1.6 Releer §12 y §13 de `docs/CHECKLIST_ENTREGA.md`, el `.zip` de `knowledge-base/11_despliegue_y_devops.md`, IN-04 y las páginas 23-24 de la consigna. Verificación: cada tarea de este change cita un requisito de esas fuentes.

## 2. Actualizar los dos READMEs

- [x] 2.1 En `parcial/README.md`, reemplazar el bloque de placeholders por el grupo **AURA** y los cinco integrantes: Enzo Giaquinta, Agustin Contardi, Fernando Torrez, Ramiro Salcedo e Ignacio Sanchez. Verificación: no queda `_(integrante` ni la nota de “pendiente hasta C-22”.
- [x] 2.2 En `despliegue/README.md`, aplicar el mismo bloque de grupo e integrantes. Verificación: los cinco nombres y “AURA” aparecen con la misma grafía que en `parcial/README.md`.
- [x] 2.3 En `parcial/README.md`, insertar `python seed.py` entre `alembic upgrade head` y el arranque, y advertir que el seed **vacía la base** antes de cargar los datos. Verificación: los pasos quedan numerados y el orden es venv → dependencias → `.env` → migraciones → seed → uvicorn.
- [x] 2.4 Verificar que el paso del `.env` explica cómo generar la clave de firma (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) y que el README no contiene credenciales reales. Verificación: `Select-String -Path parcial\README.md -Pattern "POSTGRES_PASSWORD=\S+|JWT_SECRET=\S+"` sin valores reales.
- [x] 2.5 Revisar que ambos READMEs mantengan los requisitos Python 3.12 y PostgreSQL 16, y que `despliegue/README.md` conserve sus pasos actuales sin agregar lógica. Verificación: `git diff -- parcial/README.md despliegue/README.md` sólo muestra los bloques de integrantes y el paso del seed.

## 3. Revisar `env.example` y la higiene de secretos

- [x] 3.1 Revisar `parcial/env.example`: todas las variables con placeholders, sin usuario, contraseña ni `JWT_SECRET` reales; el archivo conserva el nombre sin punto inicial. Verificación: lectura completa y `git diff -- parcial/env.example` sin valores reales.
- [x] 3.2 Revisar `despliegue/env.example`: documenta la forma de la conexión y no contiene valores reales. Verificación: lectura completa y ninguna cadena `postgresql+asyncpg://` con usuario y contraseña.
- [x] 3.3 Confirmar que `.env` sigue ignorado y que `env.example` sí está versionado: `git check-ignore -v parcial\.env despliegue\.env` y `git ls-files parcial/env.example despliegue/env.example`. Verificación: los dos `.env` ignorados y los dos ejemplos trackeados.
- [x] 3.4 Escanear el árbol de trabajo: `git grep -nIE "POSTGRES_PASSWORD=[^<]|JWT_SECRET=[^<]|postgresql\+asyncpg://[^<\s]+:[^<\s]+@|BEGIN (RSA|OPENSSH) PRIVATE KEY"`. Verificación: los hits son placeholders conocidos o no hay hits; se anotan en el transcript.
- [x] 3.5 Escanear el historial completo: `git log -p --all | Select-String -Pattern "POSTGRES_PASSWORD=[^<]|JWT_SECRET=[^<]|postgresql\+asyncpg://[^<\s]+:[^<\s]+@"`. Verificación: si aparece una credencial real, se detiene el zip y se informa como bloqueante; si no, se anota “sin hallazgos” con la fecha.
- [x] 3.6 Confirmar que `despliegue/.dockerignore` excluye `.env`, `.venv`, `.git` y `__pycache__`. Verificación: `Get-Content despliegue\.dockerignore` contiene las cuatro entradas.

## 4. Preparar la evidencia de entrega

- [x] 4.1 Crear `docs/auditoria-final/c-22-clean-room.md` con el encabezado de la corrida: fecha, commit, sistema operativo, versiones de Python/PostgreSQL y comandos previstos. Verificación: el archivo existe y todavía no afirma resultados.
- [x] 4.2 Crear `parcial/evidencia/autoevaluacion.md` con la tabla de los 10 criterios de §13 (peso, evidencia, `Verificado: no`) y el bloque de condiciones que anulan la corrección. Verificación: 10 filas y 3 condiciones nulas presentes.
- [x] 4.3 Verificar que `parcial/evidencia/` tenga las tres capturas críticas y que ninguna contenga tokens, contraseñas ni valores de `.env`. Verificación: `Get-ChildItem parcial\evidencia` y `Select-String` sin coincidencias sensibles.
- [x] 4.4 Verificar que `despliegue/evidencia/` tenga D-01…D-08 y que `DEPLOY.md` declare URL pública, fecha/hora y los comandos sin contenido de variables. Verificación: los 8 archivos y las cinco secciones de `DEPLOY.md`.
- [x] 4.5 Revisar que la autoevaluación no repita valores de credenciales ni rutas absolutas de la máquina. Verificación: lectura completa del archivo antes de la corrida limpia.

## 5. Correr el checklist en carpeta limpia

- [x] 5.1 Crear una carpeta temporal fuera del repo (`$env:TEMP\c22-cleanroom-<fecha>`) y copiar `parcial/` y `despliegue/` con `robocopy /E` excluyendo `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache` y `.env`. Verificación: la copia no contiene ningún artefacto prohibido.
- [x] 5.2 Comparar la copia con lo que se va a entregar: `git status --short`, `git ls-files parcial despliegue` y el listado de la copia. Verificación: la diferencia son sólo los archivos nuevos de C-22, sin faltantes ni sobrantes.
- [x] 5.3 Crear una base vacía exclusiva (`parcial_c22_clean`) con el PostgreSQL local, sin tocar la base `libreria` ni la del despliegue. Verificación: `psql -c "\dt"` no muestra tablas antes de migrar.
- [x] 5.4 Crear el entorno virtual e instalar dependencias dentro de la copia limpia. Verificación: `python -m pip install -r requirements.txt` termina con exit 0.
- [x] 5.5 Crear el `.env` de la corrida desde `env.example` con credenciales descartables y una clave de firma generada para esa base. Verificación: el `.env` está sólo en la copia temporal y no se copia al repo.
- [x] 5.6 Correr `alembic upgrade head`, `alembic current`, `alembic check`, `alembic downgrade base` y `alembic upgrade head` sobre la base vacía. Verificación: cinco revisiones, `head` correcto, sin diferencias y sin error en el ciclo completo.
- [x] 5.7 Correr `python seed.py` dos veces y verificar idempotencia e invariantes (libros 1–5, venta 1, stock coherente). Verificación: la segunda corrida deja el mismo estado y no toca `alembic_version`.
- [x] 5.8 Levantar `uvicorn main:app` en un puerto libre y verificar `/health/live` y `/health/ready` con 200. Verificación: ambas respuestas quedan registradas con su código.
- [x] 5.9 Instalar las dependencias de prueba que `requirements.txt` no trae (`pytest`, `pytest-asyncio`, `httpx`) y correr `python -m pytest -q` dentro de la copia limpia. Verificación: exit 0 y el resumen de tests se anexa al transcript.
- [x] 5.10 Correr los casos `.http` de `parcial/test/`, después de cada seed, y registrar el código de cada caso C-01…C-16. Verificación: cada caso tiene resultado real, sin “se asume”. **Hecho en C-22 (2026-11-08):** los cinco archivos se ejecutaron con `httpyac` 6.16.7 sobre copias de compatibilidad fuera del repo; `auth` 12/12, `registro` 7/7, `roles` 28/28, `libros` 25/25, `ventas` 19/19. Evidencia en `parcial/test/evidencia/c22-http-*.txt` y `c22-http-resumen.md`. C-07.11 se cubrió con vencimiento real de 1 min + 62 s; C-14 con `solo_agregado.sql`.
- [x] 5.11 Recorrer §0 a §10 del checklist, sección por sección, ejecutando los comandos escritos. Verificación: cada ítem queda marcado `pasa`, `falla` o `no ejecutado` con su salida. **Hecho en C-22 (2026-11-08):** tabla completa de §0–§10 en `docs/auditoria-final/c-22-clean-room.md` §12, con greps, `alembic check`, `psql`, OpenAPI y `pytest` (472 passed, 1 skipped); salida cruda en `parcial/test/evidencia/c22-checklist-0-10.txt`. Ninguna sección quedó en `falla` o `no ejecutado`; lo reutilizado está declarado.
- [x] 5.12 Recorrer §11 sobre `despliegue/` y la URL pública: `DEPLOY.md`, D-01…D-08, imagen, salud y venta desde afuera. Verificación: se registra qué se pudo comprobar en vivo y qué se toma de la evidencia archivada.
- [x] 5.13 Recorrer §12 sobre la copia limpia: dos carpetas, contenido de cada una y ausencia de `.venv`/`__pycache__`/`.env`. Verificación: los ítems de estructura y exclusiones quedan con resultado; el nombre del zip se verifica en 8.3, cuando el archivo exista.
- [x] 5.14 Si el VPS está accesible, correr la paridad de versiones en contenedores `python:3.12` y `postgres:16`: migraciones, seed, pytest y `/health/ready`. Verificación: la salida muestra las cinco revisiones y el seed; si no hay acceso, se registra **no ejecutado** con el motivo. **Hecho en C-22 (2026-11-08):** VPS `srv1930369` con `python:3.12-alpine` (3.12.16) y `postgres:16-alpine` (16.15), clone en HEAD `00111072…`, 5 revisiones, seed completo, 472 passed/1 skipped y `/health/live` y `/health/ready` → 200. Contenedores, red y `/tmp` limpiados; despliegue existente intacto. Detalle en `c-22-clean-room.md` §13.
- [x] 5.15 Cerrar el transcript con la tabla de sustituciones (3.13.2/17.11 vs 3.12/16), los ítems no ejecutados y la limpieza de la base y el entorno temporales. Verificación: no queda ningún proceso `uvicorn` ni base de prueba en uso.

## 6. Completar la autoevaluación

- [x] 6.1 Completar las 10 filas de `parcial/evidencia/autoevaluacion.md` con peso, evidencia (archivo o comando) y `Verificado: sí/no`. Verificación: ninguna fila queda vacía y las que dicen `sí` citan una salida real del transcript.
- [x] 6.2 Completar el bloque de condiciones nulas: el proyecto levanta, el esquema sale de `alembic upgrade head` sobre base vacía y no hay credenciales reales en repo/imagen/zip. Verificación: las tres condiciones tienen su comprobación y su resultado.
- [x] 6.3 Revisar que la nota final no prometa más de lo corrido: cada criterio no verificado queda enumerado y justificado. Verificación: la autoevaluación distingue explícitamente “verificado” de “no ejecutado”.
- [x] 6.4 Revisar que `parcial/evidencia/autoevaluacion.md` no contenga credenciales, tokens, rutas absolutas ni el contenido de `.env`. Verificación: `Select-String` sin coincidencias sensibles.

## 7. Validar y cerrar el change

- [x] 7.1 Ejecutar `openspec validate c-22-entrega-zip-y-autoevaluacion --strict --json`. Verificación: exit 0 y `valid: true`.
- [x] 7.2 Marcar `[C-22]` como `[x]` en `CHANGES.md`, con la fecha y los artefactos de entrega. Verificación: la fila de C-22 deja de decir `[ ] pendiente`.
- [x] 7.3 Archivar el change con `openspec archive c-22-entrega-zip-y-autoevaluacion`. Verificación: el directorio queda en `openspec/changes/archive/` y `openspec list --json` queda vacío.
- [x] 7.4 Revisar el diff final: `git status --short` y `git diff --stat`. Verificación: sólo aparecen READMEs, evidencia nueva, transcript y `CHANGES.md`; no hay cambios en `parcial/app`, `parcial/main.py`, `parcial/migrations`, `parcial/tests`, `despliegue/app` ni `despliegue/main.py`.
- [ ] 7.5 Pedir autorización explícita y, sólo entonces, hacer el commit final en Conventional Commits: `git add` de los archivos revisados y `git commit -m "docs(c-22): cerrar entrega zip y autoevaluación"`. Verificación: `git status --short` vacío y `git log -1 --oneline` muestra el commit final.

## 8. Generar y verificar el zip

- [ ] 8.1 Registrar el commit final: `git rev-parse HEAD`. Verificación: el hash coincide con `git log -1` y el árbol sigue limpio.
- [ ] 8.2 Crear la carpeta externa `%USERPROFILE%\Entrega-Parcial` y generar el zip con `git archive --format=zip --output="$env:USERPROFILE\Entrega-Parcial\Parcial_Cap1a6_AURA.zip" HEAD parcial despliegue`. Verificación: el archivo existe, pesa más que 0 y no está dentro del repo.
- [ ] 8.3 Verificar las entradas de primer nivel: `Add-Type -AssemblyName System.IO.Compression.FileSystem` y abrir el zip con `[System.IO.Compression.ZipFile]::OpenRead(...)`. Verificación: exactamente `parcial/` y `despliegue/`, sin carpeta contenedora ni archivos sueltos.
- [ ] 8.4 Extraer en una carpeta temporal nueva con `Expand-Archive` y auditar con `Get-ChildItem -Recurse -Force`. Verificación: no aparece `.venv`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.ruff_cache`, `.env` ni `.git`.
- [ ] 8.5 Comparar el árbol extraído con el commit: `git ls-tree -r --name-only HEAD -- parcial despliegue` contra los archivos extraídos y el SHA-256 de cada archivo. Verificación: mismas rutas y mismo contenido, sin faltantes ni sobrantes.
- [ ] 8.6 Correr el humo sobre lo extraído: crear venv, instalar dependencias, `.env` descartable, base vacía `parcial_c22_zip`, `alembic upgrade head`, `python seed.py`, `uvicorn` y `/health/ready` 200. Verificación: el zip extraído levanta por sí solo, sin usar la copia de trabajo.
- [ ] 8.7 Calcular el SHA-256 con `Get-FileHash -Algorithm SHA256` y registrar commit, hash, ruta y fecha en `%USERPROFILE%\Entrega-Parcial\ENTREGA.md`. Verificación: el hash del archivo coincide con el registrado.
- [ ] 8.8 Confirmar que generar y verificar el zip no ensució el repo: `git status --short` vacío. Verificación: no hay archivos nuevos ni modificados después del commit final.

## 9. Cierre

- [ ] 9.1 Confirmar que el zip final está en `%USERPROFILE%\Entrega-Parcial\Parcial_Cap1a6_AURA.zip`, con el SHA-256 registrado y sin credenciales. Verificación: `Get-FileHash` y la auditoría de exclusiones repetidas sobre el archivo definitivo.
- [ ] 9.2 Confirmar que no se hizo `push` ni se modificó el despliegue en línea. Verificación: `git status -sb` muestra el commit local y `https://libreria.enzogiaquinta.me/health/ready` sigue respondiendo 200.
- [ ] 9.3 Dejar anotado que la subida al campus la hace un solo integrante y que el zip no se versiona. Verificación: la nota queda en `%USERPROFILE%\Entrega-Parcial\ENTREGA.md` y en el reporte final.

## Workflow follow-up

- El push y la subida al campus quedan fuera de este change hasta que el usuario los pida.
- Si el VPS no estuvo accesible en 5.14, la paridad 3.12/16 queda como riesgo residual declarado en la autoevaluación.
- Si aparece una credencial real en 3.5, el zip no se genera hasta rotarla y dejarla fuera del historial.
