# Tasks — C-16 fix: venta transaccional, hardening y evidencia

## 1. Contrato de entrada estricto (`RN-09`, `RN-15`, `CHECKLIST §8`)

- [x] 1.1 **RED** — Ampliar `parcial/tests/test_ventas_schemas.py` con casos que hoy fallan: `cliente_id`/`libro_id` en `10**30` y en `9223372036854775808` dan `ValidationError`; `cantidad` en `2**31` da `ValidationError`; `cantidad: true`, `"1"` y `1.5` dan `ValidationError`; `0` y negativos siguen rechazados. Verificar con `python -m pytest tests/test_ventas_schemas.py -q` que falla por la razón correcta. **Rastrea:** RN-09, RN-15.
- [x] 1.2 **GREEN** — En `parcial/app/modules/ventas/schemas.py`, tipar `cliente_id`, `libro_id` y `cantidad` con `Annotated[int, Field(strict=True, ge=1, le=...)]` y las cotas `BIGINT_MAX`/`INT_MAX` del design; conservar `extra="forbid"` y `min_length=1`. Verificar `python -m pytest tests/test_ventas_schemas.py -q` en verde. **Rastrea:** RN-09, RN-15.
- [x] 1.3 **API** — Agregar a `parcial/tests/test_ventas_api.py` los casos HTTP de ID fuera de rango, `cantidad` booleana, string/float y cantidad fuera de rango: `422`, sin `500`, sin filas nuevas y con mensaje en español. Verificar con `python -m pytest tests/test_ventas_api.py -q -k "rango o booleana o tipo"`. **Rastrea:** RN-15, CHECKLIST §8.

## 2. Borde de errores de datos (`RN-15`)

- [x] 2.1 **RED** — Escribir en `parcial/tests/` un test que provoque `DBAPIError` con `orig` de asyncpg `DataError` (por ejemplo, un ID fuera de rango que llegue a la consulta) y afirme `422`, mensaje propio en español y ausencia de texto de PostgreSQL. Verificar que falla hoy con `500`. **Rastrea:** RN-15.
- [x] 2.2 **GREEN** — En `parcial/app/core/errors.py`, agregar `traducir_error_de_datos(exc)` y el handler de `DBAPIError`; registrarlo en `parcial/main.py`. El handler devuelve `422` para `DataError`/`orig DataError` y `500` genérico sin texto para el resto. Verificar el test de 2.1 en verde y que `traducir_integrity_error` sigue devolviendo 409/422 para FK/CHECK. **Rastrea:** RN-15.
- [x] 2.3 **Integración** — En `parcial/app/modules/ventas/service.py`, ampliar el `except` exterior a `(IntegrityError, DBAPIError)` con prioridad para `IntegrityError` y re-lanzar los `DBAPIError` que no sean de datos; confirmar que el `except` sigue fuera del `async with` y que el rollback ocurre antes de traducir. Verificar con `python -m pytest tests/test_ventas_service.py tests/test_ventas_crear_service.py -q`. **Rastrea:** RN-10, RN-15, CV-02.

## 3. Orden 401 → 403 → 409 → 422 y ruta sin 307 (`CV-08`, `RN-09`)

- [x] 3.1 **RED** — Agregar tests de servicio/API para: duplicado de `libro_id` con cliente inexistente → `409` (hoy `422`); duplicado con libro inexistente → `409`; duplicado con stock agregado insuficiente → `409`; duplicado válido → `422`; y `POST /ventas` sin barra final → mismo status/cuerpo que con barra, sin `307`. Verificar que fallan. **Rastrea:** CV-08, RN-09.
- [x] 3.2 **GREEN** — Mover la detección de duplicados dentro del `async with`, después de cliente/libros/baja y del stock agregado por `libro_id`; devolver `422` sólo después de los 409. En `parcial/app/modules/ventas/router.py`, apilar `@router.post("", include_in_schema=False)` y `@router.post("/")` sobre el mismo handler. Verificar los tests de 3.1 en verde. **Rastrea:** CV-08, RN-09, RN-10.
- [x] 3.3 **Mensajes 422** — Actualizar `manejador_request_validation_error` en `parcial/app/core/errors.py` para conservar `loc`/`type` y devolver `msg` en español según el tipo de error. Verificar con un test que `extra_forbidden`, `int_parsing`, `bool_type` y `greater_than` devuelven mensaje en español y que ningún `msg` contiene texto de PostgreSQL. **Rastrea:** RN-15, RD-03.

## 4. Evidencia de tests: stock inicial e invariante global (`RN-11`, `CHECKLIST §4`, `§7`, `§10`)

- [x] 4.1 **Fixtures** — En `parcial/tests/conftest.py`, crear el helper/fixture `libro_con_stock_inicial(...)` que cree el libro con `stock=0` y aplique `LibroRepository.aplicar_movimiento(libro, stock_inicial, "Stock inicial", usuario_id)`; hacer que `catalogo_factory.libro(stock>0)` use ese camino. Verificar que un test que crea un libro con stock deja `stock == SUM(movimiento_stock.cantidad)`. **Rastrea:** RN-11, CHECKLIST §4.
- [x] 4.2 **Escenarios** — Migrar los fixtures de `test_ventas_api.py` y `test_ventas_crear_service.py` para que no construyan `Libro(stock=N)` directo; usar el helper de 4.1. Verificar que la consulta global del invariante devuelve 0 filas para los libros creados por los tests. **Rastrea:** RN-11, CHECKLIST §7.
- [x] 4.3 **Aserciones 409/422** — Reemplazar `pytest.raises(Exception)` por `pytest.raises(HTTPException)` con `status_code == 409` (o 422 donde corresponda) y afirmar que `venta`, `renglon_venta`, `movimiento_stock` y `libro.stock` no cambian. Eliminar los `try/finally: pass` de `test_ventas_crear_service.py` y documentar el aislamiento por datos únicos. Verificar con `python -m pytest tests/test_ventas_crear_service.py -q`. **Rastrea:** RN-10, CHECKLIST §7, §8.
- [x] 4.4 **Base local** — Ejecutar la consulta global del invariante contra PostgreSQL 17; si hay violaciones históricas de la suite anterior, repararlas una vez con movimientos compensatorios de "Stock inicial" o reconstruir la base de prueba, sin `UPDATE`/`DELETE` sobre `movimiento_stock`. Verificar que la consulta devuelve 0 filas y registrar la salida. **Rastrea:** RN-11, RN-12, CHECKLIST §4.

## 5. Evidencia manual `parcial/test/ventas.http` (`CHECKLIST §8`, `§10`)

- [x] 5.1 Crear `parcial/test/ventas.http` con C-10 (alta válida de dos renglones, `201`, precios copiados, total, stock, movimientos y aviso de `BackgroundTasks`), C-11 (Rayuela 1 + Bestiario 2 → `409` sin escrituras e invariante 0 filas), C-12 (cliente/libro inexistente y libro dado de baja → `409`) y las consultas SQL de control; cada caso con status y cuerpo esperado en un comentario. Verificar que el archivo existe y que cada caso cita su `RN`. **Rastrea:** CHECKLIST §8, §10.
- [x] 5.2 Ejecutar el `.http` contra `uvicorn main:app` con PostgreSQL real y registrar códigos, cuerpos y consultas como evidencia; si el entorno headless no permite REST Client, registrar la ejecución manual como externa y dejar constancia de que los tests de integración cubren el mismo comportamiento. Verificar que la evidencia incluye el log del aviso después de la respuesta. **Rastrea:** CHECKLIST §10.

## 6. Reconciliación documental (`C-16`, `CHANGES.md`, specs principales)

- [x] 6.1 Actualizar `openspec/specs/venta-transaccional/spec.md` con el delta de este change: contrato estricto, orden 401 → 403 → 409 → 422, traducción de errores de datos y rutas sin 307; corregir el título del requisito de orden y aclarar que el 404 es sólo de lecturas. Verificar con `openspec validate venta-transaccional --type spec --strict`. **Rastrea:** RN-15, CV-08.
- [x] 6.2 Actualizar `openspec/specs/ventas/spec.md`: agregar `POST /ventas` al alcance y ajustar el `Purpose` para que no describa el módulo como sólo lecturas, sin duplicar el contrato transaccional. Verificar con `openspec validate ventas --type spec --json` (sin `--strict`: ese spec principal ya tiene warnings de longitud ajenos a este change). **Rastrea:** RN-09.
- [x] 6.3 Corregir `CHANGES.md` de `C-16`: evidencia real 325 tests vs 264 del padre (+61, no 21) y cliente/libro inexistente → `409`; mantener `[x]` y no reescribir el commit `f2b6b89`. Verificar con `Select-String -Path CHANGES.md -Pattern "325|264|409"`. **Rastrea:** CHECKLIST §10.
- [x] 6.4 Reconciliar `openspec/changes/archive/2026-11-07-c-16-venta-transaccional/tasks.md`: agregar al inicio la nota de evidencia completada por este change y marcar sólo las tareas que la nueva evidencia satisface de verdad; dejar `[ ]` y explicar las que no. Verificar con `openspec validate --archived --strict` y documentar el resultado. **Rastrea:** CHECKLIST §10.

## 7. Verificación de integración y cierre

- [x] 7.1 Correr `python -m pytest -q` dos veces consecutivas con `PYTHONPATH=parcial` y PostgreSQL 17; ambas corridas deben dar el mismo resultado, sin fallos ni tests nuevos saltados. Verificar que el invariante global sigue en 0 filas después de cada corrida. **Rastrea:** CHECKLIST §10.
- [x] 7.2 Correr `alembic check` desde `parcial/` y `git status --short parcial/migrations`; no debe haber migraciones nuevas ni diferencias de esquema. **Rastrea:** CV-10, CHECKLIST §3.
- [x] 7.3 Revisar reglas duras con `grep`: sin `commit()` en repositorios, sin `AsyncSession`/`UnitOfWork(` en `service.py`, sin `selectinload` fuera de `repository.py`, y sin `raise HTTPException(500)` por entrada inválida. Verificar que los comandos no devuelven ocurrencias. **Rastrea:** CV-01, CV-02, CV-03, RN-15.
- [x] 7.4 Ejecutar `openspec status --change "c-16-fix-venta-transaccional" --json` y `openspec validate "c-16-fix-venta-transaccional" --strict --json`; ambos deben pasar. **Rastrea:** proceso OpenSpec.

## Workflow follow-up

- Archivar este change cuando la revisión del proyecto lo apruebe.
- Confirmar que `C-16` sigue `[x]` en `CHANGES.md` y que la nota de evidencia apunta a este change.
- No hacer `commit` ni `push` sin pedido explícito.
