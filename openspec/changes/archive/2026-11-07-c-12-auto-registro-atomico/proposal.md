# Proposal — C-12 auto-registro-atomico

## Why

La API ya permite iniciar y cerrar sesión (C-11) y consultar la identidad con roles (C-13), pero no existe forma de que un visitante cree su propia cuenta. Sin `POST /auth/registro`, el circuito de acceso queda incompleto: no hay usuario, ni rol `CLIENTE`, ni ficha de cliente que ligar a las ventas. `RN-02` es además la operación que justifica el capítulo 6 del parcial: tres escrituras que sólo tienen sentido juntas y un `409` que no debe tocar la ficha ajena.

## What Changes

- Agregar `POST /auth/registro` en el grupo abierto de `/auth` → **201** con `email`, `nombre` y `password`; el campo `rol` no existe y mandarlo da **422** (`extra="forbid"`).
- Calcular el hash bcrypt **antes** de abrir el Unit of Work, con `asyncio.to_thread` y el semáforo compartido del `lifespan`; contraseña de más de **72 bytes** → **422** sin llegar a bcrypt.
- Escribir `usuario`, `asignacion_rol` con `rol='CLIENTE'` (`desde=now()`, `vence_en` y `revocada_en` nulos) y `cliente` con `usuario_id` del usuario nuevo dentro de **un solo** `async with uow`; las tres filas o ninguna.
- Responder **409** con mensaje propio cuando el correo ya existe como usuario y **409** con otro mensaje cuando ya existe como cliente, sin apropiarse de la ficha existente (nunca se le escribe `usuario_id`) y sin dejar filas sueltas en ninguno de los dos casos.
- No exponer `password_hash` en la respuesta ni texto interno de la base en los errores (`RN-15`).
- Cubrir el caso `C-02` de `docs/CHECKLIST_ENTREGA.md` §10 y el invariante de §7 con pruebas y un archivo `.http` de evidencia.

## Capabilities

### New Capabilities

- `auto-registro-clientes`: alta atómica de la identidad de un cliente (usuario + rol `CLIENTE` + ficha de cliente), con validación del contrato de entrada, rechazo de correos duplicados y respuesta sin credenciales.

### Modified Capabilities

Ninguna. `cookie-authentication` sigue cubriendo sólo inicio/cierre de sesión e identidad por petición; C-12 no cambia sus requisitos. `clientes-y-perfil` cubre el CRUD de personal y no se modifica.

## Impact

- Código nuevo/ampliado en `parcial/app/modules/usuarios/`: schemas, repositorio de `asignacion_rol`, Unit of Work de registro, servicio y router.
- Reutiliza `parcial/app/core/security.py` (`hash_password`), `parcial/app/core/errors.py` (`traducir_integrity_error`, `CONSTRAINTS` ya mapea `uq_usuario_email` y `uq_cliente_email` a 409 con mensajes distintos) y `ClienteRepository` de `parcial/app/modules/clientes/`.
- No requiere migraciones: `usuario`, `asignacion_rol` y `cliente` ya existen en el esquema; `cliente.email` y `cliente.usuario_id` tienen sus `UNIQUE`.
- Pruebas nuevas en `parcial/tests/` y evidencia manual en `parcial/test/registro.http`.
- Habilita C-15 (alta de personal) y C-18 (casos `.http`); no toca autorización ni C-13.
