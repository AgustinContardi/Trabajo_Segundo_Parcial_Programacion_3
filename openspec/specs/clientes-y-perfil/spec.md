# clientes-y-perfil Specification

## Purpose

Define el comportamiento del módulo `clientes` tras su migración a seis capas: alta de
cliente de mostrador con `usuario_id` nulo, consulta y edición con perfil, alta de
perfil 1—1 y ventas del cliente paginadas, con el contrato de capas (router construye
el UoW, el servicio lo abre, la precarga vive sólo en `repository.py`).

## Requirements

### Requirement: Alta de cliente de mostrador

El sistema SHALL permitir crear un cliente de mostrador mediante `POST /clientes`,
respondiendo `201` con la entidad creada y `usuario_id` nulo. Si el correo ya existe
SHALL responder `409` con mensaje propio. Si el cuerpo incluye un campo no declarado
SHALL responder `422`.

#### Scenario: Alta exitosa

- **WHEN** se envía un cuerpo válido a `POST /clientes`
- **THEN** la respuesta es `201` con el cliente creado, incluyendo su `id` y
  `usuario_id` nulo

#### Scenario: Correo duplicado

- **WHEN** se intenta crear un cliente cuyo correo ya existe
- **THEN** la respuesta es `409` con un mensaje propio y no se crea la fila

#### Scenario: Contrato inválido

- **WHEN** el cuerpo incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422` y no se ejecuta el alta

### Requirement: Consulta de cliente con perfil

El sistema SHALL permitir consultar un cliente mediante `GET /clientes/{id}`,
respondiendo `200` con su perfil cuando lo tiene. Si el cliente no existe SHALL
responder `404`.

#### Scenario: Cliente existente con perfil

- **WHEN** se solicita `GET /clientes/{id}` con un id existente que tiene perfil
- **THEN** la respuesta es `200` con los datos del cliente y su perfil

#### Scenario: Cliente existente sin perfil

- **WHEN** se solicita `GET /clientes/{id}` con un id existente sin perfil
- **THEN** la respuesta es `200` con los datos del cliente y `perfil` nulo

#### Scenario: Cliente inexistente

- **WHEN** se solicita `GET /clientes/{id}` con un id que no existe
- **THEN** la respuesta es `404`

### Requirement: Actualización parcial de cliente

El sistema SHALL permitir actualizar un cliente mediante `PATCH /clientes/{id}`,
aplicando únicamente los campos presentes en la petición y respondiendo `200`. Si el
cliente no existe SHALL responder `404`; si el correo choca con uno existente SHALL
responder `409`; si el contrato se viola SHALL responder `422`.

#### Scenario: Actualización parcial

- **WHEN** se envía un `PATCH` con un subconjunto de campos a `/clientes/{id}`
- **THEN** sólo esos campos se modifican y los omitidos conservan su valor, con `200`

#### Scenario: Recurso inexistente

- **WHEN** se envía un `PATCH` a un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Correo que choca

- **WHEN** el `PATCH` intenta un correo que ya existe en otro cliente
- **THEN** la respuesta es `409` con mensaje propio

#### Scenario: Contrato inválido

- **WHEN** el `PATCH` incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422`

### Requirement: Alta de perfil de cliente

El sistema SHALL permitir crear el perfil de un cliente mediante
`POST /clientes/{id}/perfil`, respondiendo `201`. Si el cliente no existe SHALL
responder `404`. Si el cliente ya tiene perfil SHALL responder `409`.

#### Scenario: Alta exitosa

- **WHEN** se envía un cuerpo válido a `POST /clientes/{id}/perfil` con un cliente
  existente sin perfil
- **THEN** la respuesta es `201` con el perfil creado

#### Scenario: Cliente inexistente

- **WHEN** se envía `POST /clientes/{id}/perfil` con un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Perfil duplicado

- **WHEN** se intenta crear un perfil para un cliente que ya tiene uno
- **THEN** la respuesta es `409` con mensaje propio

### Requirement: Ventas del cliente paginadas

El sistema SHALL permitir listar las ventas de un cliente mediante `GET /clientes/{id}/ventas`, respondiendo `200` con el envoltorio `{items, total, page, size, pages}`. Sin cookie válida SHALL responder `401`. La ruta SHALL exigir rol vigente `VENDEDOR` o `ADMIN` leído de `asignacion_rol` en cada petición; un `CLIENTE` SHALL responder `403` y un rol revocado o vencido no SHALL otorgar acceso. Para personal autorizado, un cliente inexistente SHALL responder `404`.

#### Scenario: Listado paginado

- **WHEN** personal (VENDEDOR o ADMIN) solicita `GET /clientes/{id}/ventas` con un cliente existente
- **THEN** la respuesta es `200` con el envoltorio y las ventas de ese cliente

#### Scenario: Cliente inexistente

- **WHEN** personal autorizado solicita `GET /clientes/{id}/ventas` con un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Solicitante CLIENTE

- **WHEN** un usuario con rol `CLIENTE` solicita `GET /clientes/{id}/ventas`
- **THEN** la respuesta es `403` y no se ejecuta la consulta de ventas

#### Scenario: Sin cookie válida

- **WHEN** se solicita `GET /clientes/{id}/ventas` sin `access_token`, con token inválido o vencido, o con usuario inactivo
- **THEN** la respuesta es `401`

#### Scenario: Rol revocado o vencido

- **WHEN** un usuario cuya asignación `VENDEDOR` fue revocada o venció solicita `GET /clientes/{id}/ventas` con la misma cookie anterior
- **THEN** la respuesta es `403`

#### Scenario: Forma del envoltorio

- **WHEN** se solicita `GET /clientes/{id}/ventas` válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

### Requirement: Unit of Work por módulo compone el repositorio con la misma sesión

El módulo SHALL proveer un `ClientesUnitOfWork` que extienda el base y componga su
`ClienteRepository` pasándole la misma sesión recibida.

#### Scenario: Misma sesión

- **WHEN** se instancia el Unit of Work del módulo con una sesión
- **THEN** su repositorio usa esa misma sesión

### Requirement: Servicio no recibe AsyncSession ni construye el UoW

Ningún servicio del módulo SHALL declarar un parámetro de tipo `AsyncSession` ni
instanciar un Unit of Work. El router SHALL construir el UoW con una dependencia y
pasarlo al servicio, que lo abre con `async with`.

#### Scenario: Ausencia de AsyncSession en el servicio

- **WHEN** se inspecciona `app/modules/clientes/service.py`
- **THEN** no aparece `AsyncSession` ni `UnitOfWork(`

### Requirement: Precarga sólo en repository.py

Toda precarga (`selectinload` u otra) del módulo SHALL vivir únicamente en
`repository.py`. Ni `service.py` ni `router.py` SHALL contener precarga.

#### Scenario: Precarga fuera de repository.py

- **WHEN** se busca `selectinload` en `service.py` y `router.py` del módulo
- **THEN** no se encuentra ninguna ocurrencia

### Requirement: Modelo de cliente con usuario opcional y único

El modelo `Cliente` SHALL declarar `usuario_id` nulo permitido y `UNIQUE`, con
navegación en los dos extremos (`Cliente.usuario` devuelve un objeto, `Usuario.cliente`).
`PerfilCliente` SHALL declarar `cliente_id` como FK `UNIQUE` 1—1.

#### Scenario: Múltiples clientes sin usuario

- **WHEN** existen varios clientes con `usuario_id` nulo
- **THEN** la base los admite (el `UNIQUE` permite múltiples `NULL`)

#### Scenario: Un usuario en dos fichas

- **WHEN** se intenta asignar el mismo `usuario_id` a dos clientes
- **THEN** la base rechaza la operación por el `UNIQUE`

#### Scenario: Un perfil por cliente

- **WHEN** se intenta crear un segundo perfil para el mismo cliente
- **THEN** la base rechaza la operación por el `UNIQUE` de `perfil_cliente.cliente_id`
