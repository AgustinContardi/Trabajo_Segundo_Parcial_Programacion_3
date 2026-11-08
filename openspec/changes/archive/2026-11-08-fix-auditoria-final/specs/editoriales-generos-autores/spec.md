# Spec Delta — editoriales-generos-autores

## MODIFIED Requirements

### Requirement: Alta de editorial, género y autor

El sistema SHALL permitir crear una editorial, un género y un autor, respondiendo `201`
con la entidad creada. Si el nombre ya existe en una entidad que declara unicidad —`editorial.nombre` o
`genero.nombre`— SHALL responder `409` con un mensaje propio, sin exponer texto de la base. `autor` no
tiene unicidad de dominio en este sistema: dos autores con el mismo `nombre` y `nacionalidad` son válidos
y `POST /autores` MUST NOT prometer un `409` por duplicado.

#### Scenario: Alta exitosa

- **WHEN** se envía un cuerpo válido a `POST /editoriales`, `/generos` o `/autores`
- **THEN** la respuesta es `201` con la entidad creada, incluyendo su `id`

#### Scenario: Duplicado

- **WHEN** se intenta crear una editorial o un género cuyo nombre ya existe
- **THEN** la respuesta es `409` con un mensaje propio y no se crea la fila

#### Scenario: Autores homónimos

- **WHEN** se crea un autor con el mismo `nombre` y `nacionalidad` que otro existente
- **THEN** la respuesta es `201` y quedan dos filas distintas

#### Scenario: Contrato inválido

- **WHEN** el cuerpo incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422` y no se ejecuta el alta

### Requirement: Actualización parcial de editorial y autor

El sistema SHALL permitir actualizar una editorial y un autor aplicando únicamente los
campos presentes en la petición, respondiendo `200`. Si el recurso no existe SHALL
responder `404`; si la unicidad de la editorial choca SHALL responder `409`; si el contrato se viola
SHALL responder `422`. Como `autor` no declara unicidad, `PATCH /autores/{id}` no puede producir un `409`
por duplicado: la traducción de `IntegrityError` queda como defensa ante constraints futuras y así SHALL
documentarse en el servicio. El género no admite actualización parcial en este change.

#### Scenario: Actualización parcial

- **WHEN** se envía un `PATCH` con un subconjunto de campos a
  `/editoriales/{id}` o `/autores/{id}`
- **THEN** sólo esos campos se modifican y los omitidos conservan su valor, con `200`

#### Scenario: Recurso inexistente

- **WHEN** se envía un `PATCH` a un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Unicidad en actualización

- **WHEN** el `PATCH /editoriales/{id}` intenta un nombre que ya existe
- **THEN** la respuesta es `409` con mensaje propio

#### Scenario: Autor sin unicidad

- **WHEN** el `PATCH /autores/{id}` cambia `nombre` o `nacionalidad` a valores que ya tiene otro autor
- **THEN** la respuesta es `200` (no hay unicidad que choque)

#### Scenario: Contrato inválido en actualización

- **WHEN** el `PATCH` incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422`

## ADDED Requirements

### Requirement: Consulta de género por id

El sistema SHALL exponer `GET /generos/{genero_id}` y responder `200` con `GeneroRead`
(`id`, `nombre`). Un id inexistente SHALL responder `404` con el mensaje `"Género no encontrado"`, igual
que la lectura de libros por género. La ruta SHALL ser pública, como el resto de las lecturas del catálogo.

#### Scenario: Género existente

- **WHEN** se solicita `GET /generos/{id}` con un id existente
- **THEN** la respuesta es `200` con `id` y `nombre`

#### Scenario: Género inexistente

- **WHEN** se solicita `GET /generos/{id}` con un id que no existe
- **THEN** la respuesta es `404` con `{"detail": "Género no encontrado"}`

#### Scenario: Ruta publicada

- **WHEN** se inspecciona `openapi.json`
- **THEN** existe `GET /generos/{genero_id}` junto a `GET /generos/{genero_id}/libros`
