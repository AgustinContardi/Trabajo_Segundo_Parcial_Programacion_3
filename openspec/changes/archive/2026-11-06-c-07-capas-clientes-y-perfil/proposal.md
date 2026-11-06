# Proposal — C-07 capas-clientes-y-perfil

## Why

C-06 ya dejó el molde de seis capas validado sobre los CRUDs simples del catálogo
(`editoriales`, `generos`, `autores`), pero `clientes` sigue con el patrón anterior del
TP cap. 1-4: el servicio recibe `AsyncSession`, escribe con `session.add(...)` y el
router confirma con `session.commit()`, y la precarga (`selectinload`) vive en el
servicio. Ese patrón vale el **16 %** de la rúbrica («Repositorios y Unit of Work») y
es el que C-07 reemplaza para el módulo de clientes.

C-07 es el segundo eslabón de Fase 4 y el que introduce el primer módulo con **relación
1—0..1 con `usuario`** y **1—1 con `perfil_cliente`**: el `usuario_id` nullable +
`UNIQUE` de `cliente` es lo que hace posible `RN-02` (auto-registro atómico) y `RN-14`
(lo propio). Un `UNIQUE` mal puesto rompe el cliente de mostrador (que no tiene usuario)
o permite que un usuario cuelgue de dos fichas. Por eso la governance es **ALTO** y se
hace antes de C-12 (auto-registro), que depende de este modelo.

## What Changes

- Refactorizar el módulo `clientes` a las **seis capas** obligatorias (`models`,
  `schemas`, `repository`, `unit_of_work`, `service`, `router`), conforme a `CV-03`.
- Crear `ClienteRepository` (extiende `BaseRepository[Cliente]`) con precarga de
  `perfil` y de `usuario` **declarada adentro del método que la necesita** (`CV-02`), y
  un método `ventas_de(cliente_id, page, size)` que pagina las ventas del cliente
  (query sobre `venta`, con `paginar()` y los mismos filtros).
- Crear `ClientesUnitOfWork` que extienda el base y componga `ClienteRepository` con la
  **misma** sesión recibida.
- Reescribir `service.py` para que **abra** el UoW con `async with` y **nunca** lo
  construya ni reciba una `AsyncSession`; traducir `IntegrityError` a `409`/`422` con
  mensaje propio.
- Reescribir `router.py` para que **construya** el UoW con una dependencia y lo pase al
  servicio, sin `session.commit()` ni `session.rollback()` en el router (`CV-01`).
- Asegurar que `Cliente.usuario_id` es **nulo permitido** y **`UNIQUE`**: el cliente de
  mostrador no tiene acceso web y un usuario no puede colgar de dos fichas. La
  navegación se declara en los dos extremos (`Cliente.usuario` devuelve un objeto,
  `Usuario.cliente`).
- `POST /clientes` → **201** con `usuario_id` nulo; **409** si el correo ya existe;
  **422** por campos de más (`extra="forbid"`).
- `GET /clientes/{id}` → **200** con su perfil (si lo tiene); `PATCH /clientes/{id}` →
  **200** sólo con lo enviado; **404** inexistente; **409** correo que choca.
- `POST /clientes/{id}/perfil` → **201**; **404** cliente inexistente; **409** si ya
  tiene perfil (unicidad `perfil_cliente.cliente_id`).
- `GET /clientes/{id}/ventas` → **200** paginado; **404** si el cliente no existe; **403**
  si quien pide es `CLIENTE` (`RN-14`).
- `ClienteRead` incluye `usuario_id` (nulo para clientes de mostrador) y
  `ClienteDetailRead` expone `perfil` opcional.
- Verificación de la capa: `grep -rn "AsyncSession\|UnitOfWork(" app/modules/clientes/service.py`
  vacío y precarga exclusiva en `repository.py` (`CV-02`).

## Capabilities

### New Capabilities

- `clientes-y-perfil`: seis capas para el módulo `clientes` — alta de cliente de
  mostrador con `usuario_id` nulo (`201`), consulta y edición con perfil (`200`), alta
  de perfil (`201`/`404`/`409`) y ventas del cliente paginadas (`200`/`404`/`403` para
  `CLIENTE`). El router construye el UoW y el servicio lo abre; la precarga vive sólo en
  `repository.py`; `usuario_id` es nulo y `UNIQUE`.

### Modified Capabilities

Ninguna: los requisitos de `data-model` (`cliente.usuario_id` nulo + `UNIQUE`,
`perfil_cliente.cliente_id` FK `UNIQUE` 1—1, navegación en los dos extremos) y de
`core-repositories` (repositorios base, UoW base, paginación) no cambian; C-07 los
**consume** y los aplica al módulo. Los schemas base de `api-contracts`
(`Create`/`Update`/`Read` con `extra="forbid"`) tampoco se redefinen: se instancian por
entidad en el módulo.

## Impact

- **Código nuevo**: `parcial/app/modules/clientes/repository.py` y `unit_of_work.py`.
- **Código reescrito**: `service.py` y `router.py` del módulo (pierden `AsyncSession` y
  `session.commit()`); `schemas.py` se extiende con `usuario_id` en `ClienteRead` y
  `Pagina` en el listado de ventas.
- **Modelos**: sin cambios de esquema (`models.py` ya tiene `usuario_id` nulo + `UNIQUE`
  y la navegación en los dos extremos por C-03); se verifica que no se altere.
- **Migraciones**: ninguna nueva.
- **API**: se mantienen las rutas existentes del TP cap. 1-4, pero con el patrón de
  capas y los códigos de estado ya fijados por C-05 (201/200/404/409/422); se agrega
  paginación a `GET /clientes/{id}/ventas`.
- **Dependencias aguas abajo**: habilita `C-10` (capas-ventas-lecturas, que reusa el
  patrón y la precarga fija de consultas) y `C-12` (auto-registro atómico, que depende
  del `usuario_id` nullable/`UNIQUE` y de `ClienteRepository`).
- **Riesgo principal**: un `UNIQUE` mal puesto en `usuario_id` rompe el cliente de
  mostrador (múltiples `NULL` deben estar permitidos) o permite que un usuario cuelgue
  de dos fichas; se mitiga con el modelo ya validado en C-03 y con la verificación de
  la capa. El `403` de `GET /clientes/{id}/ventas` para `CLIENTE` depende de
  `get_usuario_actual`/`requiere_rol` (C-11/C-13); hasta que estén disponibles, el
  servicio deja el punto de decisión documentado y el cableado se completa en C-13.