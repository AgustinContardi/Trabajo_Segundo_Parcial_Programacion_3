# cookie-authentication Specification

## Purpose

Define cómo una persona inicia y cierra una sesión mediante credenciales y una cookie HttpOnly, y cómo la API autentica su identidad en cada petición. Esta capability no decide permisos por rol ni propiedad de recursos.

## Requirements

### Requirement: El contrato de credenciales de login valida la entrada

`POST /auth/login` SHALL aceptar email y contraseña, rechazar campos no declarados y responder `422` si la contraseña supera 72 bytes antes de ejecutar bcrypt.

#### Scenario: Campo no declarado

- **WHEN** el cuerpo de login incluye un campo distinto de email o contraseña
- **THEN** la respuesta es `422` y no se ejecuta la verificación de contraseña

#### Scenario: Contraseña mayor a 72 bytes

- **WHEN** el cuerpo de login contiene una contraseña de más de 72 bytes
- **THEN** la respuesta es `422` antes de ejecutar bcrypt

### Requirement: Login válido emite una cookie de acceso y no expone el token

El sistema SHALL validar las credenciales y emitir un JWT con `sub`, `exp` y los roles vigentes al momento de emitirlo. SHALL transportar el token sólo en `Set-Cookie: access_token` con `HttpOnly`, `SameSite=Lax`, `Max-Age` igual al TTL y `Secure` configurable; el cuerpo de respuesta SHALL omitir el token.

#### Scenario: Login correcto

- **WHEN** una cuenta activa envía credenciales válidas a `POST /auth/login`
- **THEN** la respuesta es `200`, incluye `debe_cambiar_password` y `expira_en_segundos`, y establece la cookie con los atributos requeridos

#### Scenario: Token no se entrega en el cuerpo

- **WHEN** el login termina correctamente
- **THEN** ni el JWT ni otro token de acceso aparecen en el cuerpo de respuesta

#### Scenario: Roles del token son informativos

- **WHEN** se emite el JWT de una cuenta con roles vigentes
- **THEN** el claim `roles` refleja esos roles al emitirlo y no constituye una decisión de autorización para peticiones posteriores

### Requirement: Login rechaza credenciales no válidas sin revelar existencia de cuenta

El sistema SHALL responder `401` con el mismo cuerpo para contraseña incorrecta, email inexistente y usuario inactivo, y SHALL realizar verificación de contraseña de costo comparable exista o no la cuenta.

#### Scenario: Contraseña incorrecta

- **WHEN** existe una cuenta activa para el email pero la contraseña no coincide
- **THEN** la respuesta es `401` con el mensaje genérico de credenciales inválidas

#### Scenario: Email inexistente

- **WHEN** no existe una cuenta para el email enviado
- **THEN** se verifica la contraseña contra el hash ficticio ya preparado y la respuesta `401` tiene el mismo cuerpo que una contraseña incorrecta

#### Scenario: Usuario inactivo

- **WHEN** las credenciales corresponden a un usuario con `activo = false`
- **THEN** la respuesta es `401` con el mismo cuerpo genérico y no se emite cookie de acceso

### Requirement: Operaciones bcrypt no bloquean el event loop

Toda operación bcrypt iniciada por autenticación SHALL ejecutarse fuera del event loop y SHALL respetar el límite de concurrencia configurado.

#### Scenario: Verificación concurrente

- **WHEN** llegan verificaciones bcrypt concurrentes a `POST /auth/login`
- **THEN** ninguna se ejecuta en el event loop y la cantidad simultánea no supera `BCRYPT_MAX_CONCURRENCY`

### Requirement: Login limita intentos fallidos antes de verificar la contraseña

El sistema SHALL contar fallos del mismo email e IP en la ventana de `LOGIN_VENTANA_SEG` posterior al último login exitoso de ese par. Tras cinco fallos en la ventana, SHALL responder `429` al siguiente intento con `Retry-After` cuyo valor sea un entero decimal que expresa milisegundos, según `docs/CHECKLIST_ENTREGA.md` §5, sin verificar ni calcular un hash. Por ejemplo, `Retry-After: 250` expresa 250 milisegundos.

#### Scenario: Quinto fallo

- **WHEN** se recibe el quinto intento fallido dentro de la ventana vigente
- **THEN** se procesa la credencial y se registra el fallo sin responder `429`

#### Scenario: Intento siguiente al umbral

- **WHEN** ya existen cinco fallos contabilizables para el mismo email e IP
- **THEN** la respuesta es `429` con `Retry-After` expresado como entero decimal en milisegundos y no se ejecuta ninguna operación bcrypt

#### Scenario: Login exitoso reinicia el conteo

- **WHEN** un login exitoso ocurre después de intentos fallidos del mismo email e IP
- **THEN** esos fallos se conservan en `intento_acceso` pero no cuentan para intentos posteriores

### Requirement: Cada intento de login queda registrado en una transacción propia

El sistema SHALL registrar cada intento recibido, incluso si responde `401` o `429`, en `intento_acceso` con email, IP y resultado. El registro SHALL confirmarse en una sesión y transacción independientes de la transacción de lectura/login.

#### Scenario: Intento con credenciales inválidas

- **WHEN** un login termina en `401`
- **THEN** queda una fila de `intento_acceso` con `exito = false`, confirmada aunque la petición falle

#### Scenario: Intento limitado

- **WHEN** un login es rechazado por el límite de intentos
- **THEN** el intento también queda registrado en su transacción propia

#### Scenario: Login exitoso

- **WHEN** un login termina correctamente
- **THEN** queda una fila con `exito = true` y los fallos anteriores permanecen almacenados

### Requirement: Logout expira la cookie de acceso

El sistema SHALL permitir cerrar sesión mediante `POST /auth/logout`, responder `200` y expirar `access_token` mediante una cookie con `Max-Age=0`.

#### Scenario: Cierre de sesión

- **WHEN** se envía `POST /auth/logout`
- **THEN** la respuesta es `200` y el navegador recibe una instrucción para eliminar `access_token`

### Requirement: La identidad actual se obtiene exclusivamente de la cookie

En las rutas que requieran identidad, el sistema SHALL leer `access_token` sólo de `request.cookies`, validar firma y `exp`, y resolver en la base de datos un usuario existente y activo. SHALL responder `401` si falta la cookie, el token es inválido o venció, o el usuario no existe o está inactivo. Este requisito no concede ni deniega roles.

#### Scenario: Cookie válida

- **WHEN** una petición autenticada incluye una cookie válida cuyo sujeto corresponde a un usuario activo
- **THEN** se resuelve la identidad de ese usuario

#### Scenario: Sin cookie

- **WHEN** una ruta que requiere identidad recibe una petición sin `access_token`
- **THEN** la respuesta es `401`

#### Scenario: Token inválido o vencido

- **WHEN** una ruta que requiere identidad recibe una cookie con JWT inválido o vencido
- **THEN** la respuesta es `401` sin exponer detalles criptográficos

#### Scenario: Authorization no es una fuente de identidad

- **WHEN** una petición no incluye cookie pero incluye `Authorization: Bearer <token>`
- **THEN** la respuesta es `401` y el header no autentica la petición

#### Scenario: Usuario inexistente o inactivo

- **WHEN** un JWT válido identifica un usuario inexistente o inactivo
- **THEN** la respuesta es `401`
