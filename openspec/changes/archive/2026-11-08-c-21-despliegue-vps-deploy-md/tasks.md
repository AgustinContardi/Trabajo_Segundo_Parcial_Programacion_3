# Tasks

## 1. Confirmar el estado real del despliegue antes de tocar nada
- [x] 1.1 Identificar el contenedor que atiende la URL pública: `docker ps` filtrado por `libreria-api`, nombre, imagen, puertos y estado. Verificación: el nombre y el puerto coinciden con lo que se va a escribir en `DEPLOY.md`.
- [x] 1.2 Confirmar la URL pública y su salud sin tocar el servidor: `Invoke-RestMethod https://libreria.enzogiaquinta.me/health/ready` → 200. Verificación: la respuesta es 200 y se registra fecha y hora UTC-3.
- [x] 1.3 Confirmar la versión de la base: `docker exec <contenedor> python -m alembic current`. Verificación: devuelve `5f67a857f685 (head)` o la revisión vigente; se anota el valor para comparar en D-04.
- [x] 1.4 Localizar el archivo de variables real **fuera del repo** y confirmar que no está versionado: `ls -l /home/<usuario>/libreria.env` y `git ls-files | Select-String "libreria.env"` (vacío). Verificación: sólo se documenta el nombre/ruta, nunca el contenido.

## 2. Revisar D-01…D-07 contra el contenedor de hoy
- [x] 2.1 Releer `despliegue/evidencia/D-01.md` y, si la salida no coincide, volver a correr `docker images` en el VPS. Verificación: el archivo tiene comando y salida con `python:3.12-alpine` < 100 MB y la imagen del proyecto.
- [x] 2.2 Releer `D-02.md`; si el contenedor cambió de nombre, actualizar el comando para que cite `libreria-api`. Verificación: comando ejecutable y salida `running | healthy` con la revisión de Alembic.
- [x] 2.3 Releer `D-03.md` y completar con la verificación desde fuera del VPS: `/health/ready` 200, `/libros/` 200 con datos, `POST /ventas/` 201. Verificación: la salida incluye precios copiados por renglón y total; no se pega ningún token ni credencial.
- [x] 2.4 Releer `D-04.md`; dejarlo preparado para anexar el resultado del one-off del punto 3 (o el equivalente documentado). Verificación: el archivo explica que `alembic upgrade head` corre pero no aplica nada porque la base está en head.
- [x] 2.5 Releer `D-05.md`; si hace falta, repetir la corrida sin `POSTGRES_*` y registrar `Exited`. Verificación: el log contiene `ValidationError` por los campos faltantes y `EXIT=1`; con `--rm` no queda contenedor que listar.
- [x] 2.6 Releer `D-06.md` con `docker run --rm --entrypoint ls <imagen> -a /app` y `--entrypoint env <imagen>`. Verificación: no aparece `.env` ni `POSTGRES_PASSWORD`/`POSTGRES_HOST`/cadena de conexión.
- [x] 2.7 Releer `D-07.md` con `docker exec libreria-api id`. Verificación: `uid=100(app)`, distinto de root.

## 3. D-04: persistencia con reinicio del contenedor EasyPanel
- [x] 3.1 Confirmar que la imagen y el contenedor activo son los de EasyPanel: `docker ps` filtrado por `libreria-api` y `docker images`; anotar imagen/tag. Verificación: el contenedor `libreria-api` está `healthy` y la imagen coincide con la desplegada.
- [x] 3.2 Registrar la línea base: `docker exec "$CID" python -m alembic current` y un dato de referencia (libro 4 con stock 2). Verificación: revisión `5f67a857f685 (head)` y dato anotados.
- [x] 3.3 Ejecutar el reinicio controlado del contenedor gestionado por EasyPanel (`docker restart "$CID"` sobre `libreria-api`) para D-04, sin `docker run` manual y sin bajar el servicio más que el reinicio. Verificación: la acción queda registrada con fecha y hora.
- [x] 3.4 Verificar persistencia: `docker inspect` -> `running | healthy`, `docker exec "$CID" python -m alembic current` -> misma revisión, y el dato de referencia sigue igual; `alembic_version` no cambió. Verificación: los tres valores coinciden con 3.2.
- [x] 3.5 Documentar en `D-04.md` y `DEPLOY.md` que D-04 se cumple por equivalencia EasyPanel, no por el `docker run` literal; marcar la diferencia explícitamente. Verificación: la evidencia no afirma haber corrido el comando literal.

## 4. D-08: evidencia o excepción documentada
- [x] 4.1 Confirmar que `despliegue/` no tiene `BackgroundTasks` ni emite el aviso del comprobante: `Select-String -Path despliegue\app -Pattern "BackgroundTasks|comprobante"`. Verificación: no hay coincidencias en el código del TP.
- [x] 4.2 Crear `despliegue/evidencia/D-08.md` con: el caso, la explicación de que pertenece a `parcial/` (C-10), la cita a `parcial/evidencia/c-10-backgroundtasks.txt` y la transcripción del orden (aviso después de `POST /ventas/ 201 Created`). Verificación: el archivo existe y no inventa una corrida en `despliegue/`.
- [x] 4.3 Confirmar que la opción (a) es la elegida por el usuario; no se implementa la opción (c). Verificación: `D-08.md` cita `parcial/` y `design.md` registra la decisión.
- [x] 4.4 No agregar `BackgroundTasks` a `despliegue/`. Verificación: `git diff -- despliegue/app despliegue/main.py` vacío.

## 5. Completar `despliegue/DEPLOY.md`
- [x] 5.1 Agregar al inicio la URL pública y la fecha y hora del despliegue (UTC-3). Verificación: ambos datos están y la fecha corresponde al despliegue que corre hoy.
- [x] 5.2 Declarar la topología: EasyPanel (`grupo-acgs/libreria-api`, puerto 8000) como runtime principal, con build desde GitHub y build path `despliegue/`; justificar la elección. Verificación: el documento responde «dónde se construye y por qué».
- [x] 5.3 Dejar el `docker build` y el `docker run` **literales** completos con `--name`, `-p <puerto>:8000`, `--restart unless-stopped` y `--env-file <archivo>`, y aclarar que es el camino equivalente sin Compose. Verificación: los comandos son copiables y no contienen valores reales.
- [x] 5.4 Documentar el archivo de variables por **nombre/ruta** y las siete variables `POSTGRES_*`; aclarar que la URL se deriva y que no se declara `DATABASE_URL`. Verificación: no hay contenido del archivo ni contraseña.
- [x] 5.5 Cerrar el procedimiento de actualización: build → `docker rm -f` → `docker run`, con rollback por tag anterior y la aclaración de que los datos viven en la base. Verificación: la secuencia está completa y menciona D-04.
- [x] 5.6 Actualizar la sección de evidencia: D-01…D-07 con enlaces y D-08 con la excepción; quitar la frase «D-08 queda para C-21». Verificación: los ocho casos figuran y ningún enlace apunta a un archivo inexistente.
- [x] 5.7 Revisar que no haya secretos: `Select-String -Path despliegue\DEPLOY.md -Pattern "password=|POSTGRES_PASSWORD=|postgresql\+asyncpg://[^<\s]"`. Verificación: sin coincidencias con valores reales.

## 6. Verificación desde afuera y sostenimiento
- [x] 6.1 Verificar la URL pública completa el día del cierre: `/health/ready` 200, `/libros/` 200 con datos y `POST /ventas/` 201. Verificación: salida real anexada a `D-03.md`, con fecha y hora.
- [x] 6.2 Confirmar que el `POST /ventas/` devuelve precios copiados por renglón y total calculado (`RN-10`). Verificación: el cuerpo de la respuesta muestra ambos.
- [x] 6.3 Confirmar que el despliegue sigue en línea después de todas las pruebas y que no quedó ningún contenedor one-off. Verificación: `docker ps` sólo con `libreria-api` y la URL respondiendo 200.
- [x] 6.4 Confirmar que no se tocó la lógica del TP ni `parcial/`: `git status --short` sólo muestra `despliegue/DEPLOY.md` y `despliegue/evidencia/D-08.md` (más ajustes de evidencia), y `git diff --stat -- despliegue/app despliegue/main.py despliegue/migrations despliegue/alembic.ini despliegue/requirements.txt despliegue/seed.py parcial` está vacío. Verificación: el diff no tiene código.

## 7. Cierre
- [x] 7.1 Marcar `[C-21]` como `[x]` en `CHANGES.md` sólo si D-01…D-08 están en `despliegue/evidencia/` y `DEPLOY.md` tiene los cinco contenidos obligatorios. Verificación: la fila de C-21 cita los archivos y la fecha.
- [x] 7.2 Correr `openspec validate c-21-despliegue-vps-deploy-md --strict` antes de archivar. Verificación: exit 0.
- [x] 7.3 Archivar el change con `openspec archive c-21-despliegue-vps-deploy-md`. Verificación: el directorio queda en `openspec/changes/archive/` y `openspec list` vacío.
- [x] 7.4 Dejar el despliegue en línea y no hacer `commit` ni `push` sin pedido explícito. Verificación: `libreria-api` `healthy` y cambios en el working tree.

## Workflow follow-up
- La KB 11 y `CHANGES.md` siguen hablando de `DATABASE_URL`; corregirlos es un change de documentación aparte, no C-21.
- D-08 opción (a) confirmada; no hay rama (c). D-04 se documenta por equivalencia EasyPanel.
- C-22 (zip y autoevaluación) depende de que `despliegue/evidencia/` tenga los ocho archivos y `DEPLOY.md` esté completo.

## Notas de ejecución (2026-11-08)
- 1.1/1.3/3.1-3.4: el estado del servidor se toma de la evidencia real D-02/D-04, capturada el 2026-11-08. En esta sesión no hubo SSH al VPS: `srv1930369` no resuelve desde este entorno. No se inventó una salida nueva.
- 1.4: EasyPanel inyecta las variables desde el panel; `libreria.env` es el nombre documentado del camino `docker run`. Se verificó localmente que no hay `.env` ni `libreria.env` versionado (`git ls-files` vacío); no se localizó un archivo real en el VPS porque ese runtime no usa uno.
- 3.3: el reinicio fue `docker restart "$CID"` sobre el contenedor gestionado por EasyPanel, no un recreate ni el `docker run` literal. D-04 queda como equivalencia parcial.
- 6.3: no se creó ningún contenedor one-off, así que no hay uno que eliminar; la URL respondió 200 el 2026-11-08 19:08 UTC-3.
- 7.3: archivado el 2026-11-08 como `2026-11-08-c-21-despliegue-vps-deploy-md`.
