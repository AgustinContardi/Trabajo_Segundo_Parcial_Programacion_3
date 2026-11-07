# Proposal — C-16 fix: venta transaccional, hardening y evidencia

## Why

`C-16` ya está archivado y comprometido (`f2b6b89`), pero una auditoría encontró defectos de contrato y de evidencia: IDs fuera del rango `BIGINT` producen un `DataError` de asyncpg y terminan en **500** (violación de `RN-15`); el archivo archivado tiene **0/25** tareas marcadas y no existe `parcial/test/ventas.http`, por lo que `openspec validate --archived --strict` falla; los fixtures de prueba crean `Libro(stock=...)` sin movimiento inicial y rompen el invariante global de `RN-11`; y varios tests de servicio usan `pytest.raises(Exception)` sin verificar el `409` ni la ausencia de escrituras.

No corresponde reabrir `C-16`: reescribir un change archivado destruiría su registro histórico y el commit que lo cerró. Este change correctivo depende de `C-16`, conserva su flujo transaccional y agrega el hardening y la evidencia faltantes. `C-16` sigue marcado `[x]` en `CHANGES.md`; este change es su seguimiento, no su reemplazo.

## What Changes

- **Contrato de entrada estricto** en `VentaCreate`/`RenglonCreate`: IDs enteros positivos y acotados a `BIGINT`; `cantidad` entera positiva y acotada a la capacidad de la columna (`integer`), con `strict=True` para rechazar booleanos, strings y floats coercionados. Toda entrada fuera de rango → **422** con mensaje propio en español, nunca **500**.
- **Traducción de errores de datos en el borde de la aplicación**: `DBAPIError` cuyo `orig` sea un `DataError` de asyncpg (y `DataError` de SQLAlchemy) → **422** genérico en español, sin texto de PostgreSQL. `IntegrityError` conserva su traducción actual a 409/422 y se evalúa primero.
- **Orden de validación coherente** en `POST /ventas`: 401 → 403 → 409 (cliente/libros inexistentes o dados de baja) → 409 (stock agregado insuficiente) → 422 (libro repetido/contrato). El chequeo de duplicados deja de ejecutarse antes de los 409.
- **Ruta sin redirección**: `POST /ventas` y `POST /ventas/` responden igual; se elimina el **307** por barra final.
- **Evidencia de pruebas reparada**: los fixtures siembran stock por el punto único (`movimiento_stock` inicial), se afirma el invariante global `libro.stock = SUM(movimiento_stock.cantidad)`, se comprueba que 409/422 no escriben ni cambian stock, se reemplaza `pytest.raises(Exception)` por `HTTPException(409)` y se eliminan los `finally: pass`. La suite debe ser determinista en dos corridas consecutivas contra PostgreSQL 17.
- **Evidencia manual nueva**: `parcial/test/ventas.http` con C-10, C-11, C-12 y el ítem de `BackgroundTasks`, con status, cuerpo esperado y consultas de control.
- **Documentación reconciliada**: se corrigen los conteos de evidencia de `C-16` (325 tests actuales vs 264 del padre, **+61**, no 21) y la inconsistencia 404/409; se actualizan los specs principales `venta-transaccional` y `ventas`. Las tareas archivadas de `C-16` sólo se marcan si la nueva evidencia las satisface de verdad, dejando trazabilidad hacia este change; no se reescribe el commit ni se simula historial.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `venta-transaccional`: se endurece el contrato de entrada (enteros estrictos y acotados), se fija el orden 401 → 403 → 409 → 422, se agrega la traducción de errores de datos sin filtrar PostgreSQL y se elimina la redirección por barra final.
- `ventas`: se documenta que el módulo expone `POST /ventas` como operación de escritura delegada en `venta-transaccional`, eliminando la contradicción de un spec de sólo lecturas.

## Impact

- `parcial/app/modules/ventas/schemas.py`, `service.py`, `router.py`.
- `parcial/app/core/errors.py` y `parcial/main.py` (handler de errores de datos).
- `parcial/tests/conftest.py`, `test_ventas_schemas.py`, `test_ventas_service.py`, `test_ventas_api.py`, `test_ventas_crear_*.py`.
- `parcial/test/ventas.http` (nuevo).
- `openspec/specs/venta-transaccional/spec.md`, `openspec/specs/ventas/spec.md`, artefactos archivados de `C-16` y conteos de `CHANGES.md`.
- Sin migraciones ni cambios de esquema. No toca `despliegue/`, `C-17` ni posteriores, ni el change activo `c-12-auto-registro-atomico`.

## Non-Goals

- No rediseñar la transacción ni cambiar sus cuatro escrituras (`RN-10`).
- No agregar bloqueo de fila ni actualización condicional atómica de stock: `RN-10` acepta explícitamente que la concurrencia no se evalúa. Queda como hardening futuro documentado.
- No crear migraciones, columnas, constraints ni triggers.
- No agregar ni modificar endpoints de `C-17`/`C-18`/`C-19`/`C-20`/`C-21`/`C-22`.
- No tocar `despliegue/`.
- No hay UI: `Decision: no (no UI)`.
- No hacer `commit` ni `push`; los cambios quedan en el working tree.

## Acceptance Criteria

1. `POST /ventas` con `cliente_id`/`libro_id` en `10**30`, `cantidad` fuera de rango, `cantidad: true`, `"1"` o `1.5` devuelve **422** en español, nunca **500**, y no escribe filas.
2. Un `DataError`/`DBAPIError` de datos se traduce en el borde a **422** sin nombres de tablas, columnas, constraints ni trazas de PostgreSQL; un `IntegrityError` sigue traduciéndose a 409/422.
3. Un cuerpo con libro repetido y un cliente/libro inexistente devuelve **409**, no 422; el orden 401 → 403 → 409 → 422 se verifica con tests.
4. `POST /ventas` y `POST /ventas/` responden con el mismo status y cuerpo, sin **307**.
5. Los tests siembran stock con `LibroRepository.aplicar_movimiento(..., motivo="Stock inicial")`; la query global del invariante devuelve **0 filas** en una base recién migrada y los libros usados por cada test quedan consistentes.
6. Todo 409/422 de la suite deja `venta`, `renglon_venta`, `movimiento_stock` y `libro.stock` sin cambios; los tests de servicio afirman `HTTPException` con `status_code == 409` (no `Exception` genérica).
7. `parcial/test/ventas.http` existe con C-10, C-11, C-12 y `BackgroundTasks`, cada caso con status, cuerpo esperado y consultas de control; la ejecución manual con REST Client se registra como evidencia externa si el entorno headless no puede correrla.
8. `pytest -q` pasa dos veces consecutivas contra PostgreSQL 17 con el mismo resultado; `alembic check` sigue limpio y no aparece ninguna migración nueva.
9. `openspec validate "c-16-fix-venta-transaccional" --strict` pasa; la documentación de `C-16` refleja los conteos reales (264 → 325, +61) y el `409` de cliente/libro inexistente, sin reescribir el commit.
10. `openspec validate --archived --strict` de `C-16` deja de fallar una vez que la evidencia nueva satisface sus tareas, o queda documentado exactamente qué tarea no se puede satisfacer y por qué.
