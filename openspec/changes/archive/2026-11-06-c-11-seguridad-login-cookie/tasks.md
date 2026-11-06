# Tasks — C-11 seguridad-login-cookie

## 1. Configuración y primitives de seguridad

- [x] 1.1 Agregar `COOKIE_SECURE` a `Settings` y a `parcial/env.example` sin secretos; verificar con pruebas de configuración que puede activarse en producción y desactivarse explícitamente en desarrollo local, y que importar `main` no exige ni revela secretos.
- [x] 1.2 Crear helpers de hash/verificación bcrypt en `parcial/app/core/security.py`, aplicando validación de 72 bytes, `asyncio.to_thread` y el semáforo compartido del lifespan; verificar con pruebas que el límite de concurrencia se respeta y que bcrypt no corre en el event loop.
- [x] 1.3 Añadir helpers de emisión/validación JWT y armado/expiración de cookie en `security.py`; verificar `sub`, `exp`, roles informativos, TTL, `HttpOnly`, `SameSite=Lax`, `Max-Age`, `Secure` configurable y ausencia de token en cuerpos.

## 2. Persistencia de login e intentos

- [x] 2.1 Crear las piezas de repositorio/UoW de `usuarios` necesarias para buscar usuario por email/id, cargar roles vigentes al emitir token y contar fallos por email/IP, posteriores al último éxito y dentro de la ventana; verificar consultas y filtros con PostgreSQL real.
- [x] 2.2 Implementar el registro de `IntentoAcceso` con una sesión/transacción propia y el comentario de tres puntos requerido por DD-05; verificar en PostgreSQL que los registros sobreviven a un rollback/error de login y que también se guardan los intentos 429.

## 3. Login y logout

- [x] 3.1 Crear schemas y servicio de autenticación bajo `parcial/app/modules/usuarios/`, usando el patrón router construye UoW / servicio abre UoW; verificar `extra="forbid"`, 422 para contraseña mayor a 72 bytes y que la validación ocurre antes de bcrypt.
- [x] 3.2 Implementar `POST /auth/login` con orden límite → usuario/hash real o ficticio → verificación → intento propio → respuesta/cookie; verificar contra PostgreSQL 200, 401 de cuerpo idéntico para contraseña errónea/email inexistente/usuario inactivo, y que el sexto intento responde 429 antes de bcrypt con `Retry-After` como entero decimal interpretado directamente en milisegundos, conforme al checklist.
- [x] 3.3 Implementar `POST /auth/logout` con expiración de `access_token`; verificar respuesta 200 y `Set-Cookie` con `Max-Age=0`.
- [x] 3.4 Crear `parcial/test/auth.http` con los casos de aceptación de login/logout y dos sesiones cuando corresponda; verificar que el archivo documenta códigos y cuerpos esperados para C-03, C-04 y C-05 sin incluir tokens en el JSON.

## 4. Identidad actual desde cookie

- [x] 4.1 Crear `parcial/app/core/dependencies.py` con `get_usuario_actual`, leyendo exclusivamente `request.cookies`, validando firma/expiración y consultando usuario existente/activo con la sesión de la petición; verificar 401 ante ausencia, JWT inválido/vencido, usuario inexistente/inactivo y `Authorization` sin cookie.
- [x] 4.2 Añadir pruebas de integración con PostgreSQL que monten una ruta protegida de prueba usando `get_usuario_actual`; verificar que la cookie válida resuelve identidad y que la dependencia no consulta roles ni convierte autenticación en autorización.

## 5. Integración y aceptación de C-11

- [x] 5.1 Montar el router `/auth` de C-11 en `parcial/main.py` sin cambiar el agrupamiento de rutas de C-14; verificar `python -c "import main"` con `PYTHONPATH=parcial` y que importar no abre conexiones.
- [x] 5.2 Ejecutar pruebas de autenticación contra PostgreSQL real y los casos `.http` C-03/C-04/C-05; verificar status + body, cookies, persistencia de intentos, reinicio de conteo tras login correcto, ausencia de secretos/tokens en logs y resultados.
- [x] 5.3 Ejecutar `alembic check` y revisar los cambios para confirmar que no se agregaron migraciones, `requiere_rol`, `/auth/yo` ni cambios de autorización al router de clientes; dejar expresamente el 403 pendiente de C-07 para C-13.

## Workflow follow-up

- Una vez implementada y aceptada C-11, archivar el change y actualizar `CHANGES.md` según el flujo del proyecto; C-07 sólo podrá marcarse completo cuando C-13 complete y verifique su 403.
