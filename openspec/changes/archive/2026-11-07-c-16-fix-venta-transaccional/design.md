# Design — C-16 fix: venta transaccional, hardening y evidencia

## Context

Ver `proposal.md` para la motivación y `specs/venta-transaccional/spec.md` para el contrato observable. El flujo transaccional de `C-16` ya funciona y no se rediseña; este change corrige el contrato de entrada, el borde de errores y la evidencia.

Estado observado en `parcial/` (2026-11-07):

- `VentaCreate.cliente_id` y `RenglonCreate.libro_id/cantidad` son `int` sin cota. Un `cliente_id` de `10**30` llega a asyncpg y produce `asyncpg.exceptions.DataError` (`value out of int64 range`), que SQLAlchemy envuelve como `sqlalchemy.exc.DBAPIError` (verificado con una sonda local); el servicio sólo atrapa `IntegrityError`, así que la excepción termina en **500**.
- `RenglonCreate.cantidad: int = Field(gt=0)` acepta `true` como `1` por coerción de Pydantic; también acepta strings y floats.
- `service.registrar_venta` detecta `libro_id` repetido **antes** de abrir el UoW, por lo que un cuerpo con duplicado y cliente inexistente devuelve `422` en lugar de `409`.
- `router.py` declara `POST /ventas/`; `POST /ventas` sin barra devuelve **307** por `redirect_slashes`.
- `manejador_request_validation_error` devuelve el `msg` en inglés de Pydantic.
- `C-16` archivado: `tasks.md` con **0/25** tareas marcadas y sin `parcial/test/ventas.http`; `openspec validate --archived --strict` falla.
- Fixtures de `tests/conftest.py` y de `test_ventas_api.py` crean `Libro(stock=N)` directamente, sin `movimiento_stock` inicial. Los tests comparan deltas (`stock - inicial == suma`) y no la igualdad global; después de la suite quedan libros que violan `libro.stock = SUM(movimiento_stock.cantidad)`.
- `test_ventas_crear_service.py` usa `pytest.raises(Exception)` y bloques `finally: pass`; no verifica `HTTPException(409)` ni ausencia de escrituras.
- La suite actual colecta **325 tests**; el padre de `f2b6b89` tenía **264** (delta real **+61**). `CHANGES.md` dice 325 vs 304 y el commit habla de 21 tests nuevos.
- PostgreSQL 17.11 local, `alembic check` limpio, sin migraciones nuevas.

Restricciones de arquitectura: router construye el UoW y el servicio lo abre (`CV-01`); repositorios sólo `flush()` (`CV-02`); servicios sin `AsyncSession`; `selectinload` sólo en `repository.py` (`CV-03`); sin lógica de negocio en el router; sin migraciones; sin `commit`/`push`.

## Goals / Non-Goals

**Goals:**

- Cerrar el contrato de entrada para que ninguna entrada inválida llegue a la base ni termine en 500.
- Traducir errores de datos en el borde de la aplicación sin filtrar texto de PostgreSQL.
- Alinear el orden observable 401 → 403 → 409 → 422 y eliminar la redirección 307.
- Reparar la evidencia de tests y el `.http` faltante, con el invariante global de stock verificable.
- Reconciliar la documentación sin reescribir el registro histórico de `C-16`.

**Non-Goals:**

- No cambiar la transacción, el orden de las cuatro escrituras ni el uso de `aplicar_movimiento`.
- No agregar locks, `SELECT ... FOR UPDATE` ni actualización condicional de stock; la concurrencia sigue fuera de alcance (`RN-10`).
- No crear migraciones, constraints, columnas ni triggers.
- No tocar `despliegue/`, `C-17`–`C-22` ni `c-12-auto-registro-atomico`.

## Decisions

### 1. Enteros estrictos y acotados en el schema

En `parcial/app/modules/ventas/schemas.py`:

```python
BIGINT_MAX = 2**63 - 1   # cliente_id, libro_id
INT_MAX = 2**31 - 1      # cantidad: columna integer

class RenglonCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    libro_id: Annotated[int, Field(strict=True, ge=1, le=BIGINT_MAX)]
    cantidad: Annotated[int, Field(strict=True, ge=1, le=INT_MAX)]

class VentaCreate(BaseModel, SinNulMixin):
    model_config = ConfigDict(extra="forbid")
    cliente_id: Annotated[int, Field(strict=True, ge=1, le=BIGINT_MAX)]
    renglones: List[RenglonCreate] = Field(min_length=1)
```

`strict=True` en Pydantic v2 rechaza `bool`, `float` y `str` sin coerción, justo lo que el contrato necesita. `le` evita el `DataError` de asyncpg y el desborde de `integer` en `cantidad`. Alternativa descartada: validar rangos en el servicio; obligaría a abrir el UoW para algo que el contrato puede rechazar antes, y repetiría las cotas en dos capas.

Consecuencia: `true`, `"1"`, `1.5`, `0`, negativos y `10**30` dan `422` sin tocar la base. El contrato es deliberadamente estricto; un cliente que mande strings numéricos debe corregir el JSON.

### 2. Traducción de errores de datos en el borde

La sonda local confirma que el error real es `sqlalchemy.exc.DBAPIError` con `orig` de tipo `asyncpg.exceptions.DataError` (no `sqlalchemy.exc.DataError`). Por eso:

- En `app/core/errors.py`, agregar `traducir_error_de_datos(exc)` que devuelva `HTTPException(422, "Los datos enviados no son válidos")` cuando `exc` sea `DataError` o cuando `getattr(exc, "orig", None)` sea un `DataError` de asyncpg/SQLAlchemy. No incluye el texto original.
- Registrar en `main.py` un handler para `DBAPIError`: si es un error de datos, responde `422` con el mensaje propio; si no, responde `500` con `{"detail": "No se pudo completar la operación"}` sin texto interno. Así ninguna ruta filtra PostgreSQL.
- Mantener el `except IntegrityError` del servicio **fuera** del `async with` y evaluarlo antes que el handler genérico: `IntegrityError` es subclase de `DBAPIError`, y su traducción específica a 409/422 debe prevalecer.
- En `service.registrar_venta`, ampliar el `except` exterior a `(IntegrityError, DBAPIError)` sólo para traducir datos; si el `DBAPIError` no es de datos, re-lanzar para que actúe el handler global. El `async with` ya hizo rollback antes de llegar al `except`.

Alternativa descartada: atrapar todo dentro del `async with`; confirmaría filas parciales al ver una salida normal. Alternativa descartada: confiar sólo en las cotas del schema; el handler es defensa en profundidad para cualquier otra entrada y para no filtrar texto interno.

### 3. Orden de validación dentro del único `async with`

Mover la detección de duplicados desde antes del UoW al servicio dentro de la transacción, después de las verificaciones 409:

1. `cliente` existente → 409.
2. libros existentes (`get_by_ids`) → 409 si falta alguno.
3. libros vigentes (`borrado_en IS NULL`) → 409.
4. stock agregado por `libro_id` (sumar cantidades de renglones repetidos) → 409 si no alcanza.
5. recién ahora, `libro_id` repetido → 422.
6. escritura: venta → renglones → movimientos.

El stock se evalúa con cantidades agregadas para que un duplicado no pueda pasar dos chequeos individuales que en conjunto exceden el stock. Si hay duplicado y además stock insuficiente, gana el 409, respetando el orden. Alternativa descartada: validar duplicados con un `model_validator` de Pydantic; correría antes de la autenticación y convertiría un 401/403 en 422.

### 4. Ruta sin 307

Apilar dos decoradores sobre el mismo handler:

```python
@router.post("", response_model=VentaDetailRead, status_code=201, include_in_schema=False)
@router.post("/", response_model=VentaDetailRead, status_code=201)
async def crear_venta(...):
    ...
```

`/ventas` y `/ventas/` comparten handler, dependencias y respuesta; la variante sin barra no aparece en OpenAPI. Alternativa descartada: `redirect_slashes=False`; convertiría el 307 en 404.

### 5. Mensajes 422 en español sin romper el contrato de errores

`manejador_request_validation_error` conservará `loc` y `type` (los tests actuales los usan) y reemplazará `msg` por un texto propio en español según el tipo de error:

- `missing` → "Falta un campo obligatorio".
- `extra_forbidden` → "El campo no está permitido".
- `int_parsing`, `int_type`, `bool_type`, `float_type` → "Debe ser un número entero válido".
- `greater_than` / `greater_than_equal` → "El valor debe ser mayor que el mínimo permitido".
- `less_than_equal` → "El valor supera el máximo permitido".
- `too_short` → "La lista no puede estar vacía".
- desconocido → "Los datos enviados no son válidos".

No se traduce ni se devuelve el texto de Pydantic ni el de PostgreSQL. Alternativa descartada: un handler sólo para `POST /ventas`; duplicaría la lógica y dejaría el resto del proyecto con mensajes en inglés.

### 6. Evidencia de tests: stock inicial por el punto único e invariante global

- Agregar a `tests/conftest.py` un helper/fixture `libro_con_stock_inicial(...)` que cree el libro con `stock=0` y luego aplique `LibroRepository.aplicar_movimiento(libro, stock_inicial, "Stock inicial", usuario_id)`; el stock y el movimiento nacen juntos. Extender `catalogo_factory.libro` para que use ese camino cuando reciba `stock > 0`.
- Los escenarios de `test_ventas_api.py` y `test_ventas_crear_service.py` deben usar ese helper, no `Libro(stock=N)`.
- Agregar una consulta de invariante reutilizable:

```sql
SELECT l.id
FROM libro l
LEFT JOIN movimiento_stock m ON m.libro_id = l.id
GROUP BY l.id, l.stock
HAVING l.stock <> COALESCE(SUM(m.cantidad), 0);
```

- Afirmar 0 filas para los libros creados por el test y ejecutar la consulta global al final de la suite. Si la base local conserva violaciones históricas de la suite anterior, repararlas una vez con movimientos compensatorios de "Stock inicial" (nunca con `UPDATE`/`DELETE` sobre `movimiento_stock`) o reconstruir la base de prueba; el resultado se registra como evidencia. No se debilita la aserción.
- Los tests de 409/422 deben capturar `pytest.raises(HTTPException)` y afirmar `status_code`, además de comparar conteos de `venta`, `renglon_venta`, `movimiento_stock` y el stock de los libros antes/después.
- Eliminar los `try/finally: pass` de `test_ventas_crear_service.py`; usar datos únicos por test y aserciones relativas. Como `movimiento_stock` es de sólo agregado, el teardown no puede borrar libros ya vendidos: la estrategia es aislamiento por datos únicos y deltas, no borrado destructivo. Documentarlo en el docstring del archivo.
- Dos corridas consecutivas de `pytest -q` deben dar el mismo resultado; no se usan IDs ni emails repetidos.

### 7. `parcial/test/ventas.http`

Crear el archivo con bloques REST Client para:

- **C-10**: login de vendedor, alta válida con dos renglones, `201`, precios copiados, total, stock, movimientos y el aviso de `BackgroundTasks` en la consola de uvicorn.
- **C-11**: Rayuela (1, alcanza) + Bestiario (2, hay 1) → `409`; consultas de control de `venta`, `renglon_venta`, `movimiento_stock` y del invariante (0 filas).
- **C-12**: cliente inexistente, libro inexistente y libro dado de baja → `409` en los tres, con las mismas consultas de control.
- Cada caso con el status y el cuerpo esperado en un comentario, y las consultas SQL de control.

La ejecución con REST Client es manual y externa al entorno headless; si no se puede automatizar, se registra como evidencia pendiente de ejecución y los tests de integración cubren el mismo comportamiento.

### 8. Reconciliación documental sin reescribir historia

- `openspec/changes/archive/2026-11-07-c-16-venta-transaccional/tasks.md`: marcar una tarea sólo cuando la evidencia nueva la satisfaga de verdad; al inicio del archivo, agregar una nota `Evidencia completada por c-16-fix-venta-transaccional` con la fecha y el puntero, en vez de reescribir el contenido original. Si alguna tarea sigue sin poder satisfacerse, dejarla `[ ]` y explicar por qué.
- `CHANGES.md`: corregir el estado de `C-16` a "325 passed vs 264 del padre (+61)" y aclarar que cliente/libro inexistente es **409**. No se reescribe el commit `f2b6b89` ni se hace `amend`.
- `openspec/specs/venta-transaccional/spec.md`: aplicar el delta (contrato estricto, orden, errores de datos, rutas sin 307). Corregir el título del requisito de orden a **401 → 403 → 409 → 422**; el 404 pertenece a las lecturas de detalle, no a `POST /ventas`.
- `openspec/specs/ventas/spec.md`: agregar la mención de `POST /ventas` y ajustar el `Purpose` para que el módulo no se describa como sólo lecturas, sin duplicar el contrato transaccional.

## Risks / Trade-offs

- [El handler de `DBAPIError` podría clasificar como 422 un error de datos legítimo y ocultar un bug] → Sólo los `DataError`/`orig DataError` se traducen a 422; el resto devuelve 500 genérico sin texto. Los tests de integración cubren los casos válidos e inválidos.
- [Un `DBAPIError` deja la sesión inutilizable hasta el rollback] → El `except` vive fuera del `async with`; no se ejecuta ninguna consulta posterior salvo el rollback del `__aexit__`.
- [`strict=True` rechaza clientes que mandaban `"1"` o `1.0`] → Es el contrato pedido (`RN-15`): un JSON con tipos incorrectos es inválido; se documenta en el `.http` y en los tests.
- [Mover el duplicado después del stock hace que un duplicado con stock insuficiente devuelva 409] → Es coherente con el orden 409 → 422 y con el chequeo agregado; se prueba explícitamente.
- [`movimiento_stock` es de sólo agregado y los tests no pueden borrar lo creado] → Aislamiento por datos únicos y aserciones relativas; la base de prueba crece, pero las dos corridas son deterministas. No se relaja el trigger.
- [La base local ya tiene libros con el invariante roto por la suite anterior] → Reparación única con movimientos compensatorios o reconstrucción de la base de prueba; la consulta global debe dar 0 filas antes de cerrar el change.
- [Marcar tareas archivadas puede leerse como reescritura de historia] → Sólo se marcan con evidencia real y se agrega una nota de procedencia; el commit y el contenido original no se alteran.
- [La concurrencia sigue sin resolverse] → Aceptado por `RN-10`; se documenta como hardening futuro, no como blocker de este change.

## Migration Plan

Sin migraciones ni cambios de esquema: se modifican schemas, servicio, router, errores, tests y documentación. El despliegue es un reinicio normal de la aplicación. Rollback: revertir los archivos de código y documentación; las ventas ya confirmadas siguen siendo válidas. La reparación de la base de prueba, si se hace, es local y no forma parte del esquema.

## Open Questions

Ninguna que bloquee el plan. La decisión de reparar o reconstruir la base local de pruebas se toma durante la implementación según el estado observado y se registra como evidencia.

## UI Mockups

- Design system mode: `off` (sin UI en este change).
- Decision: no (no UI)
- Fecha: 2026-11-07
- Motivo: API pura; no hay pantallas, componentes ni estilos. El cambio es hardening de contrato, errores y evidencia de tests.
