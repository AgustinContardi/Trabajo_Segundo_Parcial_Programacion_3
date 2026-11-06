# Design — C-07 capas-clientes-y-perfil

## Context

Ver `proposal.md` — Why. El estado actual (C-05 y C-06 cerrados) deja `BaseRepository`,
`UnitOfWork` y `paginar()` listos en `app/core/`, y `editoriales`/`generos`/`autores`
refactorizados a seis capas (molde C-06). `clientes` sigue con el patrón anterior del
TP cap. 1-4: el servicio recibe `AsyncSession`, escribe con `session.add(...)` y el
router confirma con `session.commit()`, y la precarga (`selectinload`) vive en el
servicio. Las migraciones 0001-0004 ya están aplicadas; no hay cambios de esquema. El
modelo `Cliente` ya tiene `usuario_id` nulo + `UNIQUE` y la navegación en los dos
extremos por C-03; `PerfilCliente` ya tiene `cliente_id` `UNIQUE` 1—1.

## Goals / Non-Goals

**Goals:**

- Migrar `clientes` al patrón de seis capas con el router construyendo el UoW y el
  servicio abriéndolo (`CV-01`), reusando el molde de C-06.
- Establecer `ClienteRepository` con precarga de `perfil` y `usuario` **declarada
  adentro del método que la necesita** (`CV-02`), y un método `ventas_de(...)` que
  pagina las ventas del cliente.
- Mantener el contrato HTTP ya fijado por C-05 (201/200/404/409/422, envoltorio,
  `exclude_unset`, mensajes propios) y agregar paginación a
  `GET /clientes/{id}/ventas`.
- Garantizar `grep -rn "AsyncSession\|UnitOfWork(" app/modules/clientes/service.py`
  vacío y precarga exclusiva en `repository.py` (`CV-02`).

**Non-Goals:**

- No se tocan `models.py` (ya correctos por C-03) ni se agregan migraciones.
- `POST /clientes` no crea usuario ni rol: el cliente de mostrador nace sin acceso web;
  el auto-registro atómico llega con C-12.
- No se implementa autenticación ni autorización en este change (llega con C-11 …
  C-13): los endpoints quedan preparados para recibir el usuario actual, pero la
  comprobación de `403` para `CLIENTE` en `GET /clientes/{id}/ventas` se cablea cuando
  `get_usuario_actual`/`requiere_rol` estén disponibles.
- No se tocan los módulos `libros`, `ventas`, `usuarios`.

## Decisions

### D-1: Dependencia de UoW en el router

- **Decisión**: el módulo expone `get_clientes_uow(session) -> ClientesUnitOfWork`
  que recibe la sesión de `get_session` e instancia el UoW con ella. El router la
  declara como `uow: ClientesUnitOfWork = Depends(get_clientes_uow)`.
- **Alternativa**: construir el UoW directamente en el handler con
  `Depends(get_session)` y un wrapper. Se descarta porque la convención del repo
  (C-02, `CV-01`) es que el router construye el UoW con una dependencia y lo pasa
  sin abrirlo.
- **Rationale**: centraliza la construcción, facilita los tests con
  `dependency_overrides` y deja el handler limpio.

### D-2: Repositorio con precarga declarada en el método que la necesita

- **Decisión**: `ClienteRepository(BaseRepository[Cliente])` con constructor
  `(session, Cliente)`. La precarga de `perfil` y `usuario` se declara **adentro**
  del método que la necesita (`get_by_id` hace `selectinload(Cliente.perfil)` y
  `selectinload(Cliente.usuario)`; `ventas_de` no precarga cliente/perfil porque la
  consulta es sobre `Venta`). Ningún `selectinload` fuera de `repository.py`.
- **Alternativa**: precargar siempre `perfil` y `usuario` en `get_by_id`. Se descarta
  parcialmente porque la precarga debe ser la mínima necesaria por método (`CV-02`);
  en este módulo `get_by_id` sí las necesita (consulta y edición con perfil), pero
  otros métodos (como `ventas_de`) no.
- **Rationale**: respeta `CV-02` y evita cargar relaciones que no se usan.

### D-3: Servicio sin `AsyncSession`

- **Decisión**: cada función del `service.py` recibe el UoW como primer parámetro y lo
  abre con `async with uow:`. Dentro usa `uow.clientes` para consultar/escribir y
  `uow.clientes.add/update` (que hacen `flush()`). La traducción de `IntegrityError`
  se hace capturando la excepción **después** de que el `async with` revirtió, sin
  llamar a `session.rollback()` desde el servicio; se invoca
  `traducir_integrity_error(exc)` y se lanza la `HTTPException` resultante.
- **Orden de errores** (`CV-08`): 404 (existencia del recurso de la ruta) → 403
  (autorización, cuando esté disponible) → 409 (unicidad/conflicto, incluida la
  traducción de `IntegrityError`) → 422 (contrato, resuelto por el schema antes de
  entrar).
- **Rationale**: mantiene la frontera de transacción en un solo `async with` y evita
  doble commit/rollback.

### D-4: Actualización parcial

- **Decisión**: el servicio carga la entidad con `uow.clientes.get_by_id(id)` (404 si
  `None`), aplica `data.model_dump(exclude_unset=True)` con `setattr`, hace
  `await uow.clientes.update(obj)` (flush) dentro del `async with`. La unicidad se
  garantiza por la base; un choque sale como `IntegrityError` y se traduce a 409.
- **Rationale**: coincide con C-05 (`exclude_unset`) y con el orden `CV-08`.

### D-5: Alta de perfil (1—1)

- **Decisión**: `crear_perfil` primero verifica que el cliente exista (404), luego
  verifica que no tenga perfil (409, consultando `uow.clientes.get_by_id` que precarga
  `perfil`, o un método dedicado). Si pasa, crea `PerfilCliente(cliente_id=..., ...)`
  y hace `add` + `flush` dentro del `async with`. La unicidad `perfil_cliente.cliente_id`
  es el garante final; un choque por concurrencia se traduce a 409.
- **Rationale**: doble barrera (consulta previa + constraint de base) y un solo
  `async with`.

### D-6: Ventas del cliente paginadas

- **Decisión**: se agrega `ClienteRepository.ventas_de(cliente_id, page, size)` que
  consulta `Venta` filtrando por `cliente_id`, ordena por `id` (o `fecha`) y delega a
  `paginar(session, stmt, page, size)`. La precarga de cliente/renglones/libro **no**
  se hace acá (el listado devuelve `VentaRead` resumen); si se quisiera detalle, se
  carga en el router a partir de los atributos ya disponibles.
- **Autorización**: `GET /clientes/{id}/ventas` es de personal (VENDEDOR/ADMIN); un
  `CLIENTE` recibe `403` (`RN-14`). El servicio decide: si el usuario actual está
  presente y tiene sólo rol `CLIENTE` (y no es personal), lanza `403`. Hasta que
  `get_usuario_actual`/`requiere_rol` existan (C-11/C-13), el endpoint se implementa
  con un parámetro opcional `actual` y el punto de decisión documentado; el cableado se
  completa en C-13 sin cambiar la firma del servicio.
- **Rationale**: reusa `paginar()` (C-02/C-05) y deja la autorización como decisión
  de servicio (`RN-14`), no de rol en la ruta.

### D-7: Mapeo de `Venta` a `VentaRead`

- **Decisión**: el router mapea cada `Venta` a `VentaRead` reusando el schema del
  módulo `ventas` (`VentaRead`, `ClienteRef`), construyendo el `ClienteRef` a partir
  del cliente ya cargado para el `404`. No se agrega precarga fuera de
  `repository.py`.
- **Rationale**: evita duplicar lógica de serialización; el módulo `ventas` es el
  dueño de su schema.

### D-8: `ClienteRead` incluye `usuario_id`

- **Decisión**: `ClienteRead` agrega `usuario_id: Optional[int] = None` (y
  `ClienteDetailRead` lo hereda) para que `POST /clientes` pueda responder `201` con
  `usuario_id` nulo, conforme al scope. `usuario` (objeto) no se expone en la API;
  la navegación es a nivel ORM (`CV-03`/modelo).
- **Rationale**: el scope exige ver `usuario_id` nulo en la respuesta; exponer el
  objeto completo filtraría datos y no está pedido.

## Risks / Trade-offs

- [El molde queda mal y se replica] → Se mitiga con la verificación
  `grep -rn "AsyncSession\|UnitOfWork(" app/modules/clientes/service.py` vacío y con la
  precarga exclusiva en `repository.py` (`CV-02`), más la revisión del patrón antes de
  archivar.
- [Doble rollback/commit] → El servicio captura `IntegrityError` sin llamar a
  `session.rollback()`; el rollback lo hace el `__aexit__` del UoW. Se documenta en
  el código.
- [`usuario_id` UNIQUE con múltiples NULL] → PostgreSQL admite múltiples `NULL` en un
  `UNIQUE`, que es exactamente lo que se quiere para clientes de mostrador. Se verifica
  con escenario en la spec.
- [Autorización de `GET /clientes/{id}/ventas`] → El `403` para `CLIENTE` depende de
  C-11/C-13. Se deja el punto de decisión en el servicio y se cablea cuando estén
  disponibles, sin cambiar la firma.
- [`ventas_de` sin precarga de renglones] → El listado devuelve resumen (`VentaRead`);
  si se requiere detalle, se carga aparte. Se documenta como límite.

## Migration Plan

No hay cambios de esquema ni de datos. El change es aditivo/refactor sobre
`app/modules/clientes/`. Rollback: revertir los archivos modificados (los `models.py`
no cambian, por lo que no hay riesgo de esquema). No se requiere
`alembic upgrade/downgrade`.

## Open Questions

Ninguna que afecte specs, enfoque ni desglose de tareas. El helper de serialización
de `Venta` se reusa del módulo `ventas` (`VentaRead`, `ClienteRef`); si no cubre algún
campo, se construye en el router a partir de los atributos cargados.