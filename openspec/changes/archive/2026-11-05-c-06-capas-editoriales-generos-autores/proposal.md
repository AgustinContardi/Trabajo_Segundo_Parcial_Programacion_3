# Proposal — C-06 capas-editoriales-generos-autores

## Why

C-05 ya fijó los contratos transversales (`traducir_integrity_error`, manejador de
`RequestValidationError`, `paginar()` conectado, schemas base con `extra="forbid"` y el orden
`404 → 403 → 409 → 422`), pero los módulos del TP cap. 1-4 siguen con el patrón anterior:
los servicios reciben `AsyncSession`, escriben con `session.add(...)` y confirman con
`session.commit()` en el router, y la precarga (`selectinload`) vive en el servicio. Ese patrón
vale el **16 %** de la rúbrica («Repositorios y Unit of Work») y es el que C-06 reemplaza
para los tres módulos más simples del catálogo: `editoriales`, `generos` y `autores`.

C-06 es el **molde** que copian C-07 … C-10 y C-15: si el patrón queda mal acá, el error
se replica cuatro veces. Por eso se hace primero sobre los CRUDs simples (sin stock, sin
ventas, sin roles), donde el riesgo es bajo y el patrón se puede validar en aislamiento.

## What Changes

- Refactorizar los tres módulos `editoriales`, `generos` y `autores` a las **seis capas**
  obligatorias (`models`, `schemas`, `repository`, `unit_of_work`, `service`, `router`),
  conforme a `CV-03`.
- Crear un `Repository` por entidad (`EditorialRepository`, `GeneroRepository`,
  `AutorRepository`), todos extendiendo `BaseRepository[T]`, con precarga (`selectinload`)
  declarada **adentro del método que la necesita** (`CV-02`).
- Crear un `UnitOfWork` por módulo (`EditorialesUnitOfWork`, `GenerosUnitOfWork`,
  `AutoresUnitOfWork`) que extienda el base y componga su repositorio con **la misma**
  sesión recibida.
- Reescribir `service.py` para que **abra** el UoW con `async with` y **nunca** lo construya
  ni reciba una `AsyncSession`; traducir `IntegrityError` a `409`/`422` con mensaje propio.
- Reescribir `router.py` para que **construya** el UoW con una dependencia y lo pase al
  servicio, sin `session.commit()` ni `session.rollback()` en el router (`CV-01`).
- `POST /editoriales`, `/generos`, `/autores` → **201**; duplicado → **409** con mensaje
  propio (`RN-01`).
- `PATCH /editoriales/{id}` y `PATCH /autores/{id}` → **200** aplicando sólo los campos
  enviados (`exclude_unset`); **404** si el recurso de la ruta no existe; **409** por
  unicidad; **422** por contrato (campo extra, tipo inválido, NUL, etc.).
- Listados paginados con el envoltorio `{items, total, page, size, pages}`.
- `GET /editoriales/{id}/libros`, `/generos/{id}/libros`, `/autores/{id}/libros` → **404**
  si el id no existe, y excluyen los libros dados de baja (`borrado_en IS NULL`).
- Verificación de la capa: `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py`
  vacío.

## Capabilities

### New Capabilities

- `editoriales-generos-autores`: CRUD con seis capas para los módulos `editoriales`,
  `generos` y `autores` — alta (`201`), duplicado (`409` con mensaje propio, `RN-01`),
  actualización parcial (`200` con `exclude_unset`), listados paginados con envoltorio y
  listado de libros por entidad (`404` si la entidad no existe, excluyendo libros dados
  de baja). El router construye el UoW y el servicio lo abre; la precarga vive sólo en
  `repository.py`.

### Modified Capabilities

Ninguna: los requisitos de `data-model` (unicidades, tipos) y de `core-repositories`
(repositorios base, UoW base, paginación) no cambian; C-06 los **consume** y los aplica a
los tres módulos. Los schemas base de `api-contracts` (`Create`/`Update`/`Read` con
`extra="forbid"`) tampoco se redefinen: se instancian por entidad en cada módulo.

## Impact

- **Código nuevo**: `parcial/app/modules/{editoriales,generos,autores}/repository.py` y
  `unit_of_work.py`.
- **Código reescrito**: `service.py` y `router.py` de los tres módulos (pierden
  `AsyncSession` y `session.commit()`); `schemas.py` ya existe con la base de C-05 y se
  mantiene.
- **Modelos**: sin cambios de esquema (`models.py` ya tiene las columnas correctas).
- **Migraciones**: ninguna nueva.
- **API**: se mantienen las rutas existentes del TP cap. 1-4, pero con el patrón de capas
  y los códigos de estado ya fijados por C-05 (201/200/404/409/422).
- **Dependencias aguas abajo**: habilita `C-08` (capas-libros, que reutiliza el patrón y
  el punto único de stock) y sirve de molde para `C-07`, `C-09`, `C-10` y `C-15`.
- **Riesgo principal**: que el molde quede mal y se replique; se mitiga con la
  verificación `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py` vacío y con
  la precarga exclusiva en `repository.py` (`CV-02`).