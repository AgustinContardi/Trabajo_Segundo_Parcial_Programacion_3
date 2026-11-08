# ventas Specification

## Purpose

Define el comportamiento del módulo `ventas` tras su migración a seis capas: sus
**lecturas** —listado paginado `GET /ventas` (personal), detalle `GET /ventas/{id}`
sin `requiere_rol` con decisión en el servicio (personal o dueño → 200, otro → 403,
inexistente → 404) que muestra el título del libro aunque esté dado de baja, y
`GET /mis-ventas` (sólo sesión, página vacía si no hay ficha de cliente)— y su
**escritura** `POST /ventas`, que delega el contrato transaccional en la capacidad
`venta-transaccional`. Incluye el contrato de capas (router construye el UoW, el
servicio lo abre, la precarga vive sólo en `repository.py`) y la precarga con
cardinalidad fija (cliente, renglones y libro de cada renglón, incluidos los dados de
baja), que no crece con la cantidad de renglones.

## Requirements

### Requirement: El módulo de ventas expone la escritura `POST /ventas`

El módulo `ventas` SHALL exponer `POST /ventas` además de sus lecturas. La operación SHALL delegar el contrato transaccional, la validación de entrada, el descuento de stock y los movimientos en la capacidad `venta-transaccional`, sin duplicar esas reglas en este spec. `GET /ventas/`, `GET /ventas/{id}` y `GET /mis-ventas` SHALL conservar su comportamiento.

#### Scenario: El módulo acepta el alta de venta

- **WHEN** se consulta el OpenAPI del módulo `ventas`
- **THEN** aparece `POST /ventas/` con `201` y el contrato de `venta-transaccional`

#### Scenario: Las lecturas no cambian

- **WHEN** un usuario autorizado consulta `GET /ventas/`, `GET /ventas/{id}` o `GET /mis-ventas`
- **THEN** la respuesta conserva el comportamiento y los códigos ya especificados

### Requirement: Listado paginado de ventas

El sistema SHALL permitir listar ventas mediante `GET /ventas` con parámetros `page` y
`size`, respondiendo `200` con el envoltorio `{items, total, page, size, pages}` para
usuarios con rol `VENDEDOR` o `ADMIN`. `size` va de 1 a 100 con default 20; página fuera
de rango SHALL responder `422`; cero resultados SHALL responder una página vacía
(`items: []`, `total: 0`, `pages: 1`). El orden SHALL ser estable. Sin sesión SHALL
responder `401`. Un usuario sin rol personal SHALL responder `403`.

#### Scenario: Listado paginado por personal

- **WHEN** un `VENDEDOR` o `ADMIN` autenticado solicita `GET /ventas?page=&size=`
- **THEN** la respuesta es `200` con el envoltorio y las ventas de la página

#### Scenario: Sin sesión

- **WHEN** se solicita `GET /ventas` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: Solicitante sin rol personal

- **WHEN** un usuario con rol `CLIENTE` solicita `GET /ventas`
- **THEN** la respuesta es `403`

#### Scenario: Página fuera de rango

- **WHEN** se solicita una página más allá de la última
- **THEN** la respuesta es `422`

#### Scenario: Cero resultados

- **WHEN** no hay ventas registradas
- **THEN** la respuesta es `200` con `items: []`, `total: 0`, `pages: 1`

#### Scenario: Forma del envoltorio

- **WHEN** se solicita `GET /ventas` válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

### Requirement: Detalle de venta sin requiere_rol

El sistema SHALL permitir consultar una venta mediante `GET /ventas/{id}`, respondiendo
`200` con cliente, renglones y el libro de cada renglón. La ruta **no** SHALL llevar
`requiere_rol`: la decisión la toma el servicio. Si la venta no existe SHALL responder
`404`. Si quien solicita es personal (`VENDEDOR`/`ADMIN`) o el dueño (el cliente de la
venta es el ligado al usuario actual) SHALL responder `200`. Si no es ni personal ni
dueño SHALL responder `403`. La ruta **no** SHALL existir como `PATCH`.

#### Scenario: Personal consulta cualquier venta

- **WHEN** un `VENDEDOR` o `ADMIN` autenticado solicita `GET /ventas/{id}` existente
- **THEN** la respuesta es `200` con cliente, renglones y libros

#### Scenario: Dueño consulta su venta

- **WHEN** el cliente dueño de la venta solicita `GET /ventas/{id}`
- **THEN** la respuesta es `200` con cliente, renglones y libros

#### Scenario: Otro cliente consulta una venta ajena

- **WHEN** un `CLIENTE` que no es el dueño solicita `GET /ventas/{id}` existente
- **THEN** la respuesta es `403`

#### Scenario: Venta inexistente

- **WHEN** se solicita `GET /ventas/{id}` con un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Libro dado de baja se muestra

- **WHEN** se consulta el detalle de una venta que contiene un libro dado de baja
- **THEN** el título del libro se muestra en el renglón

#### Scenario: Sin sesión

- **WHEN** se solicita `GET /ventas/{id}` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: No existe PATCH

- **WHEN** se envía `PATCH /ventas/{id}`
- **THEN** la respuesta es `404` o `405` (la ruta no está registrada)

### Requirement: Mis ventas (sólo sesión)

El sistema SHALL permitir listar las ventas del cliente ligado al usuario autenticado
mediante **`GET /mis-ventas`** con parámetros `page` y `size`, respondiendo `200` con el
envoltorio `{items, total, page, size, pages}`. La ruta es **independiente del prefijo
`/ventas`**: `GET /ventas/mis-ventas` MUST NOT existir ni publicarse en `openapi.json`.
La ruta **no** SHALL exigir un rol, sólo sesión (`RN-14`). Sin cookie SHALL responder `401`.
Si el usuario autenticado no tiene ficha de cliente SHALL responder `200` con una página vacía
(`items: []`, `total: 0`, `pages: 1`). `size` va de 1 a 100 con default 20; página
fuera de rango SHALL responder `422`. La ruta SHALL seguir dentro del grupo protegido, de modo
que `control_cambio_password` la alcance igual que al resto de las rutas privadas.

#### Scenario: Cliente ve sus ventas

- **WHEN** un cliente autenticado con ficha de cliente solicita `GET /mis-ventas`
- **THEN** la respuesta es `200` con sólo sus ventas en el envoltorio

#### Scenario: Sin sesión

- **WHEN** se solicita `GET /mis-ventas` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: Usuario sin ficha de cliente

- **WHEN** un usuario autenticado sin ficha de cliente (por ejemplo un `VENDEDOR`)
  solicita `GET /mis-ventas`
- **THEN** la respuesta es `200` con `items: []`, `total: 0`, `pages: 1`

#### Scenario: Forma del envoltorio

- **WHEN** se solicita `GET /mis-ventas` válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

#### Scenario: Path canónico único

- **WHEN** se inspecciona `openapi.json`
- **THEN** existe la ruta `/mis-ventas` y no existe `/ventas/mis-ventas`
- **AND** `GET /ventas/mis-ventas` responde `404`

#### Scenario: Cambio de contraseña pendiente

- **WHEN** un usuario con `debe_cambiar_password = true` solicita `GET /mis-ventas`
- **THEN** la respuesta es `403` porque la ruta sigue en el grupo protegido

### Requirement: Precarga con cardinalidad fija

`VentaRepository` SHALL precargar `cliente`, `renglones` y el `libro` de cada renglón
mediante `selectinload` anidado **declarado adentro del método que lo necesita**, con
un número de consultas **fijo** e **independiente** de la cantidad de renglones (mismo
conteo con 2 y con 4 renglones). La precarga del libro **no** SHALL filtrar los dados
de baja.

#### Scenario: Mismo conteo con 2 y 4 renglones

- **WHEN** se consulta `GET /ventas/{id}` de una venta con 2 renglones y otra con 4
  renglones con `SQL_ECHO=true`
- **THEN** el número de `SELECT` es el mismo en ambos casos

#### Scenario: Precarga sólo en repository.py

- **WHEN** se busca `selectinload`/`joinedload` en `service.py` y `router.py` del
  módulo
- **THEN** no se encuentra ninguna ocurrencia

### Requirement: Unit of Work por módulo compone el repositorio con la misma sesión

El módulo SHALL proveer un `VentasUnitOfWork` que extienda el base y componga su
`VentaRepository` (y `ClienteRepository`, para resolver `usuario_id → cliente`) pasándole
la misma sesión recibida.

#### Scenario: Misma sesión

- **WHEN** se instancia el Unit of Work del módulo con una sesión
- **THEN** sus repositorios usan esa misma sesión

### Requirement: Servicio no recibe AsyncSession ni construye el UoW

Ningún servicio del módulo SHALL declarar un parámetro de tipo `AsyncSession` ni
instanciar un Unit of Work. El router SHALL construir el UoW con una dependencia y
pasarlo al servicio, que lo abre con `async with`.

#### Scenario: Ausencia de AsyncSession en el servicio

- **WHEN** se inspecciona `app/modules/ventas/service.py`
- **THEN** no aparece `AsyncSession` ni `UnitOfWork(`

### Requirement: Precarga sólo en repository.py

Toda precarga (`selectinload`/`joinedload` u otra) del módulo SHALL vivir únicamente en
`repository.py`. Ni `service.py` ni `router.py` SHALL contener precarga.

#### Scenario: Precarga fuera de repository.py

- **WHEN** se busca `selectinload` en `service.py` y `router.py` del módulo
- **THEN** no se encuentra ninguna ocurrencia

### Requirement: No existe PATCH de ventas

El módulo **no** SHALL registrar una ruta `PATCH /ventas/{id}` y **no** SHALL existir
un schema `VentaUpdate`. Las ventas no se modifican (`RN-09`).

#### Scenario: PATCH inexistente

- **WHEN** se envía `PATCH /ventas/{id}`
- **THEN** la respuesta es `404` o `405` (la ruta no está registrada)
