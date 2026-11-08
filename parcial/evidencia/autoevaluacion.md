# Autoevaluación — rúbrica de la consigna (p. 23-24)

- **Grupo**: AURA
- **Fecha**: 2026-11-08
- **Alcance**: los 10 criterios de `docs/CHECKLIST_ENTREGA.md` §13 y las tres
  condiciones que anulan la corrección.
- **Regla aplicada**: sólo se marca `sí` cuando existe una salida real o un
  archivo de evidencia verificable. Lo que no se re-ejecutó se indica en la
  columna de evidencia y se enumera al final.

## Criterios

| # | Criterio | Peso | Evidencia (archivo o comando) | Verificado |
|---|---|---|---|---|
| 1 | Proyecto, configuración y ciclo de vida | 6 % | Corrida limpia: `alembic upgrade head` + `uvicorn main:app` + `/health/live` y `/health/ready` → 200; `Settings()` sin `.env` → 6 errores de validación; `main.py` crea motor y sessionmaker sólo en `lifespan`. Paridad 3.12/16 en el VPS: mismas migraciones y salud 200. Ver `docs/auditoria-final/c-22-clean-room.md` §2, §6 y §13. | **sí** |
| 2 | Modelos, relaciones y migraciones | 10 % | `alembic history` → 5 revisiones; `upgrade head` → `downgrade base` → `upgrade head` sin error; `alembic check` → sin diferencias; 15 tablas; 0 FKs sin índice; dinero `NUMERIC`; fechas nuevas `timestamptz`; índices únicos parciales `uq_asignacion_rol_abierta` y `uq_libro_isbn_vigente`. Ver `c-22-clean-room.md` §3. | **sí** |
| 3 | Contratos y CRUD | 8 % | `python -m pytest -q` → 472 passed, 1 skipped, 0 errors (el skip se corrió aparte y pasó); `libros.http` re-ejecutado en C-22 → 25/25 (C-01, C-13, C-16); evidencia en `parcial/test/evidencia/c22-http-libros.txt` y `c22-http-resumen.md`. | **sí** |
| 4 | Autenticación | 14 % | Suite de autenticación incluida en los 472 tests; `auth.http` re-ejecutado en C-22 → 12/12 (cookie HttpOnly, 401 uniforme, 429 + `Retry-After: 59957`, logout `Max-Age=0`); evidencia en `c22-http-auth.txt`. | **sí** |
| 5 | Autorización | 12 % | Suite de roles/RBAC incluida en los 472 tests; `roles.http` re-ejecutado en C-22 → 28/28 (roles releídos de base, revocación, vencimiento real 1 min + 62 s, `/mis-ventas`); evidencia en `c22-http-roles.txt`. | **sí** |
| 6 | Repositorios y Unit of Work | 16 % | `commit()` en `repository.py` → 0; `UnitOfWork(...)` en `service.py` → 0; 7 `unit_of_work.py` de módulo; UoW confirmado por la suite (`test_session_sharing`, `test_registro_unit_of_work`, `test_ventas_service`). Única excepción declarada: `intento_acceso` con sesión propia (DD-05). | **sí** |
| 7 | Integridad | 10 % | `trg_movimiento_stock_no_modificable` presente; `c22-http-c14-solo-agregado.txt` re-ejecutado en C-22: dos `ERROR` de UPDATE/DELETE y 15 filas intactas; invariante `libro.stock = SUM(movimiento_stock.cantidad)` → 0 violaciones; 409 de venta sin escrituras cubierto por C-11.1 y la suite. | **sí** |
| 8 | Lecturas sin N+1 y asincronía | 6 % | `parcial/evidencia/c-15_consultas_2y4.txt` → 6 SELECT con 2 renglones y 6 SELECT con 4 renglones (evidencia archivada, no re-ejecutada); `c22-http-backgroundtasks.txt` → el aviso aparece después del 201 en la corrida de C-22; los handlers de ruta son `async def`. | **sí** |
| 9 | Contenedor: la imagen | 11 % | `despliegue/evidencia/D-01.md` (base `python:3.12-alpine`, 74.8 MB), `D-02.md`, `D-05.md`, `D-06.md` (sin variables de BD ni `.env` en la imagen), `D-07.md`. Evidencia revisada; no re-ejecutada por ausencia de Docker local. | **sí** |
| 10 | Despliegue en el VPS | 7 % | `GET https://libreria.enzogiaquinta.me/health/live` → 200; `/health/ready` → 200; `/libros/` → 200 con datos; `despliegue/DEPLOY.md` con URL, fecha/hora y comandos; `D-03.md`, `D-04.md`, `D-08.md`. Paridad 3.12/16 ejecutada en el VPS con contenedores temporales (`python:3.12-alpine` + `postgres:16-alpine`): 5 migraciones, seed, 472 passed/1 skipped y salud 200; ver `c-22-clean-room.md` §13. | **sí** |

## Condiciones que anulan la corrección

| Condición | Comprobación | Resultado |
|---|---|---|
| El proyecto levanta | Base limpia `parcial_c22_clean`; `alembic upgrade head`; `uvicorn main:app` en el puerto 8123; `/health/live` y `/health/ready` → **200**; proceso detenido al terminar. | **no se cumple la condición de anulación** (el proyecto levanta) |
| El esquema sale de `alembic upgrade head` sobre base vacía | Base creada vacía (`\dt` sin relaciones); 5 revisiones aplicadas; `alembic current` = `5229054e2bcc (head)`; `downgrade base` y nuevo `upgrade head` sin error; sin `create_all` en el código. | **no se cumple la condición de anulación** (el esquema nace de Alembic) |
| No hay credenciales reales en el repositorio, la imagen ni el zip | Repositorio: `git grep` e historial sin credenciales reales (sólo placeholders `cambiar_por_...` y ejemplos `usuario:clave`). Imagen: `D-06.md` muestra «sin variables de BD en la imagen» y «sin .env en /app». Zip: **no existe todavía**, por lo que no se puede auditar. | **repo: sí; imagen: sí (evidencia D-06, no re-ejecutada); zip: no verificado en esta fase** |

## Lo que no se re-ejecutó

- El checklist de 136 ítems no se ejecutó comando por comando: §0–§10 se
  recorrieron por sección (C-22 §12) y §11–§13 se reutilizan de C-20/C-21/C-22.
- La GUI de VS Code REST Client no se abrió: los `.http` se corrieron con
  `httpyac` 6.16.7, un runner HTTP real, sobre copias de compatibilidad
  documentadas en `c22-http-resumen.md`.
- El conteo de SELECT de C-15 y la comparación de tiempos de C-04 se
  reutilizan de la evidencia de C-18/C-19; no se repitieron en C-22.
- La imagen Docker (`D-01`, `D-02`, `D-05`, `D-06`, `D-07`): se revisó la
  evidencia del despliegue, no se reconstruyó la imagen. La paridad 3.12/16
  del VPS no sustituye esa reconstrucción.
- El `.zip` final: no se generó en esta fase; su nombre, exclusiones y SHA-256
  se verifican cuando el usuario autorice el cierre.

No se incluyen tokens, contraseñas, contenido de `.env` ni rutas absolutas de la
máquina en este documento.
