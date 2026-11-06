# Design — C-08 capas-libros-alta-stock-inicial

## Context

Ver `proposal.md` — Why. El estado actual (C-05 y C-06 cerrados, C-07 cerrado) deja
`BaseRepository`, `SoftDeleteRepository`, `UnitOfWork` y `paginar()` listos en `app/core/`,
y `editoriales`/`generos`/`autores`/`clientes` refactorizados a seis capas (molde C-06/C-07).
`libros` sigue con el patrón anterior del TP cap. 1-4: el servicio recibe `AsyncSession`,
escribe con `session.add(...)` y el router confirma con `session.commit()`, y la precarga
(`selectinload`/`joinedload`) vive en el servicio. Las migraciones 0001-0004 ya están
aplicadas; no hay cambios de esquema. El modelo `Libro` ya tiene `borrado_en` + índice
parcial del ISBN, `CHECK (precio > 0)` y `CHECK (stock >= 0)`; `MovimientoStock` ya tiene
`CHECK (cantidad <> 0)` y el disparador append-only (C-04).

## Goals / Non-Goals

**Goals:**

- Migrar `libros` al patrón de seis capas con el router construyendo el UoW y el
  servicio abriéndolo (`CV-01`), reusando el molde de C-06/C-07.
- Establecer `LibroRepository(SoftDeleteRepository[Libro])` con filtro de borrados por
  defecto y precarga de editorial/género/autores **declarada adentro del método que la
  necesita** (`CV-02`), más búsqueda por título con `ilike` y parámetro ligado.
- Definir el **punto único de escritura de stock**: un solo método que actualiza
  `libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar (`RN-11`), con
  motivos `'Stock inicial'`, `'Reposición'`, `'Venta'` (`RD-02`).
- `POST /libros` con `stock_inicial` (no `stock`) y autores anidados: libro +
  `libro_autor` + movimiento «Stock inicial» en **un** `async with`; `201`/`409`/`422`.
- `PATCH /libros/{id}` sólo título y precio; mandar `stock` → `422`.
- `GET /libros` paginado con filtro por título y género, excluyendo borrados; búsqueda
  con parámetro ligado (`' OR '1'='1` no rompe).
- Garantizar `grep -rn "AsyncSession\|UnitOfWork(" app/modules/libros/service.py` vacío
  y precarga exclusiva en `repository.py` (`CV-02`).

**Non-Goals:**

- No se tocan `models.py` (ya correctos por C-03) ni se agregan migraciones.
- No se implementa baja lógica, reposición ni movimientos (C-09); el repositorio ya
  filtra borrados por defecto y expone `get_by_id_including_deleted` heredado para
  C-10/C-16.
- No se implementa autenticación ni autorización en este change (llega con C-11 …
  C-13): los endpoints quedan preparados para recibir `requiere_rol('ADMIN')` cuando
  esté disponible; hasta entonces el punto de decisión se documenta y se cablea en C-13
  sin cambiar la firma.
- No se tocan los módulos `editoriales`, `generos`, `autores`, `clientes`, `ventas`,
  `usuarios`.

## Decisions

### D-1: Dependencia de UoW en el router

- **Decisión**: el módulo expone `get_libros_uow(session) -> LibrosUnitOfWork` que
  recibe la sesión de `get_session` e instancia el UoW con ella. El router la declara
  como `uow: LibrosUnitOfWork = Depends(get_libros_uow)`.
- **Rationale**: centraliza la construcción, facilita los tests con
  `dependency_overrides` y deja el handler limpio (`CV-01`).

### D-2: Repositorio con filtro de borrados por defecto y precarga por método

- **Decisión**: `LibroRepository(SoftDeleteRepository[Libro])` con constructor
  `(session, Libro)`. Hereda el filtro `borrado_en IS NULL` de `SoftDeleteRepository`
  para `get_by_id`/`get_all`/`count`. La precarga de editorial/género/autores se
  declara **adentro del método que la necesita**:
  - `get_by_id` hace `selectinload(Libro.editorial)`, `selectinload(Libro.genero)`,
    `selectinload(Libro.autorias).selectinload(LibroAutor.autor)`.
  - `listar` (con filtros) precarga editorial y género (no autores, para no
    multiplicar consultas en el listado).
  - `buscar_por_titulo` usa `ilike` con parámetro ligado (`Libro.titulo.ilike(f"%{titulo}%")`
    es un bind param, no concatenación) y precarga editorial/género.
- **Alternativa**: precargar siempre autores en todos los métodos. Se descarta porque la
  precarga debe ser la mínima necesaria por método (`CV-02`); el listado no expone
  autores.
- **Rationale**: respeta `CV-02` y evita cargar relaciones que no se usan.

### D-3: Punto único de escritura de stock

- **Decisión**: un solo método `aplicar_movimiento(libro, cantidad, motivo, usuario_id, venta_id=None)`
  en `LibroRepository` (o en el servicio, pero centralizado) que:
  1. hace `libro.stock += cantidad` (la instancia ya cargada),
  2. crea `MovimientoStock(libro_id=libro.id, venta_id=venta_id, usuario_id=usuario_id,
     cantidad=cantidad, motivo=motivo)`,
  3. hace `flush()` de ambos en el mismo lugar.
  Los tres caminos (alta con stock inicial, reposición en C-09, venta en C-16) llaman a
  este método. **No existe** otro lugar que toque `libro.stock`.
- **Rationale**: `RN-11` exige que no haya forma de escribir uno sin el otro; centralizar
  en un método del repositorio garantiza el invariante `stock = SUM(movimiento_stock.cantidad)`.

### D-4: Alta de libro con stock inicial

- **Decisión**: `crear(uow, data, usuario_actual)`:
  1. (cuando C-13 esté disponible) comprobar rol `ADMIN` → 403/401; por ahora se deja el
     punto de decisión documentado y el parámetro `usuario_actual` opcional.
  2. Validación de contrato por el schema (`precio > 0`, `stock_inicial >= 0`,
     `autores` con `orden >= 1`, `rol` válido) → 422 antes de entrar.
  3. `async with uow`:
     - `libro = Libro(isbn=..., titulo=..., precio=..., stock=stock_inicial,
       editorial_id=..., genero_id=...)`; `await uow.libros.add(libro)` (flush → id).
     - por cada autor: `LibroAutor(libro_id=libro.id, autor_id=..., rol=..., orden=...)`;
       `await uow.libros.add_autoria(...)` o `session.add` + flush.
     - punto único: `await uow.libros.aplicar_movimiento(libro, stock_inicial,
       'Stock inicial', usuario_id, venta_id=None)`.
     - Si el ISBN choca con un libro vigente → `IntegrityError` del índice parcial
       `uq_libro_isbn_vigente` → `traducir_integrity_error` → 409.
     - Si una FK (editorial/género/autor) no existe → `IntegrityError` → 409.
  4. Tras el `async with`, devolver el libro recargado con precarga.
- **Rationale**: una sola transacción para las tres escrituras (`RN-11`); el índice parcial
  garantiza la unicidad entre vigentes (`RN-01`/`RN-13`), no una consulta previa.

### D-5: Actualización parcial

- **Decisión**: `actualizar(uow, libro_id, data)` carga la entidad con
  `uow.libros.get_by_id(id)` (404 si `None`), aplica `data.model_dump(exclude_unset=True)`
  con `setattr` (sólo `titulo` y `precio` están en el schema; mandar `stock` da 422 por
  `extra="forbid"` antes de entrar), hace `await uow.libros.update(obj)` (flush) dentro
  del `async with`. La unicidad no aplica (ISBN no se modifica); el `CHECK (precio > 0)`
  se garantiza por el schema y la base.
- **Rationale**: coincide con C-05 (`exclude_unset`) y con el orden `CV-08`.

### D-6: Listado y búsqueda

- **Decisión**: `listar(uow, page, size, titulo, genero_id)`:
  - `stmt = select(Libro)` con precarga de editorial y género.
  - si `titulo` (no vacío): `stmt = stmt.where(Libro.titulo.ilike(f"%{titulo}%"))`
    (bind param, no concatenación).
  - si `genero_id is not None`: `stmt = stmt.where(Libro.genero_id == genero_id)`.
  - delegar a `paginar(uow.session, stmt, page, size)`.
  - `SoftDeleteRepository` ya filtra `borrado_en IS NULL` en `get_all`/`count`? El
    listado usa `paginar` sobre un `select` directo, por lo que **hay que agregar**
    `.where(Libro.borrado_en.is_(None))` explícitamente en el stmt (o un helper del
    repositorio). Se documenta en el código.
- **Búsqueda**: el `ilike` con parámetro ligado hace que `' OR '1'='1` se trate como
  texto literal y no rompa ni devuelva todo (`RN-15`).
- **Rationale**: reusa `paginar()` (C-02/C-05); el filtro de borrados se aplica en la
  consulta (`SoftDeleteRepository` no cubre selects arbitrarios).

### D-7: Schemas

- **Decisión**:
  - `LibroCreate`: `isbn`, `titulo`, `precio: Decimal (gt=0)`, `stock_inicial: int (ge=0)`,
    `editorial_id`, `genero_id: Optional[int]`, `autores: List[LibroAutorCreate]`.
    **No** tiene campo `stock`.
  - `LibroUpdate`: `titulo: Optional[str]`, `precio: Optional[Decimal] (gt=0)`. **No**
    tiene `stock` ni `isbn` ni `editorial_id`/`genero_id` (sólo título y precio, scope).
  - `LibroRead`/`LibroDetailRead`: incluyen `stock` (lectura) y `autores` en el detalle.
  - `LibroAutorCreate`: `autor_id`, `rol` (validado por CHECK de base), `orden (ge=1)`.
  - `LibroAutorRead`: `autor_id`, `rol`, `orden`, `autor_nombre: Optional[str]`.
- **Rationale**: el contrato fija que mandar `stock` → 422 (`extra="forbid"`); la unicidad
  del ISBN y las FKs se garantizan por la base, no por consulta previa.

### D-8: Mapeo de `Libro` a `LibroRead`/`LibroDetailRead`

- **Decisión**: el router mapea cada `Libro` a los schemas reusando helpers del servicio
  (`to_read`, `to_detail_read`), construyendo `EditorialRef`/`GeneroRef` y la lista de
  autores a partir de las relaciones ya precargadas. No se agrega precarga fuera de
  `repository.py`.
- **Rationale**: evita duplicar lógica de serialización; el módulo es dueño de su schema.

### D-9: Autorización (punto de decisión)

- **Decisión**: `POST /libros` es de `ADMIN` (`requiere_rol('ADMIN')`); `PATCH` y las
  lecturas públicas no requieren rol (catálogo público). Hasta que `requiere_rol` esté
  disponible (C-11/C-13), el servicio deja el parámetro `usuario_actual` opcional y el
  punto de decisión documentado; el cableado se completa en C-13 sin cambiar la firma.
- **Rationale**: coincide con el patrón de C-07 (`GET /clientes/{id}/ventas`).

## Risks / Trade-offs

- [El stock se escribe por fuera del punto único] → Se mitiga centralizando la escritura
  en un solo método del repositorio y con la verificación de la capa; además, el
  `grep` de la capa busca `stock =` / `stock +=` fuera de `repository.py`.
- [Doble rollback/commit] → El servicio captura `IntegrityError` sin llamar a
  `session.rollback()`; el rollback lo hace el `__aexit__` del UoW. Se documenta en el
  código.
- [Filtro de borrados en listados arbitrarios] → `paginar` sobre un `select` directo no
  filtra borrados automáticamente; se agrega `.where(Libro.borrado_en.is_(None))`
  explícito en el stmt. Se documenta en el código para que C-09 no lo olvide.
- [Autorización de `POST /libros`] → El `401`/`403` depende de C-11/C-13. Se deja el
  punto de decisión en el servicio y se cablea cuando estén disponibles, sin cambiar la
  firma.
- [`ilike` con concatenación] → Se usa bind param (`Libro.titulo.ilike(f"%{titulo}%")`
  es un bind param en SQLAlchemy), no concatenación SQL. Se verifica con
  `' OR '1'='1` → lista vacía o resultados literales, nunca error.

## Migration Plan

No hay cambios de esquema ni de datos. El change es aditivo/refactor sobre
`app/modules/libros/`. Rollback: revertir los archivos modificados (los `models.py` no
cambian, por lo que no hay riesgo de esquema). No se requiere
`alembic upgrade/downgrade`.

## Open Questions

Ninguna que afecte specs, enfoque ni desglose de tareas. El helper de serialización
de `Libro` se mantiene en el servicio (`to_read`, `to_detail_read`); si C-09/C-10
necesitan más campos (movimientos, renglones), extienden el schema sin romper el de
C-08.