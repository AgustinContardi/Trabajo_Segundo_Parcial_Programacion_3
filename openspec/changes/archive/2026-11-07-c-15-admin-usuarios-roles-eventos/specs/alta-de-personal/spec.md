# Spec Delta — alta-de-personal

## Purpose

Alta de personal administrativo y de ventas con contraseña provisoria, rol inicial y auditoría de seguridad escritos en una única transacción, sin exponer nunca el hash ni la contraseña.

## ADDED Requirements

### Requirement: Alta de personal con contraseña provisoria

El sistema SHALL exponer `POST /usuarios` para que un administrador dé de alta personal. El cuerpo SHALL aceptar exclusivamente `email`, `nombre`, `password` y `rol`; cualquier campo adicional MUST responder `422`. El `email` SHALL normalizarse (sin espacios extremos y en minúsculas) antes de validarse y guardarse. `rol` SHALL aceptar solo `ADMIN` o `VENDEDOR`. El usuario creado SHALL quedar `activo = true` y con `debe_cambiar_password = true`. La respuesta SHALL ser `201` con `id`, `email`, `nombre`, `activo` y `debe_cambiar_password`, y MUST NOT incluir `password_hash`, `password` ni token.

#### Scenario: Alta de un administrador

- **WHEN** un administrador autenticado envía `POST /usuarios` con `email`, `nombre`, `password` y `rol = "ADMIN"`
- **THEN** la respuesta es `201` con los datos del usuario creado, `activo = true` y `debe_cambiar_password = true`

#### Scenario: Alta de un vendedor

- **WHEN** un administrador autenticado envía `POST /usuarios` con `rol = "VENDEDOR"`
- **THEN** la respuesta es `201` y el usuario creado queda identificado como personal de ventas

#### Scenario: Email normalizado

- **WHEN** se envía `email = "  Ana.Paz@Example.COM "`
- **THEN** el usuario se guarda y se devuelve con `email = "ana.paz@example.com"`

#### Scenario: Email ya registrado

- **WHEN** se envía un `email` que, ya normalizado, coincide con el de un usuario existente (incluido el caso en que solo difiere en mayúsculas o espacios)
- **THEN** la respuesta es `409`

#### Scenario: Rol inicial no permitido

- **WHEN** se envía `rol = "CLIENTE"`, un rol inexistente o se omite `rol`
- **THEN** la respuesta es `422` y no se crea ningún usuario

#### Scenario: Campos de más o contraseña demasiado larga

- **WHEN** el cuerpo incluye un campo no declarado o un `password` de más de 72 bytes
- **THEN** la respuesta es `422` y no se crea ningún usuario

#### Scenario: La respuesta no filtra secretos

- **WHEN** se inspecciona la respuesta de un alta exitosa
- **THEN** no aparecen `password`, `password_hash` ni ningún token

### Requirement: Alta atómica con auditoría en la misma transacción

El alta de personal SHALL escribir el usuario, su asignación de rol inicial y la línea de `evento_seguridad` dentro de una única transacción. El hash bcrypt SHALL calcularse antes de abrir esa transacción. La línea de auditoría SHALL llevar `actor` igual al `email` del administrador que ejecuta el alta y una `accion` que identifique la operación y el rol otorgado.

#### Scenario: Las tres escrituras son una sola operación

- **WHEN** un alta de personal termina con `201`
- **THEN** existen el usuario, exactamente una asignación de rol inicial abierta y exactamente una línea de `evento_seguridad` de alta de personal

#### Scenario: Un fallo no deja rastro parcial

- **WHEN** se fuerza un error después de crear el usuario y antes de confirmar la transacción
- **THEN** no queda el usuario, ni la asignación de rol, ni la línea de `evento_seguridad`

#### Scenario: La auditoría identifica al administrador

- **WHEN** el administrador `admin@example.com` da de alta a un vendedor
- **THEN** la línea de `evento_seguridad` resultante tiene `actor = "admin@example.com"` y menciona el alta y el rol otorgado

### Requirement: Control de acceso del alta de personal

`POST /usuarios` SHALL exigir sesión válida y rol `ADMIN` vigente, y SHALL estar dentro del grupo de rutas protegido.

#### Scenario: Sin sesión

- **WHEN** se envía `POST /usuarios` sin cookie válida
- **THEN** la respuesta es `401` y no se crea ningún usuario

#### Scenario: Autenticado sin rol ADMIN

- **WHEN** un usuario con rol vigente `VENDEDOR` o `CLIENTE` envía `POST /usuarios`
- **THEN** la respuesta es `403` y no se crea ningún usuario

#### Scenario: Administrador con cambio de contraseña pendiente

- **WHEN** un usuario con rol `ADMIN` y `debe_cambiar_password = true` envía `POST /usuarios`
- **THEN** la respuesta es `403` y no se crea ningún usuario
