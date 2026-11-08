# suite-pytest-evidencia Specification

## Purpose

Define el contrato de comportamiento de la suite de pruebas automatizada con pytest contra PostgreSQL real y de la carpeta de evidencia `parcial/evidencia/` requerida por los cambios C-14 y C-15.

## Requirements

### Requirement: Solo pytest en tests/

El sistema SHALL tener una suite `tests/` que contenga exclusivamente archivos de prueba pytest, sin archivos `.http` ni `.sql` sueltos.

#### Scenario: No archivos .http ni .sql en tests/

- **WHEN** se listan los archivos del directorio `tests/`
- **THEN** no existe ningún archivo con extensión `.http` ni `.sql`

### Requirement: Ejecución contra PostgreSQL real

Los tests de API e integración de `tests/` SHALL ejecutarse contra una base de datos PostgreSQL real,
nunca contra SQLite. Los tests unitarios que no tocan la base (por ejemplo, mapeo de errores, schemas o
dependencias con `Mock`) podrán usar dobles de prueba, pero SHALL declararlo en el docstring del archivo o
del test y MUST NOT presentarse como evidencia de integración con PostgreSQL.

#### Scenario: Tests pasan contra PostgreSQL

- **WHEN** se ejecuta `pytest -q`
- **THEN** la ejecución finaliza con código de salida 0 y los tests de API usan la base PostgreSQL
  configurada, sin SQLite

#### Scenario: Test unitario declarado

- **WHEN** un test usa `Mock` o `dependency_overrides` porque no necesita base
- **THEN** su docstring o el del archivo indica que es unitario y no se cuenta como evidencia de base real

### Requirement: Comparación por status y body

El sistema SHALL validar las respuestas de la API comparando código de estado HTTP y cuerpo de respuesta, nunca usando `model_dump()` para la comparación.

#### Scenario: Test compara status y body

- **WHEN** un test de API verifica una respuesta
- **THEN** compara el `status_code` y el `response.json()` (body), no serializaciones `model_dump()`

### Requirement: Registro de usuario

El sistema SHALL incluir un test que valide el registro de un nuevo usuario.

#### Scenario: Registro exitoso

- **WHEN** se envía una petición de registro con datos válidos
- **THEN** la respuesta tiene status 201 y el cuerpo confirma la creación del usuario

### Requirement: Login y límite de tasa 429

El sistema SHALL incluir tests que validen el login exitoso y el límite de tasa (429 Too Many Requests) tras intentos fallidos repetidos.

#### Scenario: Login exitoso

- **WHEN** se envían credenciales válidas al endpoint de login
- **THEN** la respuesta tiene status 200 y establece la cookie `access_token` HttpOnly

#### Scenario: Límite de tasa 429

- **WHEN** se realizan múltiples intentos de login fallidos consecutivos
- **THEN** la respuesta tiene status 429

### Requirement: Roles y revocación

El sistema SHALL incluir tests que validen la autorización por roles y la revocación de tokens (logout).

#### Scenario: Acceso denegado por rol insuficiente

- **WHEN** un usuario sin el rol requerido accede a un endpoint protegido
- **THEN** la respuesta tiene status 403

#### Scenario: Revocación de token (logout)

- **WHEN** un usuario autenticado cierra sesión
- **THEN** el token ya no es válido y la respuesta tiene status 200 o 204

### Requirement: Venta con rollback

El sistema SHALL incluir un test que valide que una venta fallida revierte todos los cambios (transacción con rollback).

#### Scenario: Venta fallida hace rollback

- **WHEN** se intenta crear una venta que falla por datos inválidos
- **THEN** no quedan cambios parciales persistidos en la base de datos

### Requirement: Invariante del stock

El sistema SHALL incluir un test que valide que el stock no puede quedar negativo tras una venta o reposición.

#### Scenario: Stock no queda negativo

- **WHEN** se intenta vender más unidades de las disponibles
- **THEN** la operación falla y el stock permanece sin cambios (invariante preservada)

### Requirement: Baja lógica

El sistema SHALL incluir un test que valide que las bajas son lógicas (marcación, no eliminación física).

#### Scenario: Baja lógica de registro

- **WHEN** se da de baja un registro
- **THEN** el registro sigue existiendo en la base de datos pero marcado como inactivo/eliminado lógicamente

### Requirement: Evidencia de C-14 y C-15

El sistema SHALL contar con la carpeta `parcial/evidencia/` conteniendo la captura de consola de C-15 (consultas del detalle de una venta con 2 y con 4 renglones, `SQL_ECHO=true`) y la captura de `psql` de C-14.

#### Scenario: Evidencia de C-15 existe

- **WHEN** se inspecciona `parcial/evidencia/`
- **THEN** existe la captura de consola de C-15 con consultas del detalle de una venta (2 y 4 renglones) y `SQL_ECHO=true`

#### Scenario: Evidencia de C-14 (psql) existe

- **WHEN** se inspecciona `parcial/evidencia/`
- **THEN** existe la captura de `psql` de C-14

### Requirement: El orden 401 antes que 403 se verifica de verdad

`tests/test_control_cambio_password.py` SHALL contener una prueba real —sin cuerpo vacío ni `pass`— que
demuestre que una petición sin cookie a una ruta con `control_cambio_password` responde `401` antes de que
el control evalúe `debe_cambiar_password`, y que con una cookie cuyo usuario tiene la bandera en `true`
responde `403`. La prueba SHALL fallar si el orden se invierte.

#### Scenario: Sin cookie gana el 401

- **WHEN** se llama una ruta del grupo protegido sin `access_token`
- **THEN** la respuesta es `401` y no un `403` del control de cambio

#### Scenario: Con bandera gana el 403

- **WHEN** se llama la misma ruta con la cookie de un usuario con `debe_cambiar_password = true`
- **THEN** la respuesta es `403` con `{"detail": "No autorizado"}`

### Requirement: Evidencia del aviso de comprobante junto a las capturas críticas

`parcial/evidencia/` SHALL contener la captura del aviso de `BackgroundTasks` de C-10, además de las
capturas de C-14 y C-15, de modo que las tres evidencias críticas del §10/§12 estén en la misma carpeta.

#### Scenario: Tres capturas críticas juntas

- **WHEN** se lista `parcial/evidencia/`
- **THEN** aparecen las capturas de C-10 (aviso tras la respuesta), C-14 (psql de sólo agregado) y C-15
  (conteo de SELECT con 2 y 4 renglones)
