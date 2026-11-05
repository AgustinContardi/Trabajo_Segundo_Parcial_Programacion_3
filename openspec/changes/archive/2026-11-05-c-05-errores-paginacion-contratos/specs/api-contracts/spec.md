# Spec Delta

## Purpose

Define los contratos HTTP transversales del parcial: traducción de errores de integridad a mensajes
propios, validación de entrada sin 500, paginación conectada a los listados, schemas por entidad
con campos prohibidos y orden de resolución de errores, para que todos los módulos posteriores
hereden el mismo comportamiento observable.

## ADDED Requirements

### Requirement: Violación de integridad se traduce por nombre de constraint

El sistema SHALL traducir toda `IntegrityError` originada en una violación de unicidad, clave
foránea o restricción `CHECK` a una respuesta `409` o `422` con mensaje propio, según el
constraint que la originó.

#### Scenario: Unicidad duplicada

- **WHEN** una operación intenta insertar una fila que viola una restricción de unicidad
- **THEN** la respuesta es `409` con un mensaje propio en español que identifica el recurso
  duplicado

#### Scenario: Clave foránea inexistente

- **WHEN** una operación referencia una entidad inexistente
- **THEN** la respuesta es `409` con un mensaje propio que indica el recurso inexistente

#### Scenario: Restricción CHECK violada

- **WHEN** una operación envía un valor que viola un `CHECK` de la base
- **THEN** la respuesta es `422` con un mensaje propio que describe el valor inválido

### Requirement: Ningún texto interno de la base llega al cliente

El sistema SHALL no incluir en ninguna respuesta de error el texto de PostgreSQL, nombres de
tablas, columnas, constraints ni trazas de ejecución.

#### Scenario: Error de integridad

- **WHEN** ocurre una `IntegrityError`
- **THEN** el cuerpo de la respuesta no contiene el mensaje original de la base de datos

#### Scenario: Error no controlado

- **WHEN** ocurre un error inesperado
- **THEN** la respuesta es genérica y no expone detalles internos ni traza

### Requirement: Ninguna entrada inválida termina en 500

El sistema SHALL responder `422` a toda entrada que no cumpla el contrato, incluyendo parámetro
de ruta no entero, cuerpo malformado, tamaño de página fuera de rango, string con carácter
NUL y contraseña de más de 72 bytes, sin ejecutar el handler de negocio.

#### Scenario: Id de ruta no entero

- **WHEN** se solicita un recurso con un identificador que no es entero en la ruta
- **THEN** la respuesta es `422` y el handler del recurso no se ejecuta

#### Scenario: JSON malformado

- **WHEN** el cuerpo de la petición no es JSON válido
- **THEN** la respuesta es `422` y no se procesa la operación

#### Scenario: String con carácter NUL

- **WHEN** un campo de texto contiene un carácter NUL
- **THEN** la respuesta es `422` y no se procesa la operación

#### Scenario: Contraseña de más de 72 bytes

- **WHEN** se envía una contraseña de más de 72 bytes
- **THEN** la respuesta es `422` antes de ejecutar bcrypt

### Requirement: Tamaño de página fuera de rango devuelve 422

El sistema SHALL rechazar con `422` cualquier valor de `size` menor que 1 o mayor que 100.

#### Scenario: Size cero

- **WHEN** se solicita un listado con `size = 0`
- **THEN** la respuesta es `422`

#### Scenario: Size mayor a 100

- **WHEN** se solicita un listado con `size = 101`
- **THEN** la respuesta es `422`

### Requirement: Toda colección responde con el envoltorio canónico

Todo endpoint de listado SHALL responder con el envoltorio `{items, total, page, size, pages}` y
SHALL usar `page` desde 1 y `size` con default 20.

#### Scenario: Forma del envoltorio

- **WHEN** se solicita un listado válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

#### Scenario: Default de tamaño

- **WHEN** se solicita un listado sin indicar `size`
- **THEN** la respuesta tiene `size = 20`

### Requirement: Página fuera de rango devuelve 422 con mensaje propio

El sistema SHALL responder `422` con un mensaje que indique la página solicitada y la cantidad de
páginas disponibles cuando se solicita una página mayor que la última existente.

#### Scenario: Página inexistente

- **WHEN** se solicita `page = 4` y existen 3 páginas
- **THEN** la respuesta es `422` con el mensaje «La página 4 no existe: hay 3»

#### Scenario: Página menor que uno

- **WHEN** se solicita `page = 0`
- **THEN** la respuesta es `422`

### Requirement: Cero resultados devuelve una página vacía

El sistema SHALL responder `items` vacío, `total = 0` y `pages = 1` cuando un listado no tiene
resultados.

#### Scenario: Sin resultados

- **WHEN** un listado filtrado no devuelve filas
- **THEN** la respuesta tiene `items` vacío, `total = 0` y `pages = 1`

### Requirement: El total se cuenta con los mismos filtros que la página

El `total` de un listado SHALL contar exactamente las filas que cumplen los mismos filtros que
la página devuelta.

#### Scenario: Total consistente con filtros

- **WHEN** se pagina con filtros activos
- **THEN** `total` refleja la cantidad de filas que cumplen esos filtros

### Requirement: Schemas base por entidad con campos prohibidos

Cada módulo SHALL proveer un schema `Create`, uno `Update` y uno `Read` por entidad, todos con
`extra="forbid"`, y ningún schema SHALL incluir `password_hash`.

#### Scenario: Campo extra rechazado

- **WHEN** se envía un campo no declarado en el schema
- **THEN** la respuesta es `422`

#### Scenario: Ausencia de password_hash

- **WHEN** se inspecciona cualquier schema del módulo
- **THEN** no aparece el campo `password_hash`

### Requirement: PATCH aplica solo los campos enviados

Los schemas `Update` SHALL aplicar únicamente los campos presentes en la petición, ignorando los
omitidos.

#### Scenario: Actualización parcial

- **WHEN** se envía un `PATCH` con un subconjunto de campos
- **THEN** sólo esos campos se modifican y los omitidos conservan su valor

### Requirement: Orden de resolución de errores documentado en cada servicio

Cada servicio SHALL resolver las condiciones de error en el orden `404 → 403 → 409 → 422`, de
modo que el estado HTTP devuelto sea el de la primera condición que se cumpla.

#### Scenario: Recurso inexistente antes que permiso

- **WHEN** una petición combina un recurso inexistente con falta de permiso
- **THEN** la respuesta es `404`

#### Scenario: Permiso antes que conflicto

- **WHEN** una petición combina falta de permiso con conflicto de unicidad
- **THEN** la respuesta es `403`