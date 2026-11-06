# Tasks

## 1. Refactor del módulo a seis capas (esqueleto)

- [x] 1.1 Crear `parcial/app/modules/libros/repository.py` con `LibroRepository(SoftDeleteRepository[Libro])` y verificar que importa sin error (`python -c "import app.modules.libros.repository"`).
- [x] 1.2 Crear `parcial/app/modules/libros/unit_of_work.py` con `LibrosUnitOfWork` y `get_libros_uow` y verificar que importa sin error.
- [x] 1.3 Reescribir `parcial/app/modules/libros/schemas.py`: `LibroCreate` recibe `stock_inicial` (no `stock`) y `LibroUpdate` sólo `titulo` y `precio`; verificar que `stock` en el cuerpo da `422` (`extra="forbid"`).
- [x] 1.4 Reescribir `parcial/app/modules/libros/service.py` para recibir el UoW, abrirlo con `async with` y sin `AsyncSession`/`UnitOfWork(`; verificar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/libros/service.py` vacío.
- [x] 1.5 Reescribir `parcial/app/modules/libros/router.py` para construir el UoW con `Depends(get_libros_uow)` y sin `session.commit()`/`session.rollback()`; verificar `grep -rn "session.commit\|session.rollback\|selectinload\|joinedload" parcial/app/modules/libros/router.py` vacío.

## 2. Punto único de escritura de stock

- [x] 2.1 Implementar `LibroRepository.aplicar_movimiento(libro, cantidad, motivo, usuario_id, venta_id=None)` que actualiza `libro.stock` y agrega `MovimientoStock` en el mismo lugar con `flush()`; verificar que no existe otro lugar que escriba `libro.stock` (`grep -rn "stock =" parcial/app/modules` sólo en repository).
- [x] 2.2 Implementar `LibroRepository.add_autoria(...)` (o uso directo de `session.add` + `flush`) para los `libro_autor` del alta; verificar que hace `flush()` y no `commit()`.

## 3. Alta de libro (POST /libros)

- [x] 3.1 Implementar `service.crear(uow, data, usuario_actual=None)` que en un solo `async with` crea libro + autores + movimiento «Stock inicial»; verificar con un caso manual que deja el movimiento.
- [x] 3.2 Manejar `IntegrityError` del índice parcial del ISBN y de las FKs traduciéndolo a `409` con mensaje propio; verificar que un ISBN duplicado entre vigentes da `409`.
- [x] 3.3 Verificar que un ISBN reutilizado tras baja lógica da `201` (índice parcial).
- [x] 3.4 Verificar que `precio <= 0` o `stock_inicial < 0` da `422` (schema).
- [x] 3.5 Cablear `POST /libros` en el router con `status_code=201` y respuesta `LibroDetailRead`; verificar que la ruta responde `201` en un smoke test.

## 4. Actualización parcial (PATCH /libros/{id})

- [x] 4.1 Implementar `service.actualizar(uow, libro_id, data)` aplicando sólo `titulo` y `precio` con `exclude_unset`; verificar que mandar `stock` da `422` (schema `extra="forbid"`).
- [x] 4.2 Verificar que un `PATCH` a un id inexistente da `404` y que `precio <= 0` da `422`.

## 5. Lecturas (GET /libros, GET /libros/{id}, búsqueda)

- [x] 5.1 Implementar `LibroRepository.get_by_id` con precarga de editorial, género y autores; verificar que un libro dado de baja retorna `None`.
- [x] 5.2 Implementar `service.obtener` y `to_detail_read`/`to_read`; verificar que `GET /libros/{id}` devuelve editorial, género y autores.
- [x] 5.3 Implementar `service.listar` con filtros `titulo` (ilike con bind param) y `genero_id`, exclusión de borrados y paginación; verificar el envoltorio `{items, total, page, size, pages}`.
- [x] 5.4 Verificar que `titulo = ' OR '1'='1` no rompe ni devuelve todo (parámetro ligado).
- [x] 5.5 Cablear `GET /libros`, `GET /libros/{id}` y `PATCH /libros/{id}` en el router; verificar imports de `main.py`/app OK.

## 6. Invariantes y verificación de capa

- [x] 6.1 Verificar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/libros/service.py` vacío.
- [x] 6.2 Verificar `grep -rn "selectinload\|joinedload" parcial/app/modules/libros/service.py parcial/app/modules/libros/router.py` vacío.
- [x] 6.3 Verificar `grep -rn "session.commit\|session.rollback" parcial/app/modules/libros/router.py` vacío.
- [x] 6.4 Verificar `py_compile` de todos los archivos del módulo y `import app.main` OK.
- [x] 6.5 Verificar el invariante `libro.stock = SUM(movimiento_stock.cantidad)` tras un alta manual.

## Workflow follow-up

- Archivar el change con `/opsx:archive` tras la revisión y marcar `[x]` en `CHANGES.md`.
- Verificar el resultado archivado.