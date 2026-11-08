# Auditoría final — C-17 seed-libreria

- **Fecha:** 2026-11-08
- **Auditor:** subagente auditor (solo lectura)
- **Objeto:** `parcial/seed.py` + change archivado `openspec/changes/archive/2026-11-08-c-17-seed-libreria/`
- **Criterio:** `docs/CHECKLIST_ENTREGA.md` §8 «Datos iniciales (seed.py)» + §4 (invariante) + §1 (seed ejecutable) + reglas duras del repo
- **Alcance:** lectura de código, specs y evidencia; `SELECT` de solo lectura contra PostgreSQL 17 (`127.0.0.1:5432`, db `libreria`). **No** se re-ejecutó `seed.py`, no se corrieron tests, no se escribió en la DB.

## Veredicto global: **PASS**

El estado sembrado en la DB coincide exactamente con lo declarado en `seed.py`, la spec `datos-iniciales` y la evidencia archivada. Idempotencia e ids estables verificables por construcción del código (`TRUNCATE … RESTART IDENTITY CASCADE`) y por la evidencia registrada de dos corridas; no re-ejecutada en esta auditoría (prohibido: otros auditores comparten la DB). Único WARN: defecto conocido `dd4a0e5e9cf7` (defaults timestamptz congelados), preexistente y fuera del alcance de C-17.

## Tabla de ítems

| Ítem (checklist / consigna) | Veredicto | Evidencia |
|---|---|---|
| §8.1: vacía las tablas antes de cargar | PASS | `parcial/seed.py:275-290` (`TABLAS_DOMINIO`, 14 tablas, sin `alembic_version`), `:346-364` (`TRUNCATE TABLE … RESTART IDENTITY CASCADE`, sin `DELETE`); `main()` lo ejecuta antes de `cargar` (`:639-641`) |
| §8.1: 5 usuarios con roles (2 ADMIN, 1 VENDEDOR, 1 CLIENTE, 1 VENDEDOR con `debe_cambiar_password=true`) | PASS | `seed.py:105-136`; DB: `admin|ADMIN`, `admin2|ADMIN`, `vendedor|VENDEDOR`, `ana|CLIENTE`, `nuevo|VENDEDOR|debe_cambiar_password=t`; 5 filas en `usuario` y `asignacion_rol`, todas `activo=t`, `revocada_en`/`vence_en` nulos |
| §8.1: 3 editoriales, 3 géneros, 6 autores | PASS | `seed.py:139-160`; DB: `editorial=3`, `genero=3`, `autor=6` |
| §8.1: 5 libros con stock 10/5/8/3/1 | PASS | `seed.py:165-206`; DB: Rayuela 10, Antología 5, Ficciones 8, Respiración artificial 3, Bestiario 1 (`borrado_en` nulo); precios 25000.00/30000.00/22000.00/27000.00/18000.00 (`NUMERIC`) |
| §8.2: clientes Lucía (con perfil, sin usuario), Tomás (sin usuario), Ana (con `usuario_id`) | PASS | `seed.py:241-260`; DB: Lucía `usuario_id` NULL + 1 fila en `perfil_cliente` (`cliente_id=1`, tel 111, dir Calle 1); Tomás NULL; Ana `usuario_id=4` (= `ana@example.com`) |
| §8.3: venta 1 (1 Rayuela + 2 Ficciones, total 69000.00) | PASS | `seed.py:264-267, 328-333, 506-528`; DB: `venta` id 1, `total=69000.00`; renglones `(1,1,25000.00)` y `(1,3,2,22000.00)`; 25000×1 + 22000×2 = 69000.00 ✓ (precio copiado del catálogo, nunca hardcodeado) |
| §8.3: un «Stock inicial» por libro (+11/+5/+10/+3/+1) | PASS | `seed.py:473-479`; DB `movimiento_stock`: `+11, +5, +10, +3, +1` motivo «Stock inicial», `usuario_id=1` (admin), `venta_id` nulo |
| §8.3: salidas −1/−2 de la venta | PASS | `seed.py:522-528`; DB: `(libro 1, -1)` y `(libro 3, -2)`, motivo «Venta», `usuario_id=3` (vendedor), `venta_id=1` — 7 movimientos totales |
| §8.3: línea `evento_seguridad` actor SISTEMA | PASS | `seed.py:269, 531`; DB: 1 fila `SISTEMA | Carga de los datos iniciales` |
| §8.4: idempotente (dos corridas → mismo estado e ids) | PASS | Por código: `TRUNCATE … RESTART IDENTITY` (`seed.py:346-353`) + orden determinista de carga + verificación interna de conteos y `venta.id=1` (`:534-577`); por evidencia: `evidencia.md` (corridas 1 y 2 exit 0, salida idéntica) y `tasks.md` 4.4/4.5 `[x]`. **No re-ejecutado en esta auditoría** (regla: DB compartida) |
| §1: `seed.py` en raíz de `parcial/`, sin `create_all` | PASS | Archivo en `parcial/seed.py`; `grep create_all parcial/seed.py` → 0 coincidencias; el esquema lo crea solo Alembic |
| §4: invariante `stock = SUM(movimiento_stock.cantidad)` → 0 filas | PASS | Query del checklist ejecutada contra la DB actual: **0 filas**; el propio seed la re-verifica (`seed.py:308-313, 547-552`) |
| RN-11/RN-12: stock nunca asignado directo | PASS | `seed.py:453-479`: `Libro(stock=0)` + `aplicar_movimiento`; `app/modules/libros/repository.py:79-88` (`libro.stock += cantidad` + `MovimientoStock` + flush); sin `DELETE` sobre `movimiento_stock` (TRUNCATE no dispara el trigger de `0004`) |
| RN-08: bcrypt fuera del event loop y de la transacción | PASS | `seed.py:583-599`: `hash_password` con `Semaphore(BCRYPT_MAX_CONCURRENCY)` **antes** del `async with`; `app/core/security.py:43` usa `asyncio.to_thread`; DB: los 5 `password_hash` comienzan con `$2b$` |
| CV-09: contraseñas ficticias solo en el seed, nunca impresas | PASS | `seed.py:94-100` (docstring + `PASSWORDS`); impresión solo host/puerto/db (`:632-635`); contraseñas ≤72 bytes |
| CV-01/CV-02: UoW construido por el script, sin `commit()` en repositorios | PASS | `SeedUnitOfWork` abierto con `async with` una sola vez (`:639-641`); `grep "commit()" parcial/seed.py` → única mención en docstring (negando su uso) |
| Fix de C-01: importa `app.modules.usuarios.models` para resolver `Usuario` | PASS | `seed.py:73, 89` |
| Decimal y timestamptz | PASS | `total`/`precio` son `NUMERIC` en DB; `venta.fecha` es `timestamp with time zone`; `seed.py` usa `Decimal` (nunca `float`) |
| Estado sembrado actual = declarado | PASS | Conteos DB: usuario 5, asignacion_rol 5, editorial 3, genero 3, autor 6, libro 5, libro_autor 7, cliente 3, perfil_cliente 1, venta 1, renglon_venta 2, movimiento_stock 7, evento_seguridad 1; `alembic_version` intacto (1 fila, `c8d2dea5529f` = head); ids estables (usuarios 1-5, libros 1-5, clientes 1-3, venta 1) |
| Defecto conocido `dd4a0e5e9cf7` (defaults timestamptz congelados con `now()`) | WARN | `migrations/versions/dd4a0e5e9cf7_acceso_y_stock.py:40,47,68,87` usan `server_default='now()'` (congela el timestamp de la transacción). Preexistente y fuera del alcance de C-17; el seed no escribe esas columnas por default. No constituye FAIL nuevo |

## Hallazgos

1. **[WARN] Defecto conocido `dd4a0e5e9cf7`** — defaults `server_default='now()'` en `evento_seguridad.cuando`, `intento_acceso.cuando`, `asignacion_rol.desde` y `movimiento_stock.cuando`. Congela el timestamp de la transacción. Registrado como defecto conocido: no es regresión de C-17 y no se convierte en FAIL.
2. **[INFO] `intento_acceso` con 15 filas en la DB actual** — el seed **sí** trunca `intento_acceso` (`TABLAS_DOMINIO`, `seed.py:278`) y no la carga (design: «el seed deja esa tabla vacía para que C-05 cuente desde cero»). Las 15 filas provienen de actividad de otros tests/auditores posterior al último seed; el estado sembrado declarado no incluye conteos de esta tabla. No es defecto del seed.
3. **[INFO] `libro_autor` tiene 7 filas** (1 Rayuela, 3 Antología, 1 Ficciones, 1 Respiración, 1 Bestiario), consistente con `AUTORIAS` (`seed.py:209-237`); la spec exige «al menos una autoría por libro» y se cumple.
4. **[INFO] `venta.fecha` heredada con `server_default='now()'`** (migración `0001`, fuera de C-17): el seed no setea `fecha`, así que toma el default de la transacción. `timestamptz` correcto; el valor observado (`2026-11-08 … -03`) no afecta la corrección.

## No verificado independientemente (limitaciones)

- **No re-ejecuté `python seed.py`** (regla de auditoría: reescribiría la DB compartida por otros auditores). La idempotencia y el exit code 0 se acreditan por lectura del código (`vaciar` + verificación interna) y por la evidencia registrada (`evidencia.md`: dos corridas exit 0, salida idéntica; `tasks.md` 4.4/4.5 `[x]`).
- **No corrí `python -m pytest`** (misma DB). La suite 459 passed/1 skipped de la evidencia no fue re-verificada; `tests/test_seed_datos.py` y `tests/test_seed_ejecucion.py` existen y su contenido de contrato fue contrastado contra `seed.py` por lectura.
- **Login real con las contraseñas ficticias** (spec «Login con las credenciales del seed»): los hashes en DB son `$2b$` (bcrypt) y `hash_password` es la función compartida de la app; la verificación 200 del login es alcance de C-18.
