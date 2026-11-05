# Proposal

## Why

C-02 ya entrega `BaseRepository`, `UnitOfWork` y `paginar()`, pero la transversalidad que
todos los módulos posteriores (C-06 … C-16) van a repetir todavía no está fijada:
cómo se traduce un `IntegrityError` a HTTP, cómo se valida la entrada sin terminar en
500, cómo se conecta `paginar()` a los listados y cómo se arman los schemas por módulo.
Si esta fase queda floja, cada módulo arrastra el defecto y `RN-15` (ningún texto interno de
la base, ningún 500 por entrada inválida) se rompe en cascada. Esta es la fase de
contratos: se hace una sola vez, antes de los módulos.

## What Changes

- Se introduce un traductor de `IntegrityError` por **nombre de constraint** a `409`/`422`
  con mensaje propio en español, en segunda persona y sin jerga de base (`RD-03`);
  el texto de PostgreSQL nunca sale al cliente (`RN-15`).
- Se agrega un manejador propio de `RequestValidationError` que cubre `{id}` no entero en la
  ruta, `size` fuera de rango, JSON malformado, NUL en un string y contraseña de 73 bytes,
  respondiendo siempre `422` y nunca `500`.
- Se conecta `paginar()` en todos los listados existentes: `page` desde 1, `size` 1..100
  (default 20), página fuera de rango → `422` («La página 4 no existe: hay 3»), cero
  resultados → `items: []`, `total: 0`, `pages: 1`, y `total` contado con los mismos
  filtros que la página.
- Se establece la base de schemas por módulo: un `Create`, un `Update` y un `Read` por
  entidad, todos con `extra="forbid"`, los `PATCH` aplicando `exclude_unset`, y ningún
  `password_hash` en ningún schema (`CV-07`).
- Se documenta el orden de resolución de errores `404 → 403 → 409 → 422` (`CV-08`) en el
  servicio de cada módulo.
- Se establece la convención de mensajes de error en español, segunda persona, sin jerga
  (`RD-03`).

## Capabilities

### New Capabilities

- `api-contracts`: contratos HTTP transversales del parcial — traducción de `IntegrityError`
  por constraint a `409`/`422` sin texto interno, manejador propio de `RequestValidationError`
  (nunca `500`), envoltorio de paginación conectado a los listados, base de schemas
  `Create`/`Update`/`Read` con `extra="forbid"` y `exclude_unset`, y orden de resolución
  `404 → 403 → 409 → 422` documentado en cada servicio.

### Modified Capabilities

<!-- Ninguna: los requisitos existentes de core-repositories (paginación) no cambian; C-05
     los conecta a los listados, no los redefine. -->

## Impact

- Afecta `app/core/` (nuevo módulo de traducción de errores / handlers) y todos los
  `app/modules/*/schemas.py` y `app/modules/*/service.py` que se creen en C-06 … C-16.
- Afecta `main.py` (registro del handler de `RequestValidationError` y del traductor de
  `IntegrityError`).
- No cambia el esquema de base ni las migraciones.
- Habilita C-06, C-07 y C-11 (gate 2 del roadmap).