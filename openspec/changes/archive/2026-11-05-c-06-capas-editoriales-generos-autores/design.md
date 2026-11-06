# Design — C-06 capas-editoriales-generos-autores

## Context

Ver `proposal.md` — Why. El estado actual (C-05 cerrado) deja `BaseRepository`,
`UnitOfWork` y `paginar()` listos en `app/core/`, y los tres módulos con `models`,
`schemas`, `service` y `router` del TP cap. 1-4, donde el servicio recibe
`AsyncSession`, escribe con `session.add(...)` y el router confirma con
`session.commit()`. No existe aún ningún `repository.py` ni `unit_of_work.py` a nivel
de módulo. Las migraciones 0001-0004 ya están aplicadas; no hay cambios de esquema.

## Goals / Non-Goals

**Goals:**

- Migrar `editoriales`, `generos` y `autores` al patrón de seis capas con el router
  construyendo el UoW y el servicio abriéndolo (`CV-01`).
- Establecer el **molde** que copiarán `C-07` … `C-10` y `C-15`: repository + UoW +
  service sin `AsyncSession` + router con dependencia de UoW.
- Mantener el contrato HTTP ya fijado por C-05 (201/200/404/409/422, envoltorio,
  `exclude_unset`, mensajes propios).
- Garantizar `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py` vacío y
  precarga exclusiva en `repository.py` (`CV-02`).

**Non-Goals:**

- No se tocan `models.py` ni `schemas.py` (ya correctos por C-01/C-05).
- No se agregan migraciones ni se cambia el esquema.
- `generos` no recibe `PATCH` (el scope de C-06 sólo cubre `PATCH` en editorial y autor).
- No se implementa autenticación ni autorización (llega con `C-11` … `C-13`): los
  endpoints quedan públicos como hasta ahora.
- No se tocan los módulos `libros`, `clientes`, `ventas`, `usuarios`.

## Decisions

### D-1: Dependencia de UoW en el router

- **Decisión**: cada módulo expone una función de dependencia
  `get_<modulo>_uow(request) -> <Modulo>UnitOfWork` que toma la sesión de
  `get_session` (o la recibe por parámetro) e instancia el UoW con ella. El router la
  declara como `uow: <Modulo>UnitOfWork = Depends(get_<modulo>_uow)`.
- **Alternativa**: construir el UoW directamente en el handler con
  `Depends(get_session)` y un wrapper. Se descarta porque la convención del repo
  (C-02, `CV-01`) es que el router construye el UoW con una dependencia y lo pasa
  sin abrirlo.
- **Rationale**: centraliza la construcción, facilita los tests con
  `dependency_overrides` y deja el handler limpio.

### D-2: Repositorio por entidad, sin precarga en la base

- **Decisión**: `EditorialRepository(BaseRepository[Editorial])`,
  `GeneroRepository(BaseRepository[Genero])`, `AutorRepository(BaseRepository[Autor])`,
  todos con constructor `(session, Model)`. La precarga (`selectinload`) se declara
  **adentro del método que la necesita** (por ejemplo, `AutorRepository` no precarga
  nada en `get_by_id`, pero el método `libros_de` hace el `join` a `LibroAutor`/
  `Libro` dentro del repositorio). Ningún `selectinload` fuera de `repository.py`.
- **Alternativa**: un repositorio genérico compartido entre los tres. Se descarta
  porque cada entidad tiene consultas propias (listado de libros por autor/editorial/
  género) y el molde debe mostrar un repositorio por entidad para que C-08 (libros)
  y C-10 (ventas) lo copien con sus propias consultas.
- **Rationale**: respeta `CV-02` y deja el patrón claro para los módulos siguientes.

### D-3: Servicio sin `AsyncSession`

- **Decisión**: cada `service.py` recibe el UoW como primer parámetro y lo abre con
  `async with uow:`. Dentro usa `uow.<repo>` para consultar/escribir y
  `uow.<repo>.add/update` (que hacen `flush()`). La traducción de `IntegrityError`
  se hace en el bloque `try/except` **al salir** del `async with` (o dentro, capturando
  y re-lanzando), de modo que el rollback lo hace el `__aexit__` del UoW.
- **Importante**: el `IntegrityError` se captura **después** de que el `async with`
  revirtió, por lo que no se llama a `session.rollback()` desde el servicio. Se invoca
  `traducir_integrity_error(exc)` y se lanza la `HTTPException` resultante.
- **Orden de errores** (`CV-08`): 404 (existencia del recurso de la ruta) → 403 (no
  aplica acá, sin auth) → 409 (unicidad/conflicto, incluida la traducción de
  `IntegrityError`) → 422 (contrato, resuelto por el schema antes de entrar).
- **Rationale**: mantiene la frontera de transacción en un solo `async with` y evita
  doble commit/rollback.

### D-4: Actualización parcial

- **Decisión**: el servicio carga la entidad con `uow.<repo>.get_by_id(id)` (404 si
  `None`), aplica `data.model_dump(exclude_unset=True)` con `setattr`, hace
  `await uow.<repo>.update(obj)` (flush) dentro del `async with`. La unicidad se
  garantiza por la base; un choque sale como `IntegrityError` y se traduce a 409.
- **Rationale**: coincide con C-05 (`exclude_unset`) y con el orden `CV-08`.

### D-5: Listado de libros por entidad

- **Decisión**: se agrega un método en cada repositorio
  (`EditorialRepository.libros_de(editorial_id)`, etc.) que verifica existencia de la
  entidad (404 en el servicio) y consulta los libros con `borrado_en IS NULL` y el FK
  correspondiente. La precarga (editorial/género/autor del libro) se declara adentro
  del método del repositorio. El router mapea cada `Libro` a `LibroRead` vía el
  helper existente (o un `to_read` en el módulo de libros), sin precarga en el router.
- **Rationale**: respeta `CV-02` y reusa el filtro de borrado lógico de `SoftDelete`
  (la consulta filtra `borrado_en IS NULL` directamente, ya que `Libro` no usa
  `SoftDeleteRepository` en este change; se deja para C-08).

### D-6: Mapeo de `Libro` a `LibroRead`

- **Decisión**: se reusa el helper `to_read` del módulo `libros` si existe; si no, se
  construye el `LibroRead` en el router a partir de los atributos ya cargados. No se
  agrega precarga fuera de `repository.py`.
- **Rationale**: evita duplicar lógica de serialización; el módulo `libros` es el
  dueño de su schema.

## Risks / Trade-offs

- [El molde queda mal y se replica] → Se mitiga con la verificación
  `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py` vacío y con la
  precarga exclusiva en `repository.py` (`CV-02`), más la revisión del patrón antes
  de archivar.
- [Doble rollback/commit] → El servicio captura `IntegrityError` sin llamar a
  `session.rollback()`; el rollback lo hace el `__aexit__` del UoW. Se documenta en
  el código.
- [El listado de libros por autor/editorial/género no excluye borrados] → El método
  del repositorio filtra `borrado_en IS NULL` explícitamente; se cubre con escenario
  en la spec.
- [Dependencia de `get_session` dentro del UoW] → La función de dependencia del UoW
  recibe la sesión ya creada por `get_session` y la pasa al UoW; no se crea una
  segunda sesión.

## Migration Plan

No hay cambios de esquema ni de datos. El change es aditivo/refactor sobre
`app/modules/{editoriales,generos,autores}/`. Rollback: revertir los archivos
modificados (los `models.py` y `schemas.py` no cambian, por lo que no hay riesgo de
esquema). No se requiere `alembic upgrade/downgrade`.

## Open Questions

Ninguna que afecte specs, enfoque ni desglose de tareas. El helper `to_read` de
`libros` se verifica al implementar (C-08 completará el módulo de libros); si no
existe, se construye el `LibroRead` en el router a partir de los atributos cargados.