# Proposal

## Why

El parcial ya tiene toda la API implementada y los cambios C-01 a C-18 están cerrados, pero no existe una suite de tests automatizada con pytest que corra contra PostgreSQL real, ni una carpeta `parcial/evidencia/` con las capturas exigidas por C-14 y C-15. Este change cubre esa brecha para que la entrega sea verificable con `pytest -q` y la evidencia archive en el `.zip`.

## What Changes

- Crear suite `tests/` con sólo pytest, contra PostgreSQL real (nunca SQLite), comparando status + body (no `model_dump()`): al menos registro, login y 429, roles y revocación, venta con rollback, invariante del stock y baja lógica. (RD-01: no está en la consigna.)
- Crear `parcial/evidencia/` con dos capturas: consola de C-15 (consultas del detalle de una venta con 2 y 4 renglones, `SQL_ECHO=true`) y `psql` de C-14.
- Verificar `pytest -q` verde y que `tests/` no quede con `.http` ni `.sql` sueltos.

## Capabilities

### New Capabilities

- `suite-pytest-evidencia`: suite de pruebas pytest contra PostgreSQL real que valida registro, login/429, roles/revocación, venta con rollback, invariante del stock y baja lógica, más la carpeta `parcial/evidencia/` con las capturas de C-14 y C-15. Cada caso compara status + body, nunca `model_dump()`.

### Modified Capabilities

(Ninguno: no se cambian requisitos de ninguna capacidad existente. Es puremente pruebas + evidencia.)

## Impact

- Código nuevo: solo archivos de test bajo `tests/` y archivos de evidencia bajo `parcial/evidencia/`. Sin cambios a código de producción de `parcial/`.
- No se crean migraciones (exactamente 4 archivos en `parcial/migrations/versions/`).
- No se toca `despliegue/`.
- No se hace commit ni push.
