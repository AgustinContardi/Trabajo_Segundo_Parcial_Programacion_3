# Spec Delta — api-contracts

## MODIFIED Requirements

### Requirement: Orden de resolución de errores documentado en cada servicio

Cada servicio SHALL resolver las condiciones de error en el orden `404 → 403 → 409 → 422`, de
modo que el estado HTTP devuelto sea el de la primera condición que se cumpla. Cada servicio SHALL
llevar además un comentario de contrato `CV-08` que declare ese orden y qué condición corresponde a su
dominio. Si un servicio no puede producir una de las condiciones (por ejemplo, un `409` de unicidad en
`autores`), el comentario SHALL explicarlo en lugar de prometer una rama inalcanzable.

#### Scenario: Recurso inexistente antes que permiso

- **WHEN** una petición combina un recurso inexistente con falta de permiso
- **THEN** la respuesta es `404`

#### Scenario: Permiso antes que conflicto

- **WHEN** una petición combina falta de permiso con conflicto de unicidad
- **THEN** la respuesta es `403`

#### Scenario: Contrato CV-08 presente

- **WHEN** se busca `CV-08` en `parcial/app/modules/*/service.py`
- **THEN** los siete módulos de dominio lo declaran y el orden escrito coincide con el que implementa el
  servicio

## ADDED Requirements

### Requirement: Los mensajes de validación describen el tipo esperado

El manejador de `RequestValidationError` SHALL asignar a cada tipo de error de Pydantic un mensaje en
español que describa el tipo esperado. `bool_type` → «Debe ser un valor booleano válido»; `float_type` y
`decimal_parsing` → «Debe ser un número válido»; los tres tipos enteros conservan «Debe ser un número
entero válido». Ningún mensaje SHALL contener texto de Pydantic ni de PostgreSQL (`RN-15`, `RD-03`).

#### Scenario: Booleano inválido

- **WHEN** una petición envía un valor no booleano donde el contrato espera `bool`
- **THEN** la respuesta es `422` con `msg = "Debe ser un valor booleano válido"` y `type = "bool_type"`

#### Scenario: Número decimal inválido

- **WHEN** una petición envía un valor no numérico donde el contrato espera un decimal
- **THEN** la respuesta es `422` con `msg = "Debe ser un número válido"` y `type = "float_type"` o
  `"decimal_parsing"`

#### Scenario: Entero inválido conserva su mensaje

- **WHEN** una petición envía un valor no entero donde el contrato espera un entero
- **THEN** la respuesta es `422` con `msg = "Debe ser un número entero válido"`

#### Scenario: Sin texto interno

- **WHEN** se revisa cualquier mensaje de validación
- **THEN** no contiene nombres de tablas, columnas, constraints ni trazas de Pydantic o PostgreSQL
