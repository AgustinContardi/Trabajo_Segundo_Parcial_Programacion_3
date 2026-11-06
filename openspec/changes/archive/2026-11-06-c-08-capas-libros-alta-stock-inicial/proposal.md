# Proposal — C-08 capas-libros-alta-stock-inicial

## Why

`libros` sigue con el patrón anterior del TP cap. 1-4: el servicio recibe `AsyncSession`, escribe con `session.add(...)` y el router confirma con `session.commit()`, y la precarga (`selectinload`/`joinedload`) vive en el servicio. Ese patrón vale el **16 %** de la rúbrica («Repositorios y Unit of Work») y es el que C-08 reemplaza para el módulo de libros.

C-08 es el tercer eslabón de Fase 4 y el que define el **punto único de escritura de stock** (`RN-11`): un solo método que escribe `libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar, usado por el alta, la reposición y la venta. Si alguien escribe `libro.stock` por fuera, la igualdad `stock = SUM(movimiento_stock.cantidad)` se rompe y fallan **todos** los casos de venta (`RN-10`, `RN-11`). La governance es **CRÍTICO**.

Además, C-08 introduce la **baja lógica** implícita del catálogo (el ISBN es único sólo entre los vigentes, `RN-01`/`RN-13`) y el alta con `stock_inicial` (no `stock`) más los autores anidados, que es lo que C-09 (baja/reposición/movimientos) y C-10 (ventas lecturas) y C-16 (venta transaccional) consumen.

## What Changes

- Refactorizar el módulo `libros` a las **seis capas** obligatorias (`models`, `schemas`, `repository`, `unit_of_work`, `service`, `router`), conforme a `CV-03`.
- Crear `LibroRepository(SoftDeleteRepository[Libro])` que filtre los dados de baja por defecto (`borrado_en IS NULL`) y precargue editorial, género y autores **declarado adentro del método que lo necesita** (`CV-02`); más `get_by_id_including_deleted` (heredado) y un método de búsqueda por título con `ilike` y **parámetro ligado** (sin concatenar, `RN-15`).
- Definir el **punto único de escritura de stock**: un solo método que actualiza `libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar; motivos `'Stock inicial'`, `'Reposición'`, `'Venta'` (`RD-02`). Lo usan el alta, la reposición (C-09) y la venta (C-16).
- `POST /libros` recibe `stock_inicial` (**no** `stock`) y `autores: [{autor_id, rol, orden}]`: libro + `libro_autor` + movimiento «Stock inicial» en **un** `async with`; **201**; **409** si el ISBN choca con un libro vigente o si una FK no existe; **422** si `precio <= 0` o `stock_inicial < 0`.
- `PATCH /libros/{id}` acepta **sólo** título y precio; mandar `stock` → **422** (el schema no lo declara, `extra="forbid"`).
- Lecturas: `GET /libros` (`page`, `size`, `titulo`, `genero_id`) con envoltorio y exclusión de borrados; `GET /libros/{id}`; listados por editorial/género/autor (ya cableados en C-06, se reusan); búsqueda con `ilike` y parámetro ligado.
- Reescribir `service.py` para que **abra** el UoW con `async with` y **nunca** lo construya ni reciba una `AsyncSession`; traducir `IntegrityError` a `409`/`422` con mensaje propio.
- Reescribir `router.py` para que **construya** el UoW con una dependencia y lo pase al servicio, sin `session.commit()` ni `session.rollback()` en el router (`CV-01`).
- Verificación de la capa: `grep -rn "AsyncSession\|UnitOfWork(" app/modules/libros/service.py` vacío y precarga exclusiva en `repository.py` (`CV-02`).

## Capabilities

### New Capabilities

- `libros`: seis capas para el módulo `libros` — alta de libro con `stock_inicial` y autores anidados (`201`/`409`/`422`), punto único de escritura de stock, consulta y actualización parcial (sólo título y precio; `stock` → `422`), listado paginado con filtro por título y género, y búsqueda con parámetro ligado. El router construye el UoW y el servicio lo abre; la precarga vive sólo en `repository.py`; el repositorio filtra los dados de baja por defecto.

### Modified Capabilities

Ninguna: los requisitos de `data-model` (`libro.borrado_en` + índice parcial del ISBN, `CHECK (precio > 0)`, `CHECK (stock >= 0)`, `movimiento_stock` con `CHECK (cantidad <> 0)`) y de `core-repositories` (repositorios base, UoW base, paginación) no cambian; C-08 los **consume** y los aplica al módulo. Los schemas base de `api-contracts` (`Create`/`Update`/`Read` con `extra="forbid"`) tampoco se redefinen: se instancian por entidad en el módulo.

## Impact

- **Código nuevo**: `parcial/app/modules/libros/repository.py` y `unit_of_work.py`.
- **Código reescrito**: `service.py` y `router.py` del módulo (pierden `AsyncSession` y `session.commit()`); `schemas.py` se modifica para recibir `stock_inicial` (no `stock`) en `LibroCreate` y excluir `stock` del `LibroUpdate`; `models.py` sin cambios de esquema (ya correcto por C-03).
- **Migraciones**: ninguna nueva (el esquema ya está en 0003/0004).
- **API**: se mantienen las rutas existentes del TP cap. 1-4, pero con el patrón de capas y los códigos fijados por C-05 (201/200/404/409/422); se agrega paginación y filtro a `GET /libros`; se agrega el punto único de stock que C-09 y C-16 reusarán.
- **Dependencias aguas abajo**: habilita `C-09` (baja/reposición/movimientos, que reusa el punto único y el filtro de borrados) y `C-10` (capas-ventas-lecturas, que precarga el libro incluyendo los dados de baja) y `C-16` (venta transaccional, que descuenta stock con el punto único).
- **Riesgo principal**: que el stock se escriba por fuera del punto único (rompe `stock = SUM(movimiento_stock.cantidad)` y falla todos los casos de venta); se mitiga centralizando la escritura en un solo método del repositorio/servicio y con la verificación de la capa. El `ilike` con concatenación filtraría el esquema (`RN-15`); se mitiga con parámetro ligado.