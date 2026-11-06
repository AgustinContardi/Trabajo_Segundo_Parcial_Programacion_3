# libros Specification

## Purpose

Define el comportamiento del módulo `libros` tras su migración a seis capas: alta de
libro con `stock_inicial` y autores anidados (libro + `libro_autor` + movimiento
«Stock inicial» en una sola transacción), punto único de escritura de stock, actualización
parcial sólo de título y precio, y lecturas paginadas con filtro por título y género y
búsqueda con parámetro ligado. También fija el contrato de capas (router construye el
UoW, el servicio lo abre, la precarga vive sólo en `repository.py`) y el filtro de
borrados por defecto del repositorio.

## Requirements

### Requirement: Alta de libro con stock inicial

El sistema SHALL permitir crear un libro mediante `POST /libros` con `stock_inicial`
(no `stock`) y `autores: [{autor_id, rol, orden}]`, respondiendo `201`. En una sola
transacción SHALL crear el libro, sus `libro_autor` y un `movimiento_stock` con
`cantidad = stock_inicial` y `motivo = 'Stock inicial'` (`venta_id` nulo). Conflictos
de ISBN (entre vigentes) o de FK SHALL responder `409`; `precio <= 0` o
`stock_inicial < 0` SHALL responder `422`.

#### Scenario: Alta exitosa con stock inicial y autores

- **WHEN** un administrador envía un cuerpo válido a `POST /libros` con `stock_inicial`
  y al menos un autor
- **THEN** la respuesta es `201` con el libro creado, `stock` igual a `stock_inicial`,
  y sus autores
- **AND** existe un `movimiento_stock` con `cantidad = stock_inicial` y
  `motivo = 'Stock inicial'` para ese libro

#### Scenario: ISBN que choca con un libro vigente

- **WHEN** se intenta crear un libro cuyo ISBN ya pertenece a un libro vigente
- **THEN** la respuesta es `409` con mensaje propio y no se crea la fila ni el
  movimiento

#### Scenario: ISBN reutilizado tras baja lógica

- **WHEN** se crea un libro con el ISBN de un libro dado de baja
- **THEN** la respuesta es `201` (el índice único es parcial)

#### Scenario: FK inexistente

- **WHEN** `editorial_id`, `genero_id` o un `autor_id` no existe
- **THEN** la respuesta es `409` con mensaje propio

#### Scenario: Contrato inválido (precio o stock)

- **WHEN** `precio <= 0` o `stock_inicial < 0`
- **THEN** la respuesta es `422` y no se ejecuta el alta

#### Scenario: Campo `stock` en el cuerpo

- **WHEN** el cuerpo incluye `stock` (en lugar de `stock_inicial`)
- **THEN** la respuesta es `422` (campo no declarado, `extra="forbid"`)

### Requirement: Actualización parcial de libro (sólo título y precio)

El sistema SHALL permitir actualizar un libro mediante `PATCH /libros/{id}`, aplicando
únicamente `titulo` y `precio` y respondiendo `200`. Mandar `stock` (u otro campo no
declarado) SHALL responder `422`. Si el libro no existe SHALL responder `404`. Si
`precio <= 0` SHALL responder `422`.

#### Scenario: Actualización parcial

- **WHEN** se envía un `PATCH` con un subconjunto de {`titulo`, `precio`} a
  `/libros/{id}`
- **THEN** sólo esos campos se modifican y los omitidos conservan su valor, con `200`

#### Scenario: Mandar `stock`

- **WHEN** el `PATCH` incluye `stock`
- **THEN** la respuesta es `422`

#### Scenario: Recurso inexistente

- **WHEN** se envía un `PATCH` a un id que no existe
- **THEN** la respuesta es `404`

#### Scenario: Precio inválido

- **WHEN** el `PATCH` envía `precio <= 0`
- **THEN** la respuesta es `422`

### Requirement: Consulta de libro

El sistema SHALL permitir consultar un libro mediante `GET /libros/{id}`, respondiendo
`200` con sus datos (incluyendo editorial, género y autores). Si el libro no existe o
está dado de baja SHALL responder `404`.

#### Scenario: Libro existente

- **WHEN** se solicita `GET /libros/{id}` con un id existente y vigente
- **THEN** la respuesta es `200` con los datos del libro, su editorial, género y
  autores

#### Scenario: Libro inexistente o dado de baja

- **WHEN** se solicita `GET /libros/{id}` con un id que no existe o está dado de baja
- **THEN** la respuesta es `404`

### Requirement: Listado paginado de libros

El sistema SHALL permitir listar libros mediante `GET /libros` con parámetros `page`,
`size`, `titulo` y `genero_id`, respondiendo `200` con el envoltorio
`{items, total, page, size, pages}` y excluyendo los libros dados de baja. `size` va
de 1 a 100 con default 20; página fuera de rango SHALL responder `422`; cero
resultados SHALL responder una página vacía (`items: []`, `total: 0`, `pages: 1`).

#### Scenario: Listado paginado

- **WHEN** se solicita `GET /libros` válido
- **THEN** la respuesta es `200` con el envoltorio y los libros vigentes

#### Scenario: Filtro por título

- **WHEN** se envía `titulo`
- **THEN** sólo se devuelven libros cuyo título contiene el texto (sin distinguir
  mayúsculas)

#### Scenario: Filtro por género

- **WHEN** se envía `genero_id`
- **THEN** sólo se devuelven libros de ese género

#### Scenario: Exclusión de borrados

- **WHEN** existen libros dados de baja
- **THEN** no aparecen en el listado

#### Scenario: Búsqueda con inyección

- **WHEN** se envía `titulo = ' OR '1'='1`
- **THEN** la respuesta no rompe ni devuelve todo; se trata como texto literal (lista
  vacía o resultados literales)

#### Scenario: Forma del envoltorio

- **WHEN** se solicita `GET /libros` válido
- **THEN** la respuesta contiene `items`, `total`, `page`, `size` y `pages`

### Requirement: Punto único de escritura de stock

El stock de un libro SHALL cambiar únicamente a través de un solo método que actualiza
`libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar. Ese método es
usado por el alta (motivo `'Stock inicial'`), la reposición (motivo `'Reposición'`,
C-09) y la venta (motivo `'Venta'`, C-16). No SHALL existir otro lugar que escriba
`libro.stock` directamente.

#### Scenario: Alta deja el movimiento «Stock inicial»

- **WHEN** se crea un libro con `stock_inicial = N`
- **THEN** `libro.stock = N` y existe un movimiento con `cantidad = N` y
  `motivo = 'Stock inicial'`

#### Scenario: Reposición deja movimiento de entrada

- **WHEN** se repone stock con cantidad `N > 0`
- **THEN** `libro.stock` aumenta en `N` y existe un movimiento con `cantidad = N`
  y `motivo = 'Reposición'`

#### Scenario: Invariante stock = suma de movimientos

- **WHEN** se consulta el stock de un libro recién creado
- **THEN** `libro.stock = SUM(movimiento_stock.cantidad)` para ese libro

### Requirement: Unit of Work por módulo compone el repositorio con la misma sesión

El módulo SHALL proveer un `LibrosUnitOfWork` que extienda el base y componga su
`LibroRepository` (y un repositorio de `LibroAutor` si aplica) pasándole la misma
sesión recibida.

#### Scenario: Misma sesión

- **WHEN** se instancia el Unit of Work del módulo con una sesión
- **THEN** su repositorio usa esa misma sesión

### Requirement: Servicio no recibe AsyncSession ni construye el UoW

Ningún servicio del módulo SHALL declarar un parámetro de tipo `AsyncSession` ni
instanciar un Unit of Work. El router SHALL construir el UoW con una dependencia y
pasarlo al servicio, que lo abre con `async with`.

#### Scenario: Ausencia de AsyncSession en el servicio

- **WHEN** se inspecciona `app/modules/libros/service.py`
- **THEN** no aparece `AsyncSession` ni `UnitOfWork(`

### Requirement: Precarga sólo en repository.py

Toda precarga (`selectinload`/`joinedload` u otra) del módulo SHALL vivir únicamente
en `repository.py`. Ni `service.py` ni `router.py` SHALL contener precarga.

#### Scenario: Precarga fuera de repository.py

- **WHEN** se busca `selectinload` o `joinedload` en `service.py` y `router.py` del
  módulo
- **THEN** no se encuentra ninguna ocurrencia

### Requirement: Repositorio filtra borrados por defecto

`LibroRepository` SHALL filtrar `borrado_en IS NULL` en sus consultas por defecto
(heredado de `SoftDeleteRepository`), de modo que los libros dados de baja no aparezcan
en `GET /libros`, `GET /libros/{id}` ni en los listados por editorial/género/autor.

#### Scenario: Exclusión por defecto

- **WHEN** se consulta un libro dado de baja por `get_by_id`
- **THEN** retorna `None`

### Requirement: Búsqueda con parámetro ligado

La búsqueda por título SHALL usar `ilike` con un parámetro ligado (bind param), nunca
concatenando el texto del usuario en el SQL.

#### Scenario: Parámetro ligado

- **WHEN** se inspecciona el código de búsqueda
- **THEN** el texto del usuario se pasa como bind param a `ilike`, no se concatena
  en el SQL

### Requirement: Modelo de libro con ISBN parcial y CHECKs

El modelo `Libro` SHALL declarar el índice único parcial `(isbn) WHERE borrado_en IS NULL`,
`CHECK (precio > 0)` y `CHECK (stock >= 0)`. `MovimientoStock` SHALL declarar
`CHECK (cantidad <> 0)`.

#### Scenario: Índice parcial y CHECKs

- **WHEN** se inspecciona el modelo
- **THEN** existen el índice único parcial del ISBN y los CHECK de precio y stock

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
