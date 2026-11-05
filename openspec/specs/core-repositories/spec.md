# core-repositories Specification

## Purpose
Provee la infraestructura compartida de acceso a datos del parcial: repositorios genéricos y
especializados para borrado lógico, el gestor de transacciones (Unit of Work) y el envoltorio de
paginación, usados por todos los módulos de dominio.

## Requirements

### Requirement: BaseRepository se construye con sesión y clase de modelo

El sistema SHALL proveer un repositorio genérico que reciba una sesión asincrónica y la clase del
modelo al construirse, sin requerir genéricos en tiempo de ejecución.

#### Scenario: Construcción válida

- **WHEN** se instancia el repositorio con una sesión y una clase de modelo
- **THEN** queda listo para operar sobre esa entidad y esa sesión

### Requirement: BaseRepository obtiene por identificador

El sistema SHALL permitir obtener una entidad por su identificador primario, devolviendo la entidad
o un valor nulo si no existe.

#### Scenario: Entidad existente

- **WHEN** se busca un identificador que existe
- **THEN** se devuelve la entidad correspondiente

#### Scenario: Entidad inexistente

- **WHEN** se busca un identificador que no existe
- **THEN** se devuelve un valor nulo

### Requirement: BaseRepository lista todas las entidades

El sistema SHALL permitir obtener todas las entidades del modelo, con la posibilidad de precargar
relaciones dentro del propio método del repositorio.

#### Scenario: Listado completo

- **WHEN** se solicita el listado sin filtros
- **THEN** se devuelven todas las filas del modelo

### Requirement: BaseRepository cuenta entidades

El sistema SHALL permitir contar las entidades del modelo, respetando los mismos filtros que el
listado correspondiente.

#### Scenario: Conteo consistente

- **WHEN** se cuenta con un conjunto de filtros
- **THEN** el resultado coincide con la cantidad de filas que cumplen esos filtros

### Requirement: BaseRepository agrega con flush y sin commit

El sistema SHALL agregar una entidad nueva y hacer `flush()` para obtener su identificador, sin
confirmar la transacción.

#### Scenario: Alta sin commit

- **WHEN** se agrega una entidad
- **THEN** la entidad queda disponible en la sesión y no se confirma la transacción

### Requirement: BaseRepository actualiza con flush y sin commit

El sistema SHALL actualizar una entidad existente y hacer `flush()`, sin confirmar la transacción.

#### Scenario: Actualización sin commit

- **WHEN** se actualiza una entidad
- **THEN** los cambios quedan en la sesión y no se confirma la transacción

### Requirement: BaseRepository elimina

El sistema SHALL permitir eliminar una entidad de la base, haciendo `flush()` y sin confirmar la
transacción.

#### Scenario: Eliminación sin commit

- **WHEN** se elimina una entidad
- **THEN** la entidad queda marcada para eliminación en la sesión y no se confirma la transacción

### Requirement: Ningún repositorio confirma transacciones

Ningún método de ningún repositorio SHALL invocar `commit()` ni `rollback()` sobre la sesión; sólo
`flush()`.

#### Scenario: Ausencia de commit

- **WHEN** se inspeccionan los métodos del repositorio
- **THEN** no aparece ninguna llamada a `commit()` ni a `rollback()`

### Requirement: SoftDeleteRepository filtra los dados de baja por defecto

El repositorio especializado para borrado lógico SHALL filtrar automáticamente las filas con
`borrado_en` no nulo en `get_by_id`, `get_all` y `count`, de modo que los dados de baja no
aparezcan en catálogo ni en detalle público.

#### Scenario: Listado excluye borrados

- **WHEN** existen entidades vigentes y dadas de baja
- **THEN** el listado devuelve sólo las vigentes

#### Scenario: Búsqueda por id excluye borrados

- **WHEN** se busca por id una entidad dada de baja
- **THEN** se devuelve un valor nulo

### Requirement: SoftDeleteRepository puede incluir los dados de baja

El repositorio especializado SHALL proveer un método que obtenga una entidad por id sin filtrar el
borrado lógico, para que las ventas viejas sigan mostrando el título.

#### Scenario: Inclusión de borrados

- **WHEN** se busca por id una entidad dada de baja con el método que incluye borrados
- **THEN** se devuelve la entidad aunque esté dada de baja

### Requirement: SoftDeleteRepository hace baja lógica

El repositorio especializado SHALL proveer un método que escriba `borrado_en = now()` en lugar de
borrar la fila físicamente.

#### Scenario: Baja lógica

- **WHEN** se invoca la baja lógica sobre una entidad vigente
- **THEN** la fila sigue existiendo con `borrado_en` distinto de nulo

### Requirement: Los métodos de borrado lógico no existen en la base

La clase base SHALL no declarar `get_by_id_including_deleted` ni `soft_delete`; sólo el repositorio
especializado los tiene.

#### Scenario: Ausencia en la base

- **WHEN** se inspecciona la clase base
- **THEN** no aparecen los métodos de borrado lógico

### Requirement: UnitOfWork confirma al salir sin excepción

El gestor de contexto asíncrono SHALL confirmar la transacción al salir del bloque si no hubo
excepción.

#### Scenario: Salida exitosa

- **WHEN** el bloque del Unit of Work termina sin excepción
- **THEN** se invoca `commit()` sobre la sesión

### Requirement: UnitOfWork revierte con excepción

El gestor de contexto asíncrono SHALL revertir la transacción al salir del bloque si hubo
excepción.

#### Scenario: Salida con excepción

- **WHEN** el bloque del Unit of Work lanza una excepción
- **THEN** se invoca `rollback()` sobre la sesión y la excepción se propaga

### Requirement: UnitOfWork no cierra la sesión

El gestor de contexto asíncrono SHALL no cerrar la sesión que no creó, ni al confirmar ni al
revertir.

#### Scenario: Sesión abierta tras el bloque

- **WHEN** el bloque del Unit of Work termina, con o sin excepción
- **THEN** la sesión sigue abierta y su cierre queda a cargo de quien la creó

### Requirement: El UoW se construye con una sesión

El gestor de contexto asíncrono SHALL aceptar una sesión al construirse y exponerla a los
repositorios del módulo.

#### Scenario: Construcción con sesión

- **WHEN** se instancia el Unit of Work con una sesión
- **THEN** los repositorios del módulo usan esa misma sesión

### Requirement: Paginación devuelve el envoltorio canónico

La función de paginación SHALL devolver un objeto con los campos `items`, `total`, `page`, `size` y
`pages`.

#### Scenario: Forma del resultado

- **WHEN** se pagina un conjunto de resultados
- **THEN** el resultado contiene `items`, `total`, `page`, `size` y `pages`

### Requirement: Paginación valida la página

La función de paginación SHALL rechazar con un error 422 cualquier valor de `page` menor que 1, con
un mensaje propio que indique la página solicitada y la cantidad disponible.

#### Scenario: Página menor que uno

- **WHEN** se solicita `page = 0`
- **THEN** se responde 422 con un mensaje propio

#### Scenario: Página fuera de rango

- **WHEN** se solicita una página mayor que la cantidad disponible
- **THEN** se responde 422 con un mensaje que indica la página solicitada y la cantidad de páginas

### Requirement: Paginación valida el tamaño de página

La función de paginación SHALL aceptar `size` entre 1 y 100 inclusive y rechazar con 422 cualquier
valor fuera de ese rango.

#### Scenario: Tamaño válido

- **WHEN** se solicita `size = 20`
- **THEN** se usa ese tamaño en el resultado

#### Scenario: Tamaño fuera de rango

- **WHEN** se solicita `size = 0` o `size = 101`
- **THEN** se responde 422

### Requirement: Paginación tiene tamaño por defecto 20

La función de paginación SHALL usar 20 como tamaño de página cuando no se indique uno.

#### Scenario: Default aplicado

- **WHEN** se pagina sin indicar `size`
- **THEN** el resultado tiene `size = 20`

### Requirement: Paginación con cero resultados devuelve una página vacía

La función de paginación SHALL devolver `items` vacío, `total = 0` y `pages = 1` cuando no hay
resultados.

#### Scenario: Sin resultados

- **WHEN** la consulta no devuelve filas
- **THEN** `items` es vacío, `total` es 0 y `pages` es 1

### Requirement: Paginación cuenta con los mismos filtros

El `total` devuelto por la paginación SHALL contar las filas que cumplen exactamente los mismos
filtros que la página devuelta.

#### Scenario: Total consistente con filtros

- **WHEN** se pagina con filtros activos
- **THEN** `total` refleja la cantidad de filas que cumplen esos filtros

### Requirement: El UoW de módulo compone repositorios con la misma sesión

Cada módulo SHALL proveer un Unit of Work que extienda el base y componga sus repositorios
pasándoles la misma sesión recibida.

#### Scenario: Misma sesión en todos los repositorios

- **WHEN** se instancia el Unit of Work de un módulo con una sesión
- **THEN** todos sus repositorios usan esa misma sesión

### Requirement: Contrato documentado en cada archivo

Cada archivo de la capa SHALL contener un comentario de contrato que indique quién construye, quién
abre, quién confirma y quién cierra la transacción.

#### Scenario: Comentario presente

- **WHEN** se lee cualquiera de los archivos de la capa
- **THEN** contiene el comentario de contrato con los cuatro roles
