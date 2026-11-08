# Proposal
## Why
El criterio «Despliegue en el VPS» (7 % de la rúbrica) se corrige sobre un sistema en línea: `https://libreria.enzogiaquinta.me` ya responde `/health/ready`, `/libros/` y `POST /ventas/` 201, y D-01…D-07 tienen salida real en `despliegue/evidencia/`. Falta lo que la consigna pide **sobre ese despliegue**: `DEPLOY.md` no declara URL pública ni día y hora, no documenta el procedimiento de actualización ni el `docker run` literal con `--restart unless-stopped`, y D-08 no existe. Sin eso, el despliegue funciona pero el criterio no se puede verificar.

## What Changes
- **Completar** `despliegue/DEPLOY.md` con lo obligatorio de la consigna: URL pública, día y hora (UTC-3), elección y justificación de dónde se construye la imagen (EasyPanel desde GitHub, build path `despliegue/`), `docker build` y `docker run` completos —con el **nombre** del archivo de variables y **sin su contenido**—, cambios al TP y procedimiento de actualización (build → `docker rm -f` → `docker run`, datos en la base del servidor).
- **Documentar la topología real**: EasyPanel es el runtime principal (contenedor `libreria-api`, puerto 8000). `DEPLOY.md` conserva además el `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file <archivo> libreria` literal, sin Docker Compose, como camino equivalente y reproducible.
- **Ejecutar una vez el `docker run` literal** en un puerto alternativo (`8002`) con el contenedor one-off `libreria-c21` y el mismo archivo de variables fuera del repo: demuestra D-02 y D-04 sin tocar el despliegue principal. Luego se elimina el contenedor one-off y EasyPanel sigue en 8000.
- **D-04**: `docker rm -f` + el mismo `docker run` → vuelve `healthy`, los datos siguen y `alembic_version` no cambia (las migraciones no se repiten). Si el entorno no permite el one-off, queda documentado el equivalente de EasyPanel (restart/recreate) con su diferencia explícita.
- **D-08**: crear `despliegue/evidencia/D-08.md` que cite la captura de `parcial/evidencia/c-10-backgroundtasks.txt` y explique que el aviso del comprobante pertenece a `parcial/` (C-10) y no al TP cap. 1–4, que no tiene `BackgroundTasks`. No se agrega lógica nueva a `despliegue/`.
- **Revisar y, si hace falta, corregir** D-01…D-07 para que cada archivo tenga comando y salida real y coincida con el contenedor que corre hoy.
- **Verificar desde afuera** la URL pública: `/health/ready` 200, `/libros/` 200 con datos y `POST /ventas/` 201 con precios copiados y total (`RN-10`), registrando la verificación en D-03.
- **Sostener el despliegue en línea** hasta que se publiquen las notas y marcar `[C-21]` en `CHANGES.md` al archivar.

## Non-Goals
- No se modifica la lógica de `despliegue/` (`main.py`, `app/`, `migrations/`, `alembic.ini`, `requirements.txt`, `seed.py`) ni se agregan `BackgroundTasks`: el TP cap. 1–4 se entrega tal como se entregó.
- No se toca `parcial/` ni se reutiliza esta imagen para el parcial (`DD-15`).
- No se usa Docker Compose, ni CI, ni un Postgres dentro del contenedor.
- No se reescribe la KB ni los textos de `CHANGES.md` sobre `DATABASE_URL`: C-21 documenta el contrato real (`POSTGRES_*`) sin cambiar el código.
- No se hace `commit` ni `push`.

## Capabilities
### New Capabilities
- `despliegue-vps`: comportamiento exigible al despliegue del TP cap. 1–4 en el VPS —URL pública viva, imagen construida y ejecutada sin Compose con `--env-file` fuera del repo, archivo de variables que no usa `localhost`/`127.0.0.1`, datos iniciales cargados dentro del contenedor, persistencia y actualización sin pérdida de datos, `DEPLOY.md` completo y evidencia D-01…D-08 (con la excepción documentada de D-08)—.

### Modified Capabilities
- Ninguna. `imagen-contenedor` ya cubre la imagen y D-01/D-06/D-07; C-21 no cambia sus requisitos, sólo los usa.

## Impact
- **Archivos modificados**: `despliegue/DEPLOY.md` (URL, fecha/hora, build/run, actualización, topología EasyPanel), `despliegue/evidencia/D-01…D-07.md` (revisión y ajuste si la salida no coincide), `CHANGES.md` (estado de C-21 al archivar).
- **Archivo nuevo**: `despliegue/evidencia/D-08.md` (excepción documentada con la captura de `parcial/`).
- **Sin impacto en código**: no se toca `despliegue/app/`, `main.py`, `migrations/`, `seed.py`, `parcial/`, migraciones ni tests.
- **Dependencias externas**: VPS accesible por SSH, Docker en el VPS, fácil acceso a EasyPanel, PostgreSQL 16 del proyecto y el archivo de variables real fuera del repo. Si el VPS no estuviera accesible, sólo suman `DEPLOY.md` y la evidencia ya existente.
- **Riesgos de corrección**: el `docker run` one-off comparte la misma base que el despliegue principal; se ejecuta en 8002, sin `--restart`, y se elimina al terminar. Un error en el env-file no afecta a `libreria-api`.
