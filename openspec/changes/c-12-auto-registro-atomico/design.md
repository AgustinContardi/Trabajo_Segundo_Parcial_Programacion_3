# Design — C-12 auto-registro-atomico

## Context

Ver `proposal.md` para la motivación y `specs/auto-registro-clientes/spec.md` para el contrato observable.

Estado actual relevante en `parcial/`:

- `app/modules/usuarios/` ya tiene `models.py` (`Usuario`, `AsignacionRol`), `repository.py` (`UsuarioRepository`, `IntentoAccesoRepository`), `unit_of_work.py` (`UsuariosUnitOfWork` con `usuarios` e `intentos`), `schemas.py` (`UsuarioCreate`, `UsuarioRead`, `LoginRequest`, `LoginResponse`, `YoResponse`), `service.py` (login) y `router.py` (`POST /auth/login`, `POST /auth/logout`, `GET /auth/yo`).
- `UsuarioCreate` existe con `extra="forbid"`, `SinNulMixin` y el validador de 72 bytes, pero **todavía no se usa**: C-15 lo consumirá para el alta de personal. `UsuarioRead` ya excluye `password_hash`.
- `app/modules/clientes/repository.py` expone `ClienteRepository` con `get_by_id`, `get_by_usuario_id`, `add_perfil` y `ventas_de`; hereda `add()` de `BaseRepository` (sólo `flush()`).
- `app/core/security.py` expone `hash_password(password, rounds=..., semaphore=...)` con `asyncio.to_thread`; `app/core/errors.py` ya mapea `uq_usuario_email` y `uq_cliente_email` a `409` con **mensajes distintos**.
- `app/core/unit_of_work.py` confirma en `__aexit__` si no hubo excepción y revierte si la hubo; no cierra la sesión.
- El `lifespan` de `main.py` ya deja en `app.state` `settings`, `sessionmaker` y `bcrypt_sem`; el router `/auth` ya está montado en el grupo abierto.
- El esquema ya tiene `usuario.email UNIQUE` (`uq_usuario_email`), `cliente.email UNIQUE` (`uq_cliente_email`) y `cliente.usuario_id UNIQUE` (`uq_cliente_usuario_id`). **No hay migraciones en este change.**

Restricciones de arquitectura que el diseño debe respetar: router construye el UoW y el servicio lo abre (`CV-01`); repositorios sólo `flush()` (`CV-02`); servicios reciben el UoW, nunca la sesión; `selectinload` sólo en `repository.py` (`CV-03`); sin lógica de negocio en el router; bcrypt fuera del event loop; `timestamptz` para fechas.

## Governance

**CRÍTICO.** `RN-02` es la operación que justifica el capítulo 6: tres escrituras que no tienen sentido por separado y un `409` que no debe tocar la ficha ajena. El usuario **ya aprobó explícitamente implementar C-12**; este change no reabre el alcance ni pide una nueva aprobación de negocio. Cualquier desvío del contrato de la consigna (por ejemplo, normalizar el email o elegir la forma de la respuesta `201`) queda registrado abajo como decisión de implementación, nunca como regla nueva.

## Goals / Non-Goals

**Goals:**

- Concentrar las tres escrituras de `RN-02` en una única transacción, con el router como único constructor del UoW y el servicio como único que lo abre.
- Delegar la unicidad a la base (`RN-01`): sin consulta previa de existencia, traduciendo `IntegrityError` con el mapa de `CONSTRAINTS` que ya existe.
- Calcular el hash antes de tomar una conexión y reutilizar el semáforo del `lifespan` sin crear estado paralelo.
- Dejar el endpoint en el grupo abierto ya existente, sin tocar `main.py` ni la autorización de C-13.

**Non-Goals:**

- No iniciar sesión después del registro: la consigna no pide emitir cookie ni token en el `201`.
- No reutilizar ni "reclamar" una ficha de `cliente` preexistente; eso es exactamente lo que `RN-02` prohíbe.
- No crear el alta de personal (`POST /usuarios`, C-15), el cambio de contraseña (C-14) ni la administración de roles (C-15).
- No agregar migraciones, columnas, constraints ni reglas de negocio nuevas.
- No agregar validaciones de email/formato no exigidas por la consigna (sólo la normalización descrita abajo, alineada con `LoginRequest`).

## Decisions

### 1. UoW propio del registro, compuesto por tres repositorios sobre una sola sesión

Se agrega `RegistroUnitOfWork(UnitOfWork)` en `parcial/app/modules/usuarios/unit_of_work.py`, con `usuarios: UsuarioRepository`, `roles: AsignacionRolRepository` y `clientes: ClienteRepository`, todos construidos con la **misma** `AsyncSession` que entrega `get_session`. Se expone `get_registro_uow` como dependencia para el router.

Por qué no extender `UsuariosUnitOfWork`: ese UoW existe para el login y su composición (`usuarios` + `intentos`) es la que las pruebas y el flujo de C-11 ya verifican. Sumarle `roles` y `clientes` mezcla dos operaciones con fronteras distintas y hace que un cambio en registro altere el camino de login. Un UoW por operación de negocio es el patrón que el propio `app/core/unit_of_work.py` documenta (`VentasUnitOfWork` compone repositorios de varios módulos), así que componer `ClientesUnitOfWork`/`UsuariosUnitOfWork` no es una excepción arquitectónica.

Alternativa descartada: un `RegistroUnitOfWork` que herede de `UsuariosUnitOfWork` y agregue repositorios; hereda `intentos`, que el registro no usa, y acopla ambas operaciones.

### 2. Repositorio nombrado para `asignacion_rol`

`AsignacionRolRepository(BaseRepository[AsignacionRol])` en `usuarios/repository.py`, sin métodos propios por ahora: el registro sólo necesita `add()` heredado. Existe como punto de composición tipado y como el lugar donde C-15 agregará las consultas de roles vigentes y revocación.

Alternativa descartada: `BaseRepository(session, AsignacionRol)` directo en el UoW; funciona, pero deja al módulo sin el punto de extensión que el resto de las tablas sí tiene.

### 3. El contrato de entrada reutiliza `UsuarioCreate`; la respuesta reutiliza `UsuarioRead`

`Registro` usa `UsuarioCreate` (ya tiene `extra="forbid"`, `SinNulMixin` y el validador de 72 bytes) y responde `UsuarioRead` con `status_code=201`. Así el `422` por `rol`, el `422` por más de 72 bytes y la ausencia de `password_hash` no dependen de un schema nuevo que pueda divergir. Se agrega a `UsuarioCreate` un validador de `email` que aplica `strip().lower()`, replicando la convención que `LoginRequest` ya usa desde C-11; es una decisión de implementación (no una regla de negocio) y C-15 la heredará cuando use el mismo schema.

Alternativa descartada: un `RegistroRequest`/`RegistroResponse` dedicado; duplica validaciones que ya existen y crea dos contratos para el mismo dato. Alternativa descartada: responder el `Cliente`; el recurso creado es la identidad de acceso y la ficha es un efecto de `RN-02`, no el recurso de la ruta.

### 4. Orden de las escrituras y estrategia de atomicidad

El servicio `registrar(uow, data, *, settings, semaphore)` ejecuta, en este orden:

1. `password_hash = await hash_password(data.password, rounds=settings.BCRYPT_ROUNDS, semaphore=semaphore)` — **antes** de `async with uow`.
2. `async with uow:` (una sola vez):
   - `usuario = await uow.usuarios.add(Usuario(email=..., nombre=..., password_hash=...))` → `flush()` asigna `usuario.id` y dispara `uq_usuario_email`.
   - `await uow.roles.add(AsignacionRol(usuario_id=usuario.id, rol="CLIENTE", desde=datetime.now(timezone.utc)))` → `vence_en` y `revocada_en` quedan nulos; `desde` es `timestamptz`.
   - `await uow.clientes.add(Cliente(nombre=..., email=..., usuario_id=usuario.id))` → dispara `uq_cliente_email`.
3. `except IntegrityError` **fuera** del `async with`: `raise traducir_integrity_error(exc)`.
4. `return usuario`.

Por qué el `except` va afuera: si se atrapara adentro, `__aexit__` vería una salida normal y **confirmaría** las filas parciales. Al atrapar afuera, el `IntegrityError` sale del bloque, `__aexit__` ejecuta `rollback()` y recién después se traduce. Esto es exactamente lo que la prueba de atomicidad de `docs/CHECKLIST_ENTREGA.md` §7 verifica con `SELECT count(*) FROM usuario`.

Por qué el `usuario` va primero: su `id` es la FK de las otras dos escrituras. Por qué la ficha va última: así el caso natural de fallo (correo que ya existe como `cliente`) ocurre **después** de las dos primeras escrituras y ejercita el rollback completo, que es el escenario que la consigna pide demostrar.

Por qué no se busca la ficha existente: `RN-02` prohíbe apropiarse de ella. El servicio nunca ejecuta `get_by_email` ni `get_by_usuario_id` antes del alta; la unicidad la garantiza la base (`RN-01`) y un `409` no requiere haber leído la fila ajena.

### 5. Los `409` ya tienen mensaje propio en `CONSTRAINTS`

No se modifica `app/core/errors.py`:

- `uq_usuario_email` → `409 "Ya existe un usuario con ese email"`.
- `uq_cliente_email` → `409 "Ya existe un cliente con ese email"`.

Son mensajes distintos, en español y sin nombres de tabla, que es lo que exige `RN-15`. Un constraint inesperado cae en el `409` genérico del traductor. `uq_cliente_usuario_id` no es alcanzable en este flujo porque la ficha se crea nueva.

### 6. Router sin lógica de negocio y sin tocar `main.py`

Se agrega al `router` existente de `/auth`:

```python
@router.post("/registro", response_model=UsuarioRead, status_code=201)
async def registro(
    data: UsuarioCreate,
    request: Request,
    uow: RegistroUnitOfWork = Depends(get_registro_uow),
) -> UsuarioRead:
    usuario = await service.registrar(
        uow,
        data,
        settings=request.app.state.settings,
        semaphore=request.app.state.bcrypt_sem,
    )
    return UsuarioRead.model_validate(usuario)
```

El router sólo construye el UoW (por dependencia), pasa configuración del `lifespan` y proyecta la respuesta. No decide unicidad, no hashea, no abre transacciones ni emite cookie. `main.py` ya incluye este router en el grupo abierto (RN-06: registro es ruta pública), así que **no cambia**.

### 7. Estrategia de pruebas

**Sin PostgreSQL (rápidas, sin conexión):**

- `tests/test_registro_schemas.py`: `UsuarioCreate` valida `extra="forbid"` (incluido `rol`), 72 bytes aceptados / 73 rechazados, multibyte («ñ» = 2 bytes), NUL rechazado y normalización de `email`. `UsuarioRead` no declara `password_hash`.
- `tests/test_registro_service.py`: UoW falso (registra `__aenter__`, `__aexit__`, entradas y órdenes) + `hash_password` monkeypatcheado a un doble que registra su ejecución. Se verifica: hash antes de abrir el UoW, un solo `async with`, tres `add()` en orden sobre la misma sesión lógica, `usuario_id` propagado a `asignacion_rol` y `cliente`, reintegro del `usuario`, y que un `IntegrityError` en la tercera escritura produce `409` con el mensaje traducido (nunca `commit` en los repositorios).
- Estas pruebas no reemplazan a CV-12; sólo aíslan la lógica y el orden.

**Con PostgreSQL real (obligatorias, nunca SQLite):**

- API con `httpx.AsyncClient` + `ASGITransport` sobre `main.app` y su `lifespan` (patrón de `conftest.py`): 201 + tres filas + respuesta sin `password_hash`; 422 con `rol`; 422 con 73 bytes; 409 de usuario; 409 de cliente con la ficha intacta (`usuario_id` sigue nulo).
- Atomicidad: se crea previamente un `Cliente` con el email a registrar (sin `usuario_id`); el `POST` da `409` en la tercera escritura; se verifica que `count(usuario)` y `count(asignacion_rol)` no crecieron y que la ficha conserva `usuario_id` nulo (`docs/CHECKLIST_ENTREGA.md` §7).
- Limpieza con las fixtures existentes (`usuario_factory`, `cliente_factory`) o fixtures nuevas que borren por email único al terminar.

**Manual con base (evidencia de aceptación):**

- `parcial/test/registro.http` con el caso `C-02` completo: 201, 409 de usuario, 409 de cliente y los `422` de `rol` y de 73 bytes, con los `SELECT count(*)` esperados en comentarios.
- Verificación del orden hash → transacción por inspección (`grep`) y por la prueba de dobles.

## Risks / Trade-offs

- [El `409` de cliente depende del orden de las escrituras: si la ficha se escribiera antes que el usuario, no habría `usuario_id` que asignar] → El orden está fijado en el diseño y cubierto por una prueba de servicio; la ficha siempre va última.
- [Atrapar `IntegrityError` dentro del bloque confirmaría filas parciales] → El `except` vive fuera del `async with`; hay una prueba de servicio que verifica que el UoW recibe la excepción (y por lo tanto revierte) antes de traducir.
- [Un `IntegrityError` deja la sesión en estado inválido hasta el rollback] → No se ejecuta ninguna consulta después del error; el `rollback()` del `__aexit__` es la única operación posterior.
- [Normalizar el email a minúsculas cambia el valor guardado respecto de lo enviado] → Es coherente con `LoginRequest` (`C-11`) y con la búsqueda `lower(email)` del repositorio; se documenta como convención y no se aplica a otras tablas fuera de este flujo.
- [La respuesta `201` no emite cookie, así que el cliente debe iniciar sesión después] → Es el comportamiento pedido; automatizar el login queda fuera de C-12.
- [La unicidad de `cliente.email` es sensible a mayúsculas en la base] → La normalización del nuevo alta evita duplicados nuevos; las fichas heredadas con otra capitalización no se tocan en este change.

## Migration Plan

Sin migraciones de base ni cambios de configuración: las tablas, constraints, `Settings`, semáforo y `lifespan` ya existen. El despliegue consiste en agregar el schema, el repositorio, el UoW, el servicio y la ruta, y reiniciar la aplicación. Rollback: retirar la ruta `/auth/registro` y las piezas nuevas; los datos ya registrados quedan válidos (usuario + rol + ficha) porque se escribieron en una transacción confirmada.

## Open Questions

Ninguna que cambie el contrato, el enfoque o el desglose de tareas. La forma exacta de la respuesta `201` (`UsuarioRead`) y la normalización del email quedan resueltas arriba como decisiones de implementación; no agregan reglas de negocio.

## UI Mockups

- Design system mode: `off` (`pending_inputs.visual_design.mode` en `.active-orchestrator-state.json`).
- Decision: no (no UI)
- Fecha: 2026-11-06
- Motivo: API pura (sin interfaz); el change agrega un endpoint JSON y no produce pantallas, componentes ni estilos.
