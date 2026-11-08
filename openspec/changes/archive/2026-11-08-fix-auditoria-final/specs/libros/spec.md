# Spec Delta — libros

## ADDED Requirements

### Requirement: Movimiento de stock atribuido al usuario autenticado

Todo `movimiento_stock` escrito por el alta de un libro (`motivo = 'Stock inicial'`) o por la reposición
(`motivo = 'Reposición'`) SHALL registrar en `usuario_id` al usuario autenticado que ejecuta la petición,
no a un usuario elegido por una consulta de respaldo. El servicio SHALL recibir el usuario actual desde el
router; si necesita escribir un movimiento y no recibe actor, SHALL fallar con `409` en lugar de atribuir
el movimiento a otra cuenta (`RN-11`).

#### Scenario: Alta atribuye el movimiento al ADMIN autenticado

- **WHEN** un administrador distinto del primer usuario de la tabla crea un libro con `stock_inicial > 0`
- **THEN** el `movimiento_stock` «Stock inicial» tiene `usuario_id` igual al id de ese administrador

#### Scenario: Reposición atribuye el movimiento al ADMIN autenticado

- **WHEN** un administrador distinto del primer usuario de la tabla repone stock
- **THEN** el `movimiento_stock` «Reposición» tiene `usuario_id` igual al id de ese administrador
- **AND** `GET /libros/{id}/movimientos` devuelve ese mismo `usuario_id`

#### Scenario: Sin actor no se inventa un usuario

- **WHEN** el servicio intenta escribir un movimiento sin recibir usuario actual
- **THEN** responde `409` y no escribe el movimiento ni modifica el stock

#### Scenario: Stock inicial cero no crea movimiento

- **WHEN** se crea un libro con `stock_inicial = 0`
- **THEN** no se escribe ningún movimiento (el `CHECK cantidad <> 0` lo impide) y el invariante se cumple
