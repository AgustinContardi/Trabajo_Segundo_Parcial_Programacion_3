# Spec Delta — ventas

## ADDED Requirements

### Requirement: El módulo de ventas expone la escritura `POST /ventas`

El módulo `ventas` SHALL exponer `POST /ventas` además de sus lecturas. La operación SHALL delegar el contrato transaccional, la validación de entrada, el descuento de stock y los movimientos en la capacidad `venta-transaccional`, sin duplicar esas reglas en este spec. `GET /ventas/`, `GET /ventas/{id}` y `GET /mis-ventas` SHALL conservar su comportamiento.

#### Scenario: El módulo acepta el alta de venta

- **WHEN** se consulta el OpenAPI del módulo `ventas`
- **THEN** aparece `POST /ventas/` con `201` y el contrato de `venta-transaccional`

#### Scenario: Las lecturas no cambian

- **WHEN** un usuario autorizado consulta `GET /ventas/`, `GET /ventas/{id}` o `GET /mis-ventas`
- **THEN** la respuesta conserva el comportamiento y los códigos ya especificados
