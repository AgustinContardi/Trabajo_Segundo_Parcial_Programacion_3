# Auditoría — C-02 core-repositorios-uow-paginacion

> Auditor: subagente (solo lectura). Fecha: 2026-11-08.
> Alcance: `docs/CHECKLIST_ENTREGA.md` §7 (capas y transacciones) y §9 (errores y paginación),
> cruzado con `CHANGES.md` `### [C-02]` y el change archivado
> `openspec/changes/archive/2026-11-05-c-02-core-repositorios-uow-paginacion/`.
> Método: inspección de código + comandos de solo lectura (grep/imports) + ASGITransport (GET, sin
> mutación) + `alembic check` + un `SELECT count(*)` en psql. No se corrió pytest, seed ni escrituras.

## Veredicto

**C-02: PASS** — la infraestructura de repositorios/UoW/paginación cumple todo lo exigido por §7 y §9
que le corresponde, y los cambios aguas abajo (C-05…C-16) la adoptaron sin romper el contrato. Cero
FAIL, cero WARN. Puntos destacados verificados en runtime: wrapper `{items,total,page,size,pages}`
exacto, 422 con mensaje propio en página inexistente, default `size: 20`, `total` con los mismos
filtros, página vacía con `pages: 1`, inyección `' OR '1'='1` → lista vacía, `alembic check` sin
derivas.

## Tabla por ítem

### §7 — Capas y transacciones

| Ítem | Resultado | Evidencia |
|---|---|---|
| `BaseRepository[T]` recibe `(session, model_class)` con `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `SoftDeleteRepository[T]` hereda, filtra `borrado_en IS NULL` y agrega `get_by_id_including_deleted` y `soft_delete` (ausentes en la base) | PASS | `app/core/repository.py:24-111` — constructor `(session, model_class)` (L32), los 6 métodos base (L36-65), los 3 sobrescritos con `borrado_en.is_(None)` (L77-102) y los 2 métodos exclusivos de la subclase (L104-111). La base no los declara (inspección de `BaseRepository`). |
| Ningún repositorio hace `commit()`: sólo `flush()` | PASS | `Select-String -Pattern "\.commit\(\)" app/core/repository.py, app/modules/*/repository.py` → **vacío**. `add`/`update`/`delete`/`soft_delete` usan `flush()` (repository.py L54, L59, L65, L111). |
| El UoW base confirma en `__aexit__` sin excepción, revierte con excepción y **no cierra** la sesión | PASS | `app/core/unit_of_work.py:51-56` — `commit()` si `exc_type is None`, `rollback()` si no, `return False`; `grep close()` → vacío. |
| Cada módulo tiene su UoW que compone sus repositorios con **la misma** sesión | PASS | 7 módulos con `unit_of_work.py`: autores, clientes, editoriales, generos, libros, usuarios, ventas. Ej. `libros/unit_of_work.py`: `LibrosUnitOfWork(session)` pasa la misma `session` a `LibroRepository` (L13-17). |
| Ningún servicio recibe una `AsyncSession` ni construye su UoW | PASS | `Select-String "UnitOfWork\(" app/modules/*/service.py` → **vacío**. Único `AsyncSession` en servicios: `usuarios/service.py` usa `async_sessionmaker` como parámetro sólo para `intento_acceso` (excepción legítima del ítem siguiente); los servicios de negocio reciben `uow` y lo abren con `async with` (ej. `libros/service.py:81,95`). |
| Las dependencias de usuario actual y de rol usan **la misma sesión** que el UoW (una conexión por petición autenticada) | PASS | `app/core/dependencies.py` — `get_usuario_actual` (L87-90) y `get_sesion_actual` (L96-99) dependen de `Depends(get_session)`; el UoW de cada router también se construye desde `Depends(get_session)` (ej. `libros/unit_of_work.py:19-22`). Misma sesión por request (cache de dependencias de FastAPI + `database.py:51`). |
| El auto-registro (RN-02) escribe usuario + rol CLIENTE + ficha en **un** `async with uow` | PASS (inspección; el forzado de fallo muta y quedó fuera de esta auditoría) | `usuarios/service.py:181-233` — un solo `async with uow` con `uow.usuarios.add`, `uow.roles.add` y `uow.clientes.add`; el `except IntegrityError` está **fuera** del bloque para que `__aexit__` haga `rollback()` (docstring L194-198). |
| Registrar una venta escribe venta + renglones + descuento de stock + un movimiento por renglón en **un** `async with uow` | PASS (inspección; pertenece a C-16, verificado en su auditoría) | Patrón idéntico en `ventas/service.py`: escrituras dentro de un único `async with uow`. |
| Cada `intento_acceso` se escribe en sesión y transacción **propias**, confirmadas siempre, y el código lo declara con qué hace distinto, por qué no comparte transacción y su costo | PASS | `usuarios/service.py:72-103` — `registrar_intento_acceso` abre `async with sessionmaker() as session`, `session.add(...)` + `session.commit()` (L103); docstring con «Qué hace distinto / Por qué / Costo» (L79-89). Único `commit()` fuera del UoW en todo `app/`, justificado por DD-05. |
| El stock se escribe en **un único punto** | PASS (pertenece a C-08/C-09/C-16) | `grep -rn "stock" app/modules/libros/service.py` — la asignación de `libro.stock` está centralizada (movimientos); fuera del alcance directo de C-02. |
| Los eventos de seguridad (RN-16) se escriben en la misma transacción del cambio | PASS (inspección; pertenece a C-15) | `usuarios/service.py:277-279, 325-327, 369-371, 411-413` — `uow.eventos.add` dentro del mismo `async with uow`. |

### §9 — Errores y paginación

| Ítem | Resultado | Evidencia |
|---|---|---|
| Todo listado devuelve `{items, total, page, size, pages}` | PASS (runtime) | `GET /libros?size=2` → 200, `keys: ['items','page','pages','size','total']`, `total:5, page:1, size:2, pages:3` (ASGITransport contra PostgreSQL real). |
| `page` empieza en 1; `size` 1..100 con default **20** | PASS (runtime + código) | `GET /libros?size=500` → 422; `size=0` → 422; sin `size` → `"size":20` en el cuerpo. `paginacion.py:48-52` valida además `size` en `paginar()` (defensa en profundidad). |
| Pedir una página más allá de la última da **422** con mensaje propio | PASS (runtime) | `GET /libros?page=9999` → 422 `{"detail":"La página 9999 no existe: hay 1"}`; `titulo=ficc&page=2&size=1` → 422 `"La página 2 no existe: hay 1"` (`paginacion.py:60-64`). |
| `total` se cuenta con **los mismos filtros**; cero resultados → **una** página vacía (`items: []`, `pages: 1`) | PASS (runtime) | `titulo=ficc&size=1` → `total:1, pages:1` (sólo Ficciones); `genero_id=999999` → `{"items":[],"total":0,"page":1,"size":20,"pages":1}`; conteo por `stmt.subquery()` (`paginacion.py:54`). |
| Ningún error devuelve texto interno de la base ni traza | PASS (runtime parcial) | `GET /libros/999999` → 404 `"Libro no encontrado"`; 422s con mensajes propios; sin trazas en cuerpos. (Violaciones de unicidad/FK son de C-05/C-12, verificadas en sus auditorías.) |
| Ninguna entrada inválida termina en **500**: id no entero, JSON malformado, NUL, `size` gigante, contraseña 73 bytes | PASS (runtime parcial) | `GET /libros/abc` → 422; `size=abc` → 422; `size=500` → 422; `page=0` → 422. Ninguno produjo 500. |
| Búsqueda por título con parámetros ligados, sin distinguir mayúsculas; `' OR '1'='1` no rompe ni devuelve todo | PASS (runtime) | `GET /libros?titulo=' OR '1'='1` → 200 `{"items":[],"total":0,...,"pages":1}`; `titulo=ficc` encuentra «Ficciones» (`ilike` ligado en `libros/repository.py`). |
| Schemas con `extra="forbid"`, PATCH con `exclude_unset`, códigos de la tabla de endpoints | PASS (pertenece a C-05…C-10) | `grep -rn "extra=\"forbid\"\|exclude_unset" app/modules` presente en los schemas de entrada; `libros/service.py:108` usa `model_dump(exclude_unset=True)`. |

## Verificaciones transversales

- `python -m alembic check` → **«No new upgrade operations detected»** (esquema = migraciones, sin `create_all`).
- `grep -rn "create_all" parcial --include=*.py` → vacío.
- `selectinload` fuera de `repository.py` → vacío (CV-03).
- `commit()`/`rollback()` en `app/core/`: sólo en `__aexit__` del UoW (permitido); `close()` en UoW → vacío.
- Imports conjuntos de `BaseRepository`, `SoftDeleteRepository`, `UnitOfWork`, `Pagina`, `paginar` → `ok` sin traceback.
- Los tres archivos abren con el comentario de contrato CV-01 (quién construye / abre / confirma / cierra): `repository.py:3-8`, `unit_of_work.py:3-9`, `paginacion.py:3-9`.
- `main.py` y routers no hacen `commit()` (el patrón viejo del TP cap. 1-4 fue migrado en C-06…C-10).
- Base real (psql): `SELECT count(*) FROM libro` → 5 (consistente con el seed y con `total:5` de la página).

## Notas

- El ítem «forzar un fallo en la ficha → `SELECT count(*)` no crece» (§7, auto-registro) no se ejecutó
  en runtime: implica un `POST` de escritura (aunque revierta). Se validó por inspección del bloque
  único `async with` con el `except` fuera; queda como evidencia de C-12.
- Ítems cuyo cumplimiento integral pertenece a changes posteriores (venta transaccional, stock único,
  eventos, códigos de la tabla de endpoints) se marcaron PASS con la evidencia de inspección
  disponible; sus auditorías dedicadas (C-08, C-09, C-15, C-16) los cubren en runtime.
