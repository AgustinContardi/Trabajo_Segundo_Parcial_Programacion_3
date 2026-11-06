# Spec Delta — libros

## ADDED Requirements

### Requirement: Baja lógica de libro

El sistema SHALL permitir dar de baja un libro mediante `DELETE /libros/{id}`,
respondiendo `204` y escribiendo `borrado_en = now()`. El libro SHALL dejar de
aparecer en todos los listados y en el detalle público. Dar de baja un libro ya
dado de baja o inexistente SHALL responder `404`. Un libro dado de baja no SHALL
poder venderse ni reponerse.

#### Scenario: Baja exitosa

- **WHEN** un administrador envía `DELETE /libros/{id}` con un id de un libro vigente
- **THEN** la respuesta es `204`
- **AND** el libro queda con `borrado_en` no nulo
- **AND** deja de aparecer en `GET /libros` y en `GET /libros/{id}`

#### Scenario: Baja repetida o inexistente

- **WHEN** se envía `DELETE /libros/{id}` con un id que no existe o ya está dado de baja
- **THEN** la respuesta es `404`

#### Scenario: Libro dado de baja no se repone

- **WHEN** se envía `POST /libros/{id}/reponer` con un id de un libro dado de baja
- **THEN** la respuesta es `409`

### Requirement: Reposición de stock

El sistema SHALL permitir reponer stock mediante `POST /libros/{id}/reponer` con
`cantidad`, respondiendo `200` con el libro actualizado y dejando un
`movimiento_stock` de entrada (`cantidad > 0`, `motivo = 'Reposición'`) en la misma
transacción. `cantidad <= 0` SHALL responder `422`. Un libro dado de baja SHALL
responder `409`. Un libro inexistente SHALL responder `404`.

#### Scenario: Reposición exitosa

- **WHEN** un administrador envía `POST /libros/{id}/reponer` con `cantidad = N > 0`
  a un libro vigente
- **THEN** la respuesta es `200` con el libro actualizado
- **AND** `libro.stock` aumenta en `N`
- **AND** existe un `movimiento_stock` con `cantidad = N` y `motivo = 'Reposición'`

#### Scenario: Cantidad no positiva

- **WHEN** se envía `POST /libros/{id}/reponer` con `cantidad <= 0`
- **THEN** la respuesta es `422`

#### Scenario: Libro dado de baja

- **WHEN** se envía `POST /libros/{id}/reponer` con un id de un libro dado de baja
- **THEN** la respuesta es `409`

#### Scenario: Libro inexistente

- **WHEN** se envía `POST /libros/{id}/reponer` con un id que no existe
- **THEN** la respuesta es `404`

### Requirement: Consulta de movimientos de stock

El sistema SHALL permitir consultar los movimientos de un libro mediante
`GET /libros/{id}/movimientos`, respondiendo `200` con una lista donde cada
elemento trae `cantidad` (con signo), `motivo`, `cuando`, `usuario_id` y
`venta_id` (nulo si no vino de una venta). Un libro inexistente o dado de baja
SHALL responder `404`.

#### Scenario: Lista con campos

- **WHEN** se envía `GET /libros/{id}/movimientos` con un id de un libro vigente
- **THEN** la respuesta es `200`
- **AND** cada elemento trae `cantidad`, `motivo`, `cuando`, `usuario_id` y `venta_id`

#### Scenario: Libro inexistente o dado de baja

- **WHEN** se envía `GET /libros/{id}/movimientos` con un id que no existe o está
  dado de baja
- **THEN** la respuesta es `404`

### Requirement: Libro incluyendo dados de baja para ventas viejas

El sistema SHALL permitir obtener un libro (incluyendo los dados de baja) para
mostrar su título en ventas anteriores, de modo que una venta vieja siga mostrando
el título aunque el libro esté dado de baja.

#### Scenario: Venta vieja muestra título

- **WHEN** se consulta el detalle de una venta que contiene un libro dado de baja
- **THEN** el título del libro se muestra

## MODIFIED Requirements

### Requirement: Punto único de escritura de stock

El stock de un libro SHALL cambiar únicamente a través de un solo método que
actualiza `libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar. Ese
método es usado por el alta (motivo `'Stock inicial'`), la reposición (motivo
`'Reposición'`, C-09) y la venta (motivo `'Venta'`, C-16). No SHALL existir otro
lugar que escriba `libro.stock` directamente.

#### Scenario: Alta deja el movimiento «Stock inicial»

- **WHEN** se crea un libro con `stock_inicial = N`
- **THEN** `libro.stock = N` y existe un movimiento con `cantidad = N` y
  `motivo = 'Stock inicial'`

#### Scenario: Reposición deja movimiento de entrada

- **WHEN** se repone stock con cantidad `N > 0`
- **THEN** `libro.stock` aumenta en `N` y existe un movimiento con `cantidad = N`
  y `motivo = 'Reposición'`

#### Scenario: Invariante stock = suma de movimientos

- **WHEN** se consulta el stock de un libro
- **THEN** `libro.stock = SUM(movimiento_stock.cantidad)` para ese libro