# Proposal — C-11 seguridad-login-cookie

## Why

El proyecto ya tiene los modelos de acceso y el ciclo de vida prepara un semáforo de bcrypt y un hash ficticio, pero todavía no ofrece login, cookie de sesión ni una dependencia que autentique peticiones. C-11 completa esa base de autenticación para habilitar el posterior C-13; no corrige por sí mismo la autorización pendiente de C-07.

## What Changes

- Añadir la capacidad de autenticación con bcrypt y JWT de vida acotada, transportado exclusivamente en la cookie `access_token` con `HttpOnly`, `SameSite=Lax`, `Max-Age` alineado al TTL y `Secure` configurable.
- Implementar login y logout: limitación de intentos previa a bcrypt, verificación equivalente para emails inexistentes, registro persistente de cada intento en una sesión/transacción propia y respuesta `429` con `Retry-After` como entero decimal de milisegundos conforme a la aceptación del proyecto.
- Proveer `get_usuario_actual` para validar la cookie y resolver identidad activa en cada petición; credenciales ausentes/invalidas, vencidas o asociadas a un usuario inexistente/inactivo producen 401.
- Mantener roles del JWT como información al emitirlo, nunca como decisión de autorización. `requiere_rol`, `/auth/yo`, el cableado del 403 de C-07 y demás autorización quedan para C-13.
- Integrar la configuración y los recursos con el `Settings` y el `lifespan` existentes, sin duplicar el semáforo ni el hash ficticio ya preparados.

## Capabilities

### New Capabilities

- `cookie-authentication`: login/logout con cookie segura, validación de identidad por petición, límite de intentos y protección contra enumeración de cuentas.

### Modified Capabilities

Ninguna. C-11 introduce el contrato de autenticación; consume la configuración, el ciclo de vida y los modelos ya definidos sin cambiar sus requisitos existentes.

## Impact

- Código en `parcial/app/core/security.py`, `parcial/app/core/dependencies.py`, configuración/lifespan existentes, y router/servicio/repositorio/UoW y schemas del módulo `usuarios` según el patrón del proyecto.
- API nueva para `POST /auth/login` y `POST /auth/logout`; dependencia `get_usuario_actual` disponible para las rutas que la consuman después.
- Usa `usuario`, `asignacion_rol` e `intento_acceso` existentes; no requiere migraciones.
- C-13 consumirá `get_usuario_actual` para autorización por roles y puede completar entonces el 403 faltante de `GET /clientes/{id}/ventas` documentado en C-07.
