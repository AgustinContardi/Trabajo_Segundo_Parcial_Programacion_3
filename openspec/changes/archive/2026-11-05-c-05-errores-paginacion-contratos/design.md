# Design

## Context

Ver `proposal.md` — Why. El código base ya provee `BaseRepository`, `UnitOfWork` y `paginar()`
(`parcial/app/core/`), más los módulos del TP cap. 1-4 con `models`, `schemas`, `service` y
`router` (sin repositorios ni UoW por módulo, que llegan en C-06 … C-10). Las migraciones
0001-0004 ya están aplicadas. Este change no toca el esquema ni agrega endpoints nuevos: fija
los contratos transversales que los módulos posteriores van a copiar.

## Goals / Non-Goals

**Goals:**
- Un único punto de traducción de `IntegrityError` por nombre de constraint, reutilizable por
  todos los módulos.
- Un único manejador de `RequestValidationError` registrado en la app, que cubra los casos del
  checklist (id no entero, size fuera de rango, JSON malformado, NUL, contraseña de 73 bytes)
  y nunca devuelva 500.
- Conexión de `paginar()` a todos los listados existentes, con validación de `page`/`size` y
  mensaje de página inexistente.
- Base de schemas por módulo (`Create`/`Update`/`Read`) con `extra="forbid"`, `exclude_unset`
  en PATCH y sin `password_hash`.
- Convención documentada de orden de resolución `404 → 403 → 409 → 422` en cada servicio.

**Non-Goals:**
- No se reescriben los módulos del TP cap. 1-4 a seis capas (eso es C-06 … C-10).
- No se agregan endpoints nuevos ni se cambia el esquema.
- No se implementa autenticación ni autorización (C-11 … C-13).
- No se toca el despliegue.

## Decisions

### D-1: Traductor de `IntegrityError` en `app/core/errors.py`

- **Decisión**: un módulo `app/core/errors.py` expone una función `traducir_integrity_error(exc)`
  que inspecciona `exc.orig` (el `asyncpg`/`psycopg` error) y el nombre del constraint, y
  devuelve una `HTTPException` con el código y mensaje correspondientes. Los servicios la invocan
  dentro del `except IntegrityError` al salir del `async with uow`.
- **Alternativas**: traducir en cada servicio (se replica y se olvida un caso); usar un
  exception handler global de FastAPI (más limpio pero oculta el control de flujo y dificulta
  el orden 404→403→409→422). Se descarta el handler global para `IntegrityError` porque el
  servicio debe decidir el orden; el handler global queda sólo para `RequestValidationError`.
- **Rationale**: un solo punto de verdad para los mensajes (RD-03) y control explícito del orden.

### D-2: Tabla de constraints → código/mensaje

- **Decisión**: un diccionario `CONSTRAINTS` mapea nombre de constraint → `(status_code, mensaje)`.
  Se incluyen los constraints existentes del TP (unicidades de email, nombre de editorial/género,
  ISBN parcial, FKs, CHECKs) y se extiende en cada change posterior cuando aparezcan nuevos.
- **Rationale**: agregar un constraint nuevo es agregar una línea; no se toca la lógica.
- **Convención de mensajes**: español, segunda persona, sin jerga («Ya existe un libro con ese
  ISBN», «No se puede registrar una venta con un libro inexistente»).

### D-3: Manejador de `RequestValidationError` registrado en `main.py`

- **Decisión**: un `@app.exception_handler(RequestValidationError)` en `main.py` (o en
  `app/core/errors.py` y registrado desde `main.py`) construye una respuesta `422` con un cuerpo
  estable `{ "detail": [ { "loc", "msg", "type" } ] }` (formato estándar de FastAPI) y **nunca**
  propaga la excepción. Cubre: id no entero en ruta (FastAPI ya genera 422 por type mismatch,
  pero se verifica que no llegue a 500), `size` fuera de rango (validación de `Query`),
  JSON malformado, NUL en string (`constr`/`str` con `pattern` o validador), contraseña de
  73 bytes (validador `max_length` en bytes o validador explícito).
- **Alternativa**: confiar en el handler por defecto de FastAPI. Se descarta porque el checklist
  exige que **ninguna** entrada inválida termine en 500 y el handler por defecto no cubre NUL
  ni bytes en contraseña de forma uniforme.
- **Rationale**: un solo punto de validación transversal, observable y testeable.

### D-4: Validación de contraseña por bytes

- **Decisión**: los schemas que reciben contraseña usan un validador Pydantic que rechaza si
  `len(password.encode("utf-8")) > 72`, con mensaje propio. Se aplica en registro, alta de
  personal y cambio de contraseña.
- **Rationale**: bcrypt trunca a 72 bytes; aceptar más produce un 500 o un hash silenciosamente
  truncado. La validación explícita da 422 (RN-15).

### D-5: Conexión de `paginar()` a los listados

- **Decisión**: cada endpoint de listado construye el `SELECT` filtrado y llama a
  `paginar(session, stmt, page, size)`. Los parámetros `page` y `size` se declaran con `Query`
  (`page: int = 1`, `size: int = 20`) y `paginar()` valida rangos y página inexistente.
- **Rationale**: reutiliza la validación ya implementada en C-02; no se duplica lógica.
- **Nota**: el `total` se cuenta con el mismo `stmt` filtrado (ya garantizado por `paginar()`).

### D-6: Base de schemas por módulo

- **Decisión**: cada módulo define `XxxCreate`, `XxxUpdate`, `XxxRead` en `schemas.py`, todos
  con `model_config = ConfigDict(extra="forbid")`. Los `Update` usan `model_config` con
  `extra="forbid"` y los servicios aplican `dto.model_dump(exclude_unset=True)`. Ningún schema
  incluye `password_hash` (se expone sólo vía `UsuarioRead` sin ese campo, o se omite).
- **Alternativa**: un schema genérico compartido. Se descarta porque el contrato difiere por
  entidad (campos, validaciones) y el checklist exige uno por operación.
- **Rationale**: `extra="forbid"` es lo que hace que mandar `rol` o `stock` dé 422 (RN-02,
  RN-09, RN-11).

### D-7: Orden de resolución de errores en los servicios

- **Decisión**: cada servicio documenta y aplica el orden `404 → 403 → 409 → 422`: primero se
  verifica la existencia del recurso de la ruta (404), luego el permiso (403), luego conflictos
  con lo guardado (409, incluida la traducción de `IntegrityError`), y por último el contrato
  (422, que en la práctica ya se resolvió en el router/schema antes de entrar al servicio).
- **Rationale**: coincide con CV-08 y con los casos del checklist (C-01, C-06, C-07).

### D-8: Mensajes de error (RD-03)

- **Decisión**: todos los mensajes de error de negocio se escriben en español, en segunda persona
  y sin jerga de base. Se centraliza la convención en `app/core/errors.py` (constantes o
  helpers) para que los módulos la reutilicen.
- **Rationale**: RD-03 es consecuencia operativa de RN-15; centralizar evita inconsistencias.

## Risks / Trade-offs

- [El diccionario de constraints queda incompleto] → Se extiende en cada change posterior cuando
  aparezcan nuevos constraints; el traductor lanza un error genérico (409 sin detalle) si no
  encuentra el nombre, nunca el texto de PostgreSQL.
- [El handler de `RequestValidationError` oculta casos no cubiertos] → Se registran los casos del
  checklist como escenarios y se agregan tests por caso en C-19.
- [Los schemas base se duplican por módulo] → Se acepta la duplicación a cambio de contratos
  claros por entidad; la convención se documenta en la KB y en este design.

## Migration Plan

No aplica: no hay cambios de esquema ni de datos. El change es aditivo sobre `app/core/` y
prepara la convención para los módulos posteriores. Rollback: revertir los archivos nuevos.

## Open Questions

Ninguna que afecte specs, enfoque o desglose de tareas.