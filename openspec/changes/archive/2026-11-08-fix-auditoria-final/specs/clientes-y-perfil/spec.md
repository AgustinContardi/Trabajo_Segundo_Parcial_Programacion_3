# Spec Delta — clientes-y-perfil

## MODIFIED Requirements

### Requirement: Ventas del cliente paginadas

El sistema SHALL permitir listar las ventas de un cliente mediante `GET /clientes/{id}/ventas`, respondiendo `200` con el envoltorio `{items, total, page, size, pages}`. Sin cookie válida SHALL responder `401`. La ruta SHALL exigir rol vigente `VENDEDOR` o `ADMIN` leído de `asignacion_rol` en cada petición; un `CLIENTE` SHALL responder `403` y un rol revocado o vencido no SHALL otorgar acceso. Para personal autorizado, un cliente inexistente SHALL responder `404`. La consulta SHALL aplicar un orden determinista por `Venta.id` antes de paginar, de modo que dos llamadas iguales devuelvan las mismas filas y que las páginas no repitan ni omitan ventas.

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

#### Scenario: Paginación estable con varias ventas

- **WHEN** un cliente tiene al menos tres ventas y se solicitan `size=2&page=1` y `size=2&page=2`
- **THEN** la primera página trae los dos ids menores en orden ascendente, la segunda el restante, y no
  hay ids repetidos ni faltantes entre ambas

#### Scenario: Orden documentado en la consulta

- **WHEN** se compila la consulta de `ClienteRepository.ventas_de`
- **THEN** el SQL contiene `ORDER BY venta.id` (o el criterio determinista documentado) antes del límite
