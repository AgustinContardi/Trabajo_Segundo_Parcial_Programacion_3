# Auditoría — C-08 «capas-libros-alta-stock-inicial»

- **Fecha**: 2026-11-08
- **Auditor**: subagente (solo lectura — sin INSERT/UPDATE/DELETE, sin pytest, sin seed, sin uvicorn)
- **Change**: `C-08 capas-libros-alta-stock-inicial` (archivado `openspec/changes/archive/2026-11-06-c-08-capas-libros-alta-stock-inicial/`)
- **Criterio**: `docs/CHECKLIST_ENTREGA.md` §7 (capas) y §8 (alta con `stock_inicial` + invariante), contra `CHANGES.md` §[C-08] y la spec delta archivada
- **Veredicto**: **PASS** (12/12 ítems verificados; 2 WARN, 0 FAIL)

## Método

- Inspección de `parcial/app/modules/libros/{models,schemas,repository,unit_of_work,service,router}.py`, `app/core/{repository,unit_of_work,errors}.py` y `parcial/main.py`.
- Greps de capa exigidos por §0/§7 (todos vacíos donde deben estarlo).
- Evidencia registrada: `parcial/test/EVIDENCIA.md` (bloques C-13.1/C-13.2, C-16.1–C-16.8), `parcial/tests/test_stock_invariante.py`, `tests/conftest.py` (factory `libro_con_stock_inicial`).
- Base real (SELECT-only): invariante global y contenido de `movimiento_stock`.
- La verificación de escritura (`POST /libros`) **no se ejecutó** (prohibido por reglas de auditoría); se valida por inspección + evidencia registrada.

## Tabla por ítem (§7 y §8 aplicables a C-08)

| # | Ítem del checklist | Veredicto | Evidencia |
|---|---|---|---|
| §0 | Router construye el UoW, el servicio lo abre, sólo `__aexit__` confirma | PASS | `router.py` `Depends(get_libros_uow)`; `service.py` abre con `async with uow`; `app/core/unit_of_work.py` `__aexit__` commit/rollback sin cerrar sesión |
| §0 | `selectinload` sólo en `repository.py` | PASS | grep `selectinload` en `service.py`/`router.py`/`unit_of_work.py` → vacío; precarga en `LibroRepository.get_by_id`/`listado_stmt`/`buscar_por_titulo` |
| §7 | `BaseRepository(session, model_class)` + `SoftDeleteRepository` con filtro de borrados y `get_by_id_including_deleted`/`soft_delete` | PASS | `app/core/repository.py` conforme (consumido por `LibroRepository(SoftDeleteRepository[Libro])`) |
| §7 | Ningún repositorio hace `commit()`, sólo `flush()` | PASS | grep `commit()` en `app/core/repository.py` y `app/modules/*/repository.py` → vacío; `add`/`add_autoria`/`aplicar_movimiento` hacen `flush()` |
| §7 | UoW del módulo compone el repositorio con la misma sesión | PASS | `LibrosUnitOfWork.__init__` pasa la misma `session` a `LibroRepository(session)` |
| §7 | Servicio sin `AsyncSession` ni `UnitOfWork(` | PASS | grep en `libros/service.py` → vacío; recibe `LibrosUnitOfWork` |
| §7 | Stock se escribe en un único punto (alta, reposición, venta) | PASS | única mutación de `libro.stock` en todo `app/modules`: `repository.py:87` (`libro.stock += cantidad` dentro de `aplicar_movimiento`, que agrega el `MovimientoStock` y hace `flush()`); el `stock=0` del constructor en `service.py` es valor inicial neutro, no un cambio |
| §8 | `POST /libros` recibe `stock_inicial` (no `stock`) y deja movimiento «Stock inicial» | PASS | `LibroCreate.stock_inicial: int = Field(ge=0)`, sin campo `stock` (`extra="forbid"`); `service.crear` crea libro + `libro_autor` + `aplicar_movimiento(..., "Stock inicial", ...)` en un `async with`; evidencia EVIDENCIA.md C-13.1 (`201`, `"stock":3`) y C-13.2 (`200`, `motivo: "Stock inicial"`, `cantidad: 3`) |
| §8 | Alta: ISBN duplicado entre vigentes → 409; FK inexistente → 409; `precio<=0`/`stock_inicial<0` → 422 | PASS | `IntegrityError` → `traducir_integrity_error` con mapeos `uq_libro_isbn_vigente` (409 «Ya existe un libro con ese ISBN») y FKs de libro/autor; `precio: Decimal = Field(gt=0)`, `stock_inicial: ge=0`; evidencia C-13.10 (409) |
| §8 | Re-alta con ISBN de un libro dado de baja → 201 (índice parcial) | PASS | `models.py` `Index("uq_libro_isbn_vigente", "isbn", unique=True, postgresql_where=text("borrado_en IS NULL"))`; evidencia C-13.9 (201 id 7) |
| §8 | `PATCH /libros/{id}` sólo título y precio; `stock` → 422; 404 inexistente | PASS | `LibroUpdate` sólo `titulo`/`precio` + `extra="forbid"`; `service.actualizar` usa `exclude_unset`; 404 si `get_by_id` → `None`; evidencia C-16.7 (200, precio intacto), C-16.8 (422 `extra_forbidden`) |
| §8 | Invariante `libro.stock = SUM(movimiento_stock.cantidad)` | PASS | SQL en base real: `SELECT l.id ... HAVING l.stock <> COALESCE(SUM(m.cantidad),0)` → **0 filas** (5 libros, 7 movimientos); `tests/test_stock_invariante.py` cubre alta por punto único, stock 0 y control negativo |
| §8/§9 | `GET /libros` paginado con filtros y exclusión de borrados; búsqueda con parámetro ligado | PASS | `listado_stmt` filtra `borrado_en IS NULL`, `ilike(f"%{titulo}%")` como bind param, `genero_id`, delega en `paginar`; evidencia C-16.1–C-16.6 incl. `' OR '1'='1` → `total: 0` |
| §1 | Módulo `libros` con las seis capas | PASS | `models.py`, `schemas.py`, `repository.py`, `unit_of_work.py`, `service.py`, `router.py` presentes; `main.py` cablea `libros_router` (abierto: GET) y `libros_router_admin` (protegido: POST/PATCH/DELETE/reponer/movimientos) |

Ítems de §7 no aplicables a C-08 (registro atómico, venta transaccional, `intento_acceso`, eventos RN-16) se auditan en sus changes (C-12/C-16/C-15).

## Hallazgos (WARN)

1. **WARN — `usuario_id` del movimiento «Stock inicial» es un usuario arbitrario.**
   `crear_libro` recibe `_sesion: IdentidadActual` (el admin autenticado) pero llama `service.crear(uow, data)` **sin pasarlo**; el servicio cae al fallback `select id from usuario limit 1`, atribuyendo el movimiento al primer usuario de la tabla en vez del actor real. El design D-4 de C-08 preveía pasar `usuario_actual`. No rompe el invariante ni ningún caso C, y la consigna no verifica el actor del movimiento de alta, pero es un desvío del diseño y una atribución incorrecta (auditoría RN-16 aparte).
   *Fix recomendado*: `await service.crear(uow, data, _sesion)` (y lo mismo en `reponer`, si aplica al auditar C-09).

2. **WARN — alta con `stock_inicial = 0` no deja movimiento «Stock inicial».**
   `service.crear` salta `aplicar_movimiento` cuando `stock_inicial` es 0. Es la única opción viable: `CHECK (cantidad <> 0)` de `movimiento_stock` impide un movimiento de 0, y el invariante se mantiene (`0 = 0`). Queda documentado en `test_stock_cero_no_requiere_movimiento`. El ítem §8 («deja el movimiento «Stock inicial»») debe leerse como «cuando el stock inicial es distinto de cero». Sin acción; se registra para trazabilidad.

## Nota de trazabilidad

- El `stock=0` inicial en `service.crear` (constructor) es inicialización, no cambio de stock: la única mutación posterior vive en `aplicar_movimiento` (`repository.py:87`), único punto conforme a RN-11.
- Estado de base observado: libros 1–5 con stock 10/5/8/3/1, movimientos «Stock inicial» (11, 5, 10, 3, 1) y «Venta» (−1, −2); invariante global 0 violaciones.
- `EVIDENCIA.md` registra el alta real (C-13.1: 201 `"stock":3`; C-13.2: movimiento «Stock inicial») y los controles de catálogo C-16; el smoke test propio del change (py_compile, import main, greps vacíos, 201 + invariante) consta en `CHANGES.md` §[C-08] «Estado».
