# Design — C-11 seguridad-login-cookie

## Context

Ver `proposal.md` para la motivación y `specs/cookie-authentication/spec.md` para el contrato observable. En `parcial/`, `main.py` ya crea en el `lifespan` el `sessionmaker`, el semáforo y `hash_ficticio`; `Settings` aún no declara `COOKIE_SECURE`. Existen los modelos `Usuario`, `AsignacionRol` e `IntentoAcceso`, pero no hay router/servicio/repositorio/UoW de usuarios ni `security.py` o `dependencies.py`. C-02/C-03/C-05 están archivados y disponibles; C-07 está archivado incompleto y espera C-13 para su autorización.

## Goals / Non-Goals

**Goals:**
- Reusar los recursos del lifespan y los modelos existentes, completando autenticación sin cambiar el esquema.
- Dejar un `get_usuario_actual` estable para que C-13 pueda añadir autorización sin volver a implementar validación de identidad.
- Mantener registros de intentos independientes del resultado de autenticación y no bloquear el event loop con bcrypt.

**Non-Goals:**
- No implementar `requiere_rol`, `/auth/yo`, el control de cambio obligatorio ni autorización por propiedad.
- No cerrar el 403 faltante de `GET /clientes/{id}/ventas` en C-07. C-13 consumirá `get_usuario_actual` y atenderá esa integración.
- No implementar registro, cambio de contraseña, gestión de roles, migraciones ni rotación/revocación de JWT antes de su expiración.

## Decisions

1. **Extender el núcleo actual, no crear un segundo ciclo de recursos.** `security.py` tendrá helpers de contraseña/JWT/cookie; `dependencies.py` resolverá identidad usando `Depends(get_session)`. Se agrega `COOKIE_SECURE` a `Settings`; se reutilizan `app.state.bcrypt_sem`, `hash_ficticio`, `settings` y `sessionmaker` que el `lifespan` ya inicializa. Alternativa descartada: crear un semáforo/hash por router o petición, que duplica estado y rompe el costo uniforme.

2. **Separar la lectura de login de la auditoría del intento.** El conteo y la búsqueda de usuario usan el UoW/sesión de la petición; cada fila `IntentoAcceso` se inserta y confirma con una sesión nueva de `app.state.sessionmaker`. Un conteo PostgreSQL de una sola ida incluye los fallos del par email/IP posteriores al último éxito y dentro de la ventana. Para IP se usa `request.client.host`; no se confía en `X-Forwarded-For` sin configuración explícita de proxy confiable. Alternativa descartada: guardar el intento en el UoW de login, porque un rollback del 401 borraría la evidencia que alimenta RN-07.

3. **Aplicar el límite antes de cualquier bcrypt.** Tras contar cinco fallos, registrar el intento bloqueado en su transacción propia y devolver 429 antes de buscar/verificar contraseña. `Retry-After` SHALL llevar un entero decimal interpretado directamente como milisegundos, conforme a `docs/CHECKLIST_ENTREGA.md` §5 (por ejemplo, `250` significa 250 ms). El contrato no añade una conversión a segundos ni una regla de redondeo. En el resto de casos, buscar el usuario, usar su hash o el hash ficticio ya calculado en lifespan, y verificar bcrypt con `asyncio.to_thread` bajo el semáforo compartido. Validar el máximo de 72 bytes con la validación existente antes de invocar bcrypt.

4. **JWT de acceso compacto y cookie como único transporte.** Firmar con el `JWT_SECRET` obligatorio, algoritmo fijo acordado en implementación y claims `sub`, `exp` y roles vigentes de la base al emitir. `get_usuario_actual` obtiene el token sólo de `request.cookies`, valida firma/expiración y carga un usuario activo. Los roles en el token son informativos; no se usan en esta dependencia. `COOKIE_SECURE` será configurable; producción se configura `true` y el entorno local de pruebas puede declararlo `false` según SU-06. No se agrega token al JSON ni se acepta `Authorization`.

5. **Mantener el desacoplamiento de autorización.** Los routers que requieran identidad dependerán de `get_usuario_actual`; la dependencia no consulta `asignacion_rol` ni emite 403. C-13 podrá componerla con `requiere_rol` y conectar la ruta de C-07, preservando la distinción 401 (identidad) / 403 (permiso o propiedad).

6. **Pruebas de integración con PostgreSQL real.** Verificar códigos y cuerpos, atributos de `Set-Cookie`, ausencia del token en JSON, orden de rate limit vs bcrypt, filas independientes de intento, reinicio tras éxito y 401 ante ausencia/invalidación/vencimiento/inactividad. Para comprobar el 429 sin ejecutar bcrypt, espiar el helper de verificación en la prueba; para persistencia y filtros usar PostgreSQL real, no SQLite.

## Risks / Trade-offs

- [Un rollback o caída durante el login puede dejar una fila de intento aunque no haya respuesta exitosa] → Es el comportamiento deliberado de DD-05; la escritura aislada confirma el intento aunque el flujo de login falle.
- [Los intentos guardan email e IP, datos potencialmente personales, sin una política de retención especificada en C-11] → No registrar esos valores en logs; limitar el almacenamiento a la tabla requerida y dejar retención fuera del alcance salvo que la consigna la fije.
- [El conteo por email/IP puede ser abusado para denegar acceso a una cuenta desde una IP compartida] → Respetar exactamente el umbral/ventana del proyecto y no ampliar el bloqueo a todos los usuarios por IP.
- [El valor numérico de `Retry-After` suele interpretarse como segundos por clientes HTTP estándar, mientras que la aceptación de este parcial exige milisegundos] → Para esta entrega, el contrato de aceptación del proyecto es autoritativo; cualquier adaptación para interoperabilidad externa queda fuera de C-11.
- [La cookie `Secure` evita que el cliente HTTP local la reenvíe por HTTP] → Mantenerla configurable, documentar `false` sólo para desarrollo local y usar `true` en producción.

## Migration Plan

No hay migración de base: las tablas necesarias ya existen. Al implementar, ampliar `env.example` con `COOKIE_SECURE` sin secretos y configurar el valor en los entornos. El rollback consiste en retirar las rutas/dependencias de autenticación y el campo de configuración agregado; no requiere revertir datos ni borrar intentos registrados.

## Open Questions

Ninguna decisión técnica del alcance queda diferida. SU-06 documenta el valor de `Secure` por entorno. La unidad de `Retry-After` queda resuelta como entero decimal en milisegundos para esta entrega, según la aceptación del proyecto; una adaptación a segundos para clientes HTTP estándar no forma parte de C-11.

## UI Mockups

- Decision: no (no UI)
