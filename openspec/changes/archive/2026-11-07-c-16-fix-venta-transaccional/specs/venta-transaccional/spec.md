# Spec Delta — venta-transaccional

## MODIFIED Requirements

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

`POST /ventas` SHALL responder `422` cuando `renglones` esté vacío o cuando un mismo `libro_id` aparezca en dos renglones (`RN-09`). La detección de repetidos SHALL ejecutarse después de las verificaciones de sesión, rol y existencia de cliente/libros, para no devolver `422` donde corresponde `409`, y SHALL ocurrir sin escribir filas.

#### Scenario: Cero renglones

- **WHEN** `renglones` es una lista vacía
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Libro repetido

- **WHEN** el mismo `libro_id` aparece en dos renglones del mismo cuerpo
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Libro repetido con cliente inexistente

- **WHEN** el mismo `libro_id` aparece dos veces y `cliente_id` no existe
- **THEN** la respuesta es `409`, no `422`, y no se escribe ninguna fila

#### Scenario: Libro repetido con libro inexistente

- **WHEN** el mismo `libro_id` aparece dos veces y ese libro no existe
- **THEN** la respuesta es `409`, no `422`, y no se escribe ninguna fila

### Requirement: Los errores no exponen detalles internos

Todo error de negocio SHALL devolver un mensaje propio en español y SHALL omitir nombres de tablas, columnas, constraints y trazas de PostgreSQL; ninguna entrada inválida SHALL terminar en `500` (`RN-15`). Un `DataError`/`DBAPIError` de datos SHALL traducirse a `422` genérico en español; un `IntegrityError` SHALL conservar su traducción a `409`/`422`.

#### Scenario: Entrada inválida no termina en 500

- **WHEN** se envía `POST /ventas` con cuerpo inválido (por ejemplo, `precio` extra)
- **THEN** la respuesta es `422` con un mensaje propio en español y nunca `500` ni trazas de PostgreSQL

#### Scenario: DataError se traduce sin filtrar PostgreSQL

- **WHEN** una escritura o consulta produce un `DataError` de datos
- **THEN** la respuesta es `422` con un mensaje genérico en español y sin texto interno de la base

#### Scenario: IntegrityError conserva su traducción

- **WHEN** una escritura viola una FK o un CHECK conocido
- **THEN** la respuesta es el `409` o `422` propio del constraint, sin texto de PostgreSQL

## ADDED Requirements

### Requirement: Los enteros de entrada son estrictos y acotados a sus columnas

`cliente_id` y `libro_id` SHALL ser enteros positivos y estrictos, acotados a `BIGINT` (`<= 9223372036854775807`); `cantidad` SHALL ser un entero positivo estricto acotado a la columna (`<= 2147483647`). Booleanos, strings, floats y valores fuera de rango SHALL responder `422` con mensaje en español y sin escribir filas (`RN-09`, `RN-15`, `docs/CHECKLIST_ENTREGA.md` §8).

#### Scenario: ID fuera del rango BIGINT

- **WHEN** `cliente_id` o `libro_id` es `10**30` o supera `9223372036854775807`
- **THEN** la respuesta es `422` en español, nunca `500`, y no se escribe ninguna fila

#### Scenario: Cantidad booleana

- **WHEN** `cantidad` es `true` o `false`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: ID o cantidad no entera

- **WHEN** `cliente_id`, `libro_id` o `cantidad` llega como string o float
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Cantidad fuera del rango de la columna

- **WHEN** `cantidad` supera `2147483647`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

### Requirement: Orden de verificación 401 → 403 → 409 → 422

El endpoint SHALL evaluar, en este orden: autenticación (401 sin sesión), rol vigente VENDEDOR/ADMIN (403), existencia del cliente (409), existencia y vigencia de los libros (409), stock agregado suficiente por libro (409) y, recién después, el contrato de renglones (422 por libro repetido o cuerpo inválido) (`CV-08`, `docs/CHECKLIST_ENTREGA.md` §8). Un `POST /ventas` no usa `404`: el `404` queda reservado para las lecturas de detalle.

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

- **WHEN** el `stock` de algún libro es menor que la cantidad agregada de sus renglones
- **THEN** la respuesta es `409` y no queda ninguna escritura (ni venta, ni renglones, ni descuentos, ni movimientos)

#### Scenario: Duplicado después de los 409

- **WHEN** el cuerpo repite un `libro_id` pero además el cliente o un libro no existe
- **THEN** la respuesta es `409` y no se escribe ninguna fila

### Requirement: Las rutas de alta de venta no redirigen por barra final

`POST /ventas` y `POST /ventas/` SHALL responder con el mismo status y cuerpo, sin `307`. La ruta canónica documentada SHALL ser `POST /ventas/`; la variante sin barra SHALL aceptarse sin redirección.

#### Scenario: Alta sin barra final

- **WHEN** se envía `POST /ventas` con un cuerpo válido y sesión de vendedor
- **THEN** la respuesta es `201` con el mismo cuerpo que `POST /ventas/`, sin `307`

## REMOVED Requirements

### Requirement: Orden de verificación 404 → 403 → 409 → 422

**Reason**: El título era incorrecto para `POST /ventas`: la operación no devuelve `404`; el `404` pertenece a las lecturas de detalle (`GET /ventas/{id}`). El orden real de esta escritura es 401 → 403 → 409 → 422, y el título inducía a error en la documentación y en la evidencia de `C-16`.

**Migration**: Usar `409` para cliente o libro inexistente/dado de baja en `POST /ventas`; reservar `404` para `GET /ventas/{id}`. El requisito nuevo "Orden de verificación 401 → 403 → 409 → 422" reemplaza a este con el mismo comportamiento observable ya implementado.
