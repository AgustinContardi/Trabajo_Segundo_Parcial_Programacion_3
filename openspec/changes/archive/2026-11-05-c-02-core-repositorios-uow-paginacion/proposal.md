# Proposal — C-02 core-repositorios-uow-paginacion

## Why

`C-01` (fundación) ya dejó el esqueleto `parcial/` con `Settings`, `lifespan`, `get_session` y Alembic
sin credenciales. El siguiente paso del camino crítico (`C-01 → C-02 → C-05 → …`) es la capa que
**todos** los módulos de dominio van a repetir: repositorios + Unit of Work + paginación. Hoy el TP
cap. 1-4 hace lo contrario de lo que pide la rúbrica: los servicios reciben `AsyncSession`, escriben
con `session.add(...)` y confirman con `session.commit()` en el router. Ese patrón vale **16 %** de la
nota («Repositorios y Unit of Work») y se juega entero en este change, porque lo que se define acá se
copia en `C-06`…`C-10` y `C-15`.

`C-02` no toca ningún módulo existente: sólo crea la infraestructura compartida en `app/core/` y la
plantilla de UoW por módulo, para que los changes siguientes puedan adoptarla sin reinventarla.

## What Changes

- Crear `parcial/app/core/repository.py` con:
  - `BaseRepository[T]` con constructor `(session, model_class)` (los genéricos se borran en runtime) y
    los métodos `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`.
  - `SoftDeleteRepository[T]` que hereda, filtra `borrado_en IS NULL` por defecto y agrega
    `get_by_id_including_deleted` y `soft_delete` (que **no** existen en la base).
  - `add` y `update` hacen **`flush()`**, nunca `commit()`.
- Crear `parcial/app/core/unit_of_work.py` con `UnitOfWork` como gestor de contexto asíncrono: `commit`
  en `__aexit__` sin excepción, `rollback` con excepción, y **no cierra** la sesión (no la creó).
- Crear `parcial/app/core/paginacion.py` con el tipo `Pagina[T]` y la función `paginar(...)` que devuelve
  `{items, total, page, size, pages}`, valida `page ≥ 1` y `size` 1..100 (default 20), responde **422**
  con mensaje propio si la página está fuera de rango y devuelve una página vacía (`pages: 1`) si no hay
  resultados.
- Crear la plantilla `parcial/app/modules/<módulo>/unit_of_work.py` que compone los repositorios del
  módulo con **la misma** sesión (se replica en `C-06`…`C-10` y `C-15`).
- Dejar un **comentario de contrato** en cada archivo: quién construye, quién abre, quién confirma y
  quién cierra (`CV-01`).
- No se modifica ningún módulo de dominio ni ningún router: la adopción de la nueva capa queda para los
  changes de capas (`C-06`…`C-10`).

## Capabilities

### New Capabilities

- `core-repositories`: repositorios base y especializados para borrado lógico, gestor de contexto de
  transacción (Unit of Work) y envoltorio de paginación compartido por todos los módulos.

### Modified Capabilities

Ninguna: este change no altera requisitos de capacidades existentes (`app-foundation`,
`legacy-baseline`); agrega una nueva capacidad de infraestructura que los módulos consumirán después.

## Impact

- **Código nuevo**: `parcial/app/core/repository.py`, `parcial/app/core/unit_of_work.py`,
  `parcial/app/core/paginacion.py` y la plantilla de `<módulo>/unit_of_work.py`.
- **API**: ninguna ruta nueva ni modificada. Los endpoints existentes del TP cap. 1-4 siguen funcionando
  con el patrón anterior hasta que `C-06`…`C-10` los migren.
- **Dependencias**: sólo lo ya instalado (`SQLAlchemy 2.0 async`, `SQLModel 0.0.24`, `FastAPI`). No se
  agregan paquetes.
- **Changes aguas abajo**: `C-05` (errores y contratos) construye sobre `paginar()`; `C-06`…`C-10` y
  `C-15` replican la plantilla de UoW. `C-03`/`C-04` (modelos y migraciones) no dependen de este change.
- **Riesgo principal**: que la clase base quede demasiado acoplada a un modelo concreto o que algún
  repositorio termine haciendo `commit()`; se mitiga con la regla dura 2 (sólo `flush()`) y con tests de
  la capa que verifican que `commit()` nunca se llama desde un repositorio.