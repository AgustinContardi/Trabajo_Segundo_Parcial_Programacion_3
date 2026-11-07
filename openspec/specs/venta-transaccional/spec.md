# venta-transaccional Specification

## Purpose
Define el registro atómico de una venta: una sola transacción que escribe la venta, sus renglones, el descuento de stock y un movimiento por renglón, con contrato de entrada cerrado y garantía de rollback si algún libro no alcanza.

## Requirements

### Requirement: El contrato de entrada de `POST /ventas` está cerrado a dos campos

`POST /ventas` SHALL aceptar sólo `cliente_id` y `renglones: [{libro_id, cantidad}]`. SHALL responder `422` ante cualquier campo adicional (`precio`, `total`, `fecha`) y ante un cuerpo que no cumpla el contrato (`RN-09`, `RN-15`, `docs/CHECKLIST_ENTREGA.md` §8).

#### Scenario: Campo `precio` en el cuerpo

- **WHEN** el cuerpo de `POST /ventas` incluye `precio` junto con `cliente_id` y `renglones`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Campo `total` en el cuerpo

- **WHEN** el cuerpo incluye `total`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Campo `fecha` en el cuerpo

- **WHEN** el cuerpo incluye `fecha`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Cuerpo con campo desconocido

- **WHEN** el cuerpo incluye un campo distinto de `cliente_id` y `renglones`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

### Requirement: La venta exige al menos un renglón y sin libros repetidos

`POST /ventas` SHALL responder `422` cuando `renglones` esté vacío o cuando un mismo `libro_id` aparezca en dos renglones (`RN-09`).

#### Scenario: Cero renglones

- **WHEN** `renglones` es una lista vacía
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Libro repetido

- **WHEN** el mismo `libro_id` aparece en dos renglones del mismo cuerpo
- **THEN** la respuesta es `422` y no se escribe ninguna fila

### Requirement: Orden de verificación 404 → 403 → 409 → 422

El endpoint SHALL evaluar, en este orden: autenticación (401 sin sesión), rol vigente VENDEDOR/ADMIN (403), existencia del cliente (409), existencia y vigencia de los libros (409), stock suficiente por renglón (409), y sólo entonces escribir (`CV-08`, `docs/CHECKLIST_ENTREGA.md` §8).

#### Scenario: Sin sesión

- **WHEN** la petición no trae cookie `access_token`
- **THEN** la respuesta es `401`

#### Scenario: Rol CLIENTE

- **WHEN** el usuario autenticado tiene rol `CLIENTE` vigente
- **THEN** la respuesta es `403`

#### Scenario: Cliente inexistente

- **WHEN** `cliente_id` no referencia ninguna fila de `cliente`
- **THEN** la respuesta es `409` y no se escribe ninguna fila

#### Scenario: Libro inexistente

- **WHEN** algún `libro_id` de `renglones` no referencia ninguna fila de `libro`
- **THEN** la respuesta es `409` y no se escribe ninguna fila

#### Scenario: Libro dado de baja

- **WHEN** algún `libro_id` referencia una fila de `libro` con `borrado_en IS NOT NULL`
- **THEN** la respuesta es `409` y no se escribe ninguna fila

#### Scenario: Stock insuficiente

- **WHEN** el `stock` de algún libro es menor que la `cantidad` solicitada en su renglón
- **THEN** la respuesta es `409` y no queda ninguna escritura (ni venta, ni renglones, ni descuentos, ni movimientos)

### Requirement: Una venta válida se escribe en una sola transacción

Una venta válida SHALL responder `201` y persistir, en un solo `async with uow`, una fila en `venta`, una fila en `renglon_venta` por renglón, el descuento de `libro.stock` por renglón y una fila en `movimiento_stock` por renglón con `cantidad` negativa, `venta_id` de la venta nueva y `usuario_id` del vendedor (`RN-09`, `RN-10`, `RN-11`).

#### Scenario: Alta válida con dos renglones

- **WHEN** el cuerpo es válido, el cliente existe, todos los libros existen, están vigentes y alcanzan el stock
- **THEN** la respuesta es `201`, el `total` de la venta es `Σ(cantidad × precio_unitario)`, cada renglón copia el `precio_unitario` del libro, el stock de cada libro se descuenta y hay un `movimiento_stock` por renglón con `cantidad < 0`, `motivo = 'Venta'` y `usuario_id` del vendedor

#### Scenario: Atomicidad ante falta de stock

- **WHEN** un renglón no alcanza tras haber escrito ventas/renglones/movimientos de renglones previos
- **THEN** la respuesta es `409` y `SELECT count(*)` de `venta`, `renglon_venta` y `movimiento_stock` no crece, y el invariante `libro.stock = SUM(movimiento_stock.cantidad)` sigue dando 0 filas

### Requirement: El precio se copia del libro y el total lo calcula el servidor

El `precio_unitario` de cada renglón SHALL copiarse de `libro.precio` al momento de registrar, y `venta.total` SHALL ser `Σ(cantidad × precio_unitario)` calculado por el servidor, sin que ninguno de los dos viaje en el cuerpo (`RN-09`).

#### Scenario: Precio copiado

- **WHEN** se registra una venta para un libro cuyo `precio` es `P`
- **THEN** el renglón creado tiene `precio_unitario = P` aunque después cambie el precio del libro

#### Scenario: Total calculado

- **WHEN** los renglones son `[(libro A, cantidad 2), (libro B, cantidad 3)]` con precios `PA` y `PB`
- **THEN** `venta.total = 2×PA + 3×PB`

### Requirement: El aviso del comprobante se ejecuta tras el commit

Tras confirmar la transacción, el router SHALL agenda `add_task(avisar_comprobante, venta.id)` con `BackgroundTasks`, que duerme 0.5 s y escribe un log visible con el arranque normal de uvicorn (`DD-13`, `docs/CHECKLIST_ENTREGA.md` §8 y §10).

#### Scenario: Aviso tras la respuesta

- **WHEN** la venta se registra en `201`
- **THEN** después de enviada la respuesta aparece en el registro de uvicorn la línea de `avisar_comprobante` para ese `venta.id`

### Requirement: Los errores no exponen detalles internos

Todo error de negocio SHALL devolver un mensaje propio en español y SHALL omitir nombres de tablas, columnas, constraints y trazas de PostgreSQL; ninguna entrada inválida SHALL terminar en `500` (`RN-15`).

#### Scenario: Entrada inválida no termina en 500

- **WHEN** se envía `POST /ventas` con cuerpo inválido (por ejemplo, `precio` extra)
- **THEN** la respuesta es `422` con un mensaje propio en español y nunca `500` ni trazas de PostgreSQL
