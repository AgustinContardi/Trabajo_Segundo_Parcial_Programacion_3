# Spec Delta — ventas

## MODIFIED Requirements

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
