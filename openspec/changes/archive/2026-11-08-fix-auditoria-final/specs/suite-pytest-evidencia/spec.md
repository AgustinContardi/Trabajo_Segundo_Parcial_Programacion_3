# Spec Delta — suite-pytest-evidencia

## MODIFIED Requirements

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

## ADDED Requirements

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
