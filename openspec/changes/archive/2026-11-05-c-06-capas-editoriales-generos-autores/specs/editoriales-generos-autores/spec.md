# Spec Delta — editoriales-generos-autores

## Purpose

Define el comportamiento de los módulos `editoriales`, `generos` y `autores` tras su
migración a seis capas: alta con unicidad, actualización parcial, listados paginados y
listado de libros por entidad, con el contrato de capas (router construye el UoW, el
servicio lo abre, la precarga vive sólo en `repository.py`).

## ADDED Requirements

### Requirement: Alta de editorial, género y autor

El sistema SHALL permitir crear una editorial, un género y un autor, respondiendo `201`
con la entidad creada. Si el nombre (o el par que define la unicidad) ya existe, SHALL
responder `409` con un mensaje propio, sin exponer texto de la base.

#### Scenario: Alta exitosa

- **WHEN** se envía un cuerpo válido a `POST /editoriales`, `/generos` o `/autores`
- **THEN** la respuesta es `201` con la entidad creada, incluyendo su `id`

#### Scenario: Duplicado

- **WHEN** se intenta crear una entidad cuyo nombre (o clave de unicidad) ya existe
- **THEN** la respuesta es `409` con un mensaje propio y no se crea la fila

#### Scenario: Contrato inválido

- **WHEN** el cuerpo incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422` y no se ejecuta el alta

### Requirement: Actualización parcial de editorial y autor

El sistema SHALL permitir actualizar una editorial y un autor aplicando únicamente los
campos presentes en la petición, respondiendo `200`. Si el recurso no existe SHALL
responder `404`; si la unicidad choca SHALL responder `409`; si el contrato se viola
SHALL responder `422`. El género no admite actualización parcial en este change.

#### Scenario: Actualización parcial

- **WHEN** se envía un `PATCH` con un subconjunto de campos a
  `/editoriales/{id}` o `/autores/{id}`
- **THEN** sólo esos campos se modifican y los omitidos conservan su valor, con `200`

#### Scenario: Recurso inexistente

- **WHEN** se envía un `PATCH` a un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Unicidad en actualización

- **WHEN** el `PATCH` intenta un valor que choca con una unicidad existente
- **THEN** la respuesta es `409` con mensaje propio

#### Scenario: Contrato inválido en actualización

- **WHEN** el `PATCH` incluye un campo no declarado o un tipo inválido
- **THEN** la respuesta es `422`

### Requirement: Listados paginados de editorial, género y autor

Todo listado de editoriales, géneros y autores SHALL responder con el envoltorio
`{items, total, page, size, pages}`, con `page` desde 1 y `size` default 20 en el rango
1..100. Una página inexistente SHALL responder `422` con mensaje propio y cero
resultados SHALL devolver `items` vacío, `total = 0` y `pages = 1`.

#### Scenario: Forma del envoltorio

- **WHEN** se solicita `GET /editoriales`, `/generos` o `/autores` válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

#### Scenario: Default de tamaño

- **WHEN** se solicita un listado sin indicar `size`
- **THEN** la respuesta tiene `size = 20`

#### Scenario: Página inexistente

- **WHEN** se solicita una página mayor que la última existente
- **THEN** la respuesta es `422` con un mensaje que indica la página y la cantidad

#### Scenario: Cero resultados

- **WHEN** un listado filtrado no devuelve filas
- **THEN** la respuesta tiene `items` vacío, `total = 0` y `pages = 1`

### Requirement: Listado de libros por entidad

El sistema SHALL permitir listar los libros de una editorial, un género o un autor.
Si la entidad no existe SHALL responder `404`. Los libros dados de baja SHALL quedar
excluidos del resultado.

#### Scenario: Entidad existente

- **WHEN** se solicita `GET /editoriales/{id}/libros`, `/generos/{id}/libros` o
  `/autores/{id}/libros` con un id existente
- **THEN** la respuesta es `200` con los libros vigentes de esa entidad

#### Scenario: Entidad inexistente

- **WHEN** se solicita el listado de libros de un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Exclusión de dados de baja

- **WHEN** existen libros vigentes y dados de baja para la entidad
- **THEN** el resultado incluye sólo los vigentes (`borrado_en IS NULL`)

### Requirement: Unit of Work por módulo compone el repositorio con la misma sesión

Cada uno de los tres módulos SHALL proveer un Unit of Work que extienda el base y
componga su repositorio pasándole la misma sesión recibida.

#### Scenario: Misma sesión

- **WHEN** se instancia el Unit of Work de un módulo con una sesión
- **THEN** su repositorio usa esa misma sesión

### Requirement: Servicio no recibe AsyncSession ni construye el UoW

Ningún servicio de los tres módulos SHALL declarar un parámetro de tipo
`AsyncSession` ni instanciar un Unit of Work. El router SHALL construir el UoW con una
dependencia y pasarlo al servicio, que lo abre con `async with`.

#### Scenario: Ausencia de AsyncSession en el servicio

- **WHEN** se inspecciona `app/modules/{editoriales,generos,autores}/service.py`
- **THEN** no aparece `AsyncSession` ni `UnitOfWork(`

### Requirement: Precarga sólo en repository.py

Toda precarga (`selectinload` u otra) de los tres módulos SHALL vivir únicamente en
`repository.py`. Ni `service.py` ni `router.py` SHALL contener precarga.

#### Scenario: Precarga fuera de repository.py

- **WHEN** se busca `selectinload` en `service.py` y `router.py` de los tres módulos
- **THEN** no se encuentra ninguna ocurrencia