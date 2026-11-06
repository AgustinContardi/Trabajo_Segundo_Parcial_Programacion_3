# Design — C-10 capas-ventas-lecturas

## Context

Ver `proposal.md` — Why. El estado actual (C-05…C-09 cerrados) deja `BaseRepository`,
`UnitOfWork` y `paginar()` listos en `app/core/`, y `editoriales`/`generos`/`autores`/
`clientes`/`libros` refactorizados a seis capas (molde C-06…C-09). `ventas` sigue con
el patrón anterior del TP cap. 1-4: el servicio recibe `AsyncSession`, escribe con
`session.add(...)`, el router confirma con `session.commit()` y la precarga
(`selectinload`/`joinedload`) vive en el servicio. Las migraciones 0001-0004 ya están
aplicadas; no hay cambios de esquema. El modelo `Venta`/`RenglonVenta` ya tiene las
relaciones y las FKs con índice por C-01/C-03.

## Goals / Non-Goals

**Goals:**

- Migrar `ventas` al patrón de seis capas con el router construyendo el UoW y el
  servicio abriéndolo (`CV-01`), reusando el molde de C-06…C-09.
- Establecer `VentaRepository` con precarga de `cliente`, `renglones` y el `libro` de
  cada renglón —**incluidos los dados de baja**— **declarada adentro del método que la
  necesita** (`CV-02`), con número de consultas **fijo** (caso C-15).
- Mantener el contrato HTTP ya fijado por C-05 (200/403/404/422, envoltorio,
  `exclude_unset` donde aplica, mensajes propios) para las lecturas.
- Implementar `GET /ventas`, `GET /ventas/{id}` (sin `requiere_rol`, decisión en el
  servicio) y `GET /mis-ventas` (sólo sesión).
- Garantizar `grep -rn "AsyncSession\|UnitOfWork(" app/modules/ventas/service.py` vacío
  y precarga exclusiva en `repository.py` (`CV-02`).

**Non-Goals:**

- No se tocan `models.py` (ya correctos por C-01/C-03) ni se agregan migraciones.
- No se implementa la alta transaccional `POST /ventas` (llega con C-16): C-10 no
  implementa ni redefine la creación; reusa el schema `VentaCreate` existente y deja
  el punto de entrada para C-16.
- No se implementa autenticación ni autorización en este change (llega con C-11…C-13):
  los endpoints quedan preparados para recibir el usuario actual, pero el `403` de
  `GET /ventas/{id}` para quien no es personal ni dueño y la sesión de `/mis-ventas`
  se cablean cuando `get_usuario_actual`/`requiere_rol` estén disponibles.
- No se tocan los módulos `libros`, `clientes`, `usuarios`.

## Decisions

### D-1: Dependencia de UoW en el router

- **Decisión**: el módulo expone `get_ventas_uow(session) -> VentasUnitOfWork` que
  recibe la sesión de `get_session` e instancia el UoW con ella. El router la declara
  como `uow: VentasUnitOfWork = Depends(get_ventas_uow)`.
- **Rationale**: centraliza la construcción, facilita los tests con
  `dependency_overrides` y deja el handler limpio (convención C-02/C-06, `CV-01`).

### D-2: Repositorio con precarga fija (sin N+1)

- **Decisión**: `VentaRepository(BaseRepository[Venta])` con constructor `(session, Venta)`.
  La precarga se declara **adentro** del método que la necesita:
  - `get_by_id(id)`: `selectinload(Venta.cliente)` + `selectinload(Venta.renglones).selectinload(RenglonVenta.libro)`.
    El `selectinload` anidado hace un `SELECT` por nivel y **no** filtra los libros
    dados de baja, de modo que una venta vieja sigue mostrando el título (RN-13). Número
    de consultas **fijo** (3 `SELECT`), independiente de la cantidad de renglones.
  - `listar(page, size)`: `selectinload(Venta.cliente)` sobre `Venta`, ordenado por
    `id` descendente (orden estable), delegando a `paginar()`. No precarga renglones ni
    libros (el listado devuelve `VentaRead` resumen).
  - `ventas_de_cliente(cliente_id, page, size)`: `Venta` filtrado por `cliente_id`,
    con `selectinload(Venta.cliente)`, delegando a `paginar()`.
- **Alternativa**: `joinedload` anidado. Se descarta porque multiplica filas cuando hay
  varios renglones (N+1 aparente y payload grande) y rompe el caso C-15.
- **Rationale**: `selectinload` por nivel garantiza cardinalidad fija de consultas y es
  la única forma de cumplir C-15 (misma cantidad con 2 y con 4 renglones).

### D-3: Servicio sin `AsyncSession`

- **Decisión**: cada función del `service.py` recibe el UoW como primer parámetro y lo
  abre con `async with uow:`. Dentro usa `uow.ventas` para consultar y `uow.clientes`
  para resolver `usuario_id → cliente`. La traducción de `IntegrityError` se hace
  capturando la excepción **después** de que el `async with` revirtió, sin llamar a
  `session.rollback()` desde el servicio.
- **Orden de errores** (`CV-08`): 404 (existencia del recurso de la ruta) → 403
  (autorización/propiedad) → 409 (unicidad/conflicto) → 422 (contrato, resuelto por el
  schema antes de entrar).
- **Rationale**: mantiene la frontera de transacción en un solo `async with` y evita
  doble commit/rollback.

### D-4: Detalle de venta (`GET /ventas/{id}`)

- **Decisión**: el servicio carga la venta con `uow.ventas.get_by_id(id)` (404 si
  `None`). Si quien pide es personal (`VENDEDOR`/`ADMIN`, cuando `get_usuario_actual`
  esté disponible) o el dueño (el `cliente_id` de la venta coincide con el cliente
  ligado al usuario actual) → 200. En caso contrario → **403** (`RN-14`). El router
  mapea la venta precargada a `VentaDetailRead`, leyendo `r.libro.titulo` sin acceder a
  la base (ya cargado, incluidos los dados de baja).
- **Rationale**: la decisión de propiedad es de negocio (`RN-14`), no de rol en la
  ruta; por eso `GET /ventas/{id}` **no** lleva `requiere_rol`. El número 403 (y no
  404) para lo ajeno es el que fija la consigna.

### D-5: Listado (`GET /ventas`)

- **Decisión**: `listar(page, size)` delega a `VentaRepository.listar` y mapea cada
  `Venta` a `VentaRead` con `ClienteRef` a partir del cliente ya cargado. Lleva
  `requiere_rol('VENDEDOR','ADMIN')` (cuando esté disponible); sin sesión → 401.
- **Rationale**: reusa `paginar()` (C-02/C-05) y el patrón de C-07.

### D-6: Mis ventas (`GET /mis-ventas`)

- **Decisión**: el servicio resuelve el cliente ligado al usuario actual
  (`cliente.usuario_id = usuario.id`); si no existe ficha → página vacía (`SU-05`);
  si existe → `VentaRepository.ventas_de_cliente(cliente_id, page, size)`. La ruta
  sólo pide estar autenticado (`RN-14`), no un rol. Sin cookie → 401 (lo decide
  `get_usuario_actual`).
- **Rationale**: «lo propio sólo pide estar autenticado»; un `VENDEDOR`/`ADMIN` sin
  ficha de cliente ve una página vacía, no un error.

### D-7: `VentasUnitOfWork` compone repositorios con la misma sesión

- **Decisión**: `VentasUnitOfWork(UnitOfWork)` compone `VentaRepository` y
  `ClienteRepository` (este último para resolver `usuario_id → cliente` en `GET /ventas/{id}`
  y `/mis-ventas`), pasándoles la **misma** sesión recibida. C-16 extenderá este UoW
  con `LibroRepository` y el punto único de stock de C-08.
- **Rationale**: una sola sesión por petición (C-02); la composición de repositorios en
  el UoW es el patrón de C-02/C-06…C-09.

### D-8: Sin `PATCH /ventas/{id}`

- **Decisión**: no se registra ninguna ruta `PATCH` sobre `/ventas/{id}`. Las ventas no
  se modifican (`RN-09`). El schema `VentaUpdate` no se crea.
- **Rationale**: `RN-09` lo fija; C-16 tampoco agrega PATCH.

## Risks / Trade-offs

- [Precarga que crece con los renglones (N+1)] → Se mitiga con `selectinload` anidado
  declarado en el repositorio y contando `SELECT` con `SQL_ECHO=true` (caso C-15).
- [Precarga que filtra los libros dados de baja] → `selectinload(RenglonVenta.libro)` no
  aplica filtro de borrados; se verifica con el caso C-06 (detalle muestra el título de
  un libro dado de baja).
- [Doble rollback/commit] → El servicio captura `IntegrityError` sin llamar a
  `session.rollback()`; el rollback lo hace el `__aexit__` del UoW. Se documenta en el
  código.
- [Autorización de `GET /ventas` y `GET /ventas/{id}`] → `requiere_rol` y
  `get_usuario_actual` llegan con C-11/C-13. Se deja el punto de decisión en el
  servicio y se cablea cuando estén disponibles, sin cambiar la firma. `GET /ventas`
  lleva `requiere_rol('VENDEDOR','ADMIN')`; `GET /ventas/{id}` no lleva `requiere_rol`.
- [Sesión de `/mis-ventas`] → depende de C-11; se cablea en C-13.

## Migration Plan

No hay cambios de esquema ni de datos. El change es aditivo/refactor sobre
`app/modules/ventas/`. Rollback: revertir los archivos modificados (los `models.py` no
cambian, por lo que no hay riesgo de esquema). No se requiere `alembic upgrade/downgrade`.

## Open Questions

Ninguna que afecte specs, enfoque ni desglose de tareas. El punto de escritura de stock
de C-08 (`aplicar_movimiento`) no se toca en C-10 (no hay escrituras de stock en las
lecturas); C-16 lo reusará. El helper de serialización de `Venta` se reusa del módulo
(`VentaRead`, `VentaDetailRead`, `ClienteRef`, `RenglonRead`); si no cubre algún campo,
se construye en el router a partir de los atributos cargados.