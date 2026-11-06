# Proposal — C-10 capas-ventas-lecturas

## Why

C-08 y C-09 dejaron el módulo `libros` con seis capas y el punto único de escritura
de stock, y C-07 hizo lo propio con `clientes`. El módulo `ventas`, en cambio, sigue con
el patrón anterior del TP cap. 1-4: el servicio recibe `AsyncSession`, escribe con
`session.add(...)`, el router confirma con `session.commit()` y la precarga
(`selectinload`/`joinedload`) vive en el servicio. Ese patrón vale el **16 %** de la
rúbrica («Repositorios y Unit of Work») y es el que C-10 reemplaza para las **lecturas**
de ventas.

C-10 es el primer change que exige **precarga con cardinalidad fija**: el detalle de una
venta debe cargar cliente, renglones y el libro de cada renglón —**incluidos los dados de
baja**— con un número de consultas que **no crece** con la cantidad de renglones (caso
C-15: misma cantidad con 2 y con 4 renglones). Además introduce `RN-14` en su forma de
«lo propio»: `GET /ventas/{id}` no lleva `requiere_rol` y el servicio decide
(personal → 200, dueño → 200, otro → 403, inexistente → 404), y `GET /mis-ventas` sólo
pide estar autenticado (página vacía si el usuario no tiene ficha de cliente, `SU-05`).

## What Changes

- Refactorizar el módulo `ventas` a las **seis capas** obligatorias (`models`, `schemas`,
  `repository`, `unit_of_work`, `service`, `router`), conforme a `CV-03`.
- Crear `VentaRepository` (extiende `BaseRepository[Venta]`) con precarga de `cliente`,
  `renglones` y el `libro` de cada renglón —**incluidos los dados de baja**— declarada
  adentro del método que la necesita (`CV-02`): número de consultas **fijo**, que no
  crece con los renglones.
- Crear `VentasUnitOfWork` que extienda el base y componga `VentaRepository` (y
  `ClienteRepository`, para resolver `usuario_id → cliente`) con la **misma** sesión
  recibida, y la dependencia `get_ventas_uow(session)`.
- Reescribir `service.py` para que **abra** el UoW con `async with` y **nunca** lo
  construya ni reciba una `AsyncSession`; traducir `IntegrityError` a `409`/`422` con
  mensaje propio.
- Reescribir `router.py` para que **construya** el UoW con una dependencia y lo pase al
  servicio, sin `session.commit()` ni `session.rollback()` en el router (`CV-01`).
- `GET /ventas` (`page`, `size`) → **200** para `VENDEDOR`/`ADMIN`, con envoltorio y
  orden estable (lleva `requiere_rol('VENDEDOR','ADMIN')`).
- `GET /ventas/{id}` **sin `requiere_rol`**: personal → 200, dueño → 200, otro → **403**,
  inexistente → 404. La decisión la toma el servicio (`RN-14`).
- `GET /mis-ventas` (`page`, `size`) → **200** sólo con sesión: las ventas del cliente
  ligado por `usuario_id`; sin cookie → 401; un usuario sin ficha de cliente → página
  vacía (`SU-05`).
- **No** existe `PATCH /ventas/{id}` (`RN-09`): las ventas no se modifican. La alta
  transaccional (`POST /ventas`) llega con C-16; C-10 no la implementa ni la redefine.
- Verificación de la capa: `grep -rn "AsyncSession\|UnitOfWork(" app/modules/ventas/service.py`
  vacío y precarga exclusiva en `repository.py` (`CV-02`).

## Capabilities

### New Capabilities

- `ventas`: seis capas para el módulo `ventas` centradas en las **lecturas** — listado
  paginado `GET /ventas` (200 para `VENDEDOR`/`ADMIN`, envoltorio, orden estable),
  detalle `GET /ventas/{id}` sin `requiere_rol` con decisión en el servicio (personal →
  200, dueño → 200, otro → 403, inexistente → 404) que muestra el título del libro
  aunque esté dado de baja, y `GET /mis-ventas` (sólo sesión, página vacía si no hay
  ficha de cliente). `VentaRepository` precarga cliente, renglones y el libro de cada
  renglón (incluidos los dados de baja) con número de consultas fijo. Router construye
  el UoW, servicio lo abre, precarga sólo en `repository.py`, sin `PATCH`.

### Modified Capabilities

Ninguna: C-10 **consume** `data-model` (venta, renglon_venta), `core-repositories`
(repositorios base, UoW base, paginación), `api-contracts` (schemas con `extra="forbid"`,
traducción de `IntegrityError`) y `libros` (precarga de libro incluyendo los dados de
baja, ya fijada) sin redefinir sus requisitos. La alta transaccional de ventas llega
con C-16, que extenderá este capability.

## Impact

- **Código nuevo**: `parcial/app/modules/ventas/repository.py` y `unit_of_work.py`.
- **Código reescrito**: `service.py` y `router.py` del módulo (pierden `AsyncSession` y
  `session.commit()`); `schemas.py` se ajusta para el detalle con libro incluyendo
  borrados y para `mis-ventas`.
- **Modelos**: sin cambios de esquema (`models.py` ya tiene las relaciones y las FKs con
  índice por C-01/C-03); se verifica que no se alteren.
- **Migraciones**: ninguna nueva.
- **API**: se mantienen las rutas de lectura del TP cap. 1-4 con el patrón de capas y
  los códigos de C-05; se agrega `GET /mis-ventas`; no existe `PATCH /ventas/{id}`.
- **Dependencias aguas abajo**: habilita `C-16` (venta transaccional, que reusa
  `VentasUnitOfWork` y el punto único de stock de C-08) y `C-18` (casos C-06 y C-15).
- **Riesgo principal**: precarga que crece con los renglones (N+1) o que filtra los
  libros dados de baja (rompe «la venta vieja sigue mostrando el título»). Se mitiga
  con `selectinload` anidado declarado en el repositorio y contando `SELECT` con
  `SQL_ECHO=true` (caso C-15). El `403` de `GET /ventas/{id}` para quien no es personal
  ni dueño depende de `get_usuario_actual` (C-11/C-13); hasta que estén disponibles, el
  servicio deja el punto de decisión documentado y el cableado se completa en C-13 sin
  cambiar la firma del servicio. `GET /mis-ventas` depende de la sesión (C-11); el
  cableado de autenticación se completa en C-13.