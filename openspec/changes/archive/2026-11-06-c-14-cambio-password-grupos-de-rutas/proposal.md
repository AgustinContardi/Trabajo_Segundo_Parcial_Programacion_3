# Proposal — C-14 cambio-password-grupos-de-rutas

## Why

La autenticación ya está completa (C-11) y la autorización por rol vigente en la base también (C-13), pero falta el control de cambio obligatorio de contraseña: cuando `usuario.debe_cambiar_password = true`, el usuario solo puede usar las rutas de `/auth` y las públicas; cualquier ruta del grupo protegido debe devolver `403`. Además, no existe `POST /auth/cambiar-password`, la ruta de salida del estado pendiente, ni el módulo `usuarios` tiene `EventoSeguridadRepository`, que `C-15` necesita para auditar alta de personal y cambios de rol.

## What Changes

- `main.py` agrupa los routers en **dos grupos**: abierto (`/health`, `/auth`, catálogo público) y protegido (todo lo demás), con el control del cambio obligatorio montado **una sola vez** a nivel del router protegido.
- `GET /auth/yo` y `POST /auth/cambiar-password` viven en el grupo abierto pero **exigen sesión** (`RN-06`).
- `POST /auth/cambiar-password`: body con contraseña actual + nueva (≤ 72 bytes cada una → 422); **401** si la actual no coincide (no escribe `intento_acceso`, no es un login); hash nuevo **fuera** de la transacción; en un solo UoW: `password_hash`, `debe_cambiar_password = false` y la línea de `evento_seguridad` con `actor = email` (`RN-16`).
- **No** emite token nuevo y **no** rota la cookie: la misma cookie sigue entrando al grupo protegido con `200` (`IN-03`, `DD-07`). El bloqueo se libera porque `debe_cambiar_password` vive en la base y se relee en cada petición.
- El módulo `usuarios` suma `EventoSeguridadRepository` con `add()` y listado paginado, para que `C-15` lo reutilice.
- Con `debe_cambiar_password = true`: toda ruta del grupo protegido → **403**; las de `/auth` y las públicas siguen funcionando.

## Capabilities

### New Capabilities

- `cambio-password`: contrato de `POST /auth/cambiar-password` (200, 401 contraseña actual incorrecta, 422 más de 72 bytes, no rota cookie ni emite token, línea de `evento_seguridad` en la misma transacción, hash calculado fuera del UoW).
- `grupos-de-rutas`: dos grupos de rutas en `main.py`, control de cambio obligatorio montado una vez en el router protegido, grupo protegido devuelve `403` cuando `debe_cambiar_password = true`, rutas abiertas siguen funcionando, y `EventoSeguridadRepository` con `add()` y listado paginado.

### Modified Capabilities

- Ninguna: este change no altera requisitos de capacidades existentes (`cookie-authentication`, `role-authorization`, `api-contracts`); solo agrega la nueva ruta y el agrupamiento.

## Impact

- Código: `parcial/main.py` (agrupamiento de routers + control montado una vez), `parcial/app/core/dependencies.py` (dependencia compartida que lee `debe_cambiar_password` con la misma sesión del UoW), `parcial/app/modules/usuarios/{router,service,repository,schemas,unit_of_work}.py` (nuevo endpoint, servicio atómico, `EventoSeguridadRepository`, schemas de entrada/salida).
- API: nueva ruta `POST /auth/cambiar-password` en el grupo abierto con sesión obligatoria; `GET /auth/yo` se mantiene en el grupo abierto (ya existe desde C-13).
- Datos: usa `usuario` (`password_hash`, `debe_cambiar_password`) y `evento_seguridad` (ya existen; sin migración nueva).
- Pruebas: `.http` de C-09 en `parcial/test/` e integración contra PostgreSQL 17 real (misma cookie → 200 tras el cambio; cookie no rota).
- Fuera de alcance: `POST /auth/registro` (C-12), alta de personal y administración de roles (C-15), `POST /ventas` transaccional (C-16), migraciones de esquema, rotación de cookie o nuevo token.
