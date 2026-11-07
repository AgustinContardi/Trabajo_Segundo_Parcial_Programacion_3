# Spec Delta — auto-registro-clientes

## Purpose

Define el alta atómica de la identidad de un cliente en el auto-registro público: usuario, rol `CLIENTE` y ficha de cliente como una sola operación, con contrato de entrada cerrado y rechazo de correos duplicados sin apropiarse de fichas existentes.

## ADDED Requirements

### Requirement: El contrato de entrada del auto-registro está cerrado a tres campos

`POST /auth/registro` SHALL aceptar sólo `email`, `nombre` y `password`. SHALL responder `422` ante cualquier campo adicional, incluido `rol`, y ante una contraseña de más de 72 bytes codificados en UTF-8, sin ejecutar bcrypt en este último caso (`RN-02`, `RN-15`).

#### Scenario: Campo `rol` en el cuerpo

- **WHEN** el cuerpo de `POST /auth/registro` incluye `rol` junto con `email`, `nombre` y `password`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Otro campo no declarado

- **WHEN** el cuerpo incluye un campo distinto de `email`, `nombre` y `password`
- **THEN** la respuesta es `422` y no se escribe ninguna fila

#### Scenario: Contraseña de más de 72 bytes

- **WHEN** la contraseña enviada ocupa más de 72 bytes en UTF-8, por ejemplo 40 caracteres «ñ»
- **THEN** la respuesta es `422` antes de ejecutar bcrypt y no se escribe ninguna fila

#### Scenario: Contraseña exactamente en el límite

- **WHEN** la contraseña ocupa exactamente 72 bytes en UTF-8 y el resto del cuerpo es válido
- **THEN** el registro se procesa como un alta válida

### Requirement: Un registro válido crea las tres filas en una sola operación

Un registro válido SHALL responder `201` y SHALL persistir, en la misma transacción, una fila en `usuario`, una en `asignacion_rol` con `rol = 'CLIENTE'`, `desde` con la hora del alta y `vence_en` y `revocada_en` nulos, y una en `cliente` cuyo `usuario_id` referencia el usuario recién creado (`RN-02`).

#### Scenario: Alta válida

- **WHEN** un visitante envía `email`, `nombre` y `password` válidos y el correo no está registrado
- **THEN** la respuesta es `201` y existen exactamente una fila nueva en `usuario`, una en `asignacion_rol` y una en `cliente` para ese correo

#### Scenario: Rol CLIENTE vigente y sin revocar

- **WHEN** el alta termina en `201`
- **THEN** la asignación creada tiene `rol = 'CLIENTE'`, `desde` no nulo, `vence_en` nulo y `revocada_en` nulo

#### Scenario: La ficha queda ligada al usuario nuevo

- **WHEN** el alta termina en `201`
- **THEN** la fila de `cliente` tiene `usuario_id` igual al `id` del usuario recién creado y conserva el `email` y el `nombre` enviados

#### Scenario: La respuesta no expone credenciales

- **WHEN** el alta termina en `201`
- **THEN** el cuerpo de la respuesta no contiene `password_hash` ni la contraseña en claro

### Requirement: Un fallo en cualquier escritura revierte las tres

El auto-registro SHALL ser atómico: si falla la escritura de la ficha de cliente o la de la asignación de rol, el sistema SHALL revertir la operación completa y no SHALL dejar filas en `usuario`, `asignacion_rol` ni `cliente` (`RN-02`).

#### Scenario: Falla la ficha de cliente

- **WHEN** la escritura de `cliente` falla después de haber escrito `usuario` y `asignacion_rol`
- **THEN** la respuesta es `409` o `422` según el error y `SELECT count(*) FROM usuario` no crece, ni tampoco `asignacion_rol` ni `cliente`

#### Scenario: Falla la asignación de rol

- **WHEN** la escritura de `asignacion_rol` falla después de haber escrito `usuario`
- **THEN** la operación se revierte y no queda el usuario ni la ficha de cliente

### Requirement: Un correo ya registrado produce 409 sin filas sueltas

Si el correo ya existe como `usuario`, el sistema SHALL responder `409` con un mensaje propio de usuario; si ya existe como `cliente`, SHALL responder `409` con un mensaje propio de cliente y SHALL dejar la ficha existente intacta, sin escribirle `usuario_id`. En ninguno de los dos casos SHALL quedar filas nuevas (`RN-01`, `RN-02`).

#### Scenario: Correo ya usado por un usuario

- **WHEN** el cuerpo es válido pero el correo ya pertenece a una fila de `usuario`
- **THEN** la respuesta es `409` con el mensaje propio de usuario y no se agregan filas en `usuario`, `asignacion_rol` ni `cliente`

#### Scenario: Correo ya usado por un cliente

- **WHEN** el cuerpo es válido pero el correo ya pertenece a una fila de `cliente`
- **THEN** la respuesta es `409` con el mensaje propio de cliente y no se agregan filas en `usuario`, `asignacion_rol` ni `cliente`

#### Scenario: La ficha existente no se apropia

- **WHEN** el correo ya existe como `cliente` sin `usuario_id` y el registro responde `409`
- **THEN** esa ficha conserva `usuario_id` nulo, su `nombre` y su `email` originales

### Requirement: El hash se calcula fuera de la transacción y del event loop

El sistema SHALL calcular el hash bcrypt de la contraseña antes de abrir el Unit of Work, fuera del event loop y respetando el límite de concurrencia configurado, de modo que no se retenga una conexión de base durante el cálculo (`docs/CHECKLIST_ENTREGA.md` §5).

#### Scenario: Orden del cálculo

- **WHEN** se procesa un registro válido
- **THEN** el hash se calcula antes de abrir la transacción y las tres escrituras ocurren después, dentro de un único `async with`

#### Scenario: Concurrencia acotada

- **WHEN** llegan registros concurrentes que requieren hash bcrypt
- **THEN** ninguna operación bcrypt corre en el event loop y la cantidad simultánea no supera `BCRYPT_MAX_CONCURRENCY`

### Requirement: Los errores del auto-registro no exponen detalles internos

Todo error del auto-registro SHALL devolver un mensaje propio en español y SHALL omitir nombres de tablas, columnas, constraints y trazas de PostgreSQL; ninguna entrada inválida SHALL terminar en `500` (`RN-15`).

#### Scenario: Violación de unicidad

- **WHEN** el registro choca con un correo existente
- **THEN** el cuerpo del `409` contiene el mensaje propio del proyecto y ningún texto interno de la base

#### Scenario: Texto con carácter nulo

- **WHEN** `email`, `nombre` o `password` contienen un carácter NUL
- **THEN** la respuesta es `422`, no `500`

#### Scenario: JSON malformado

- **WHEN** el cuerpo de la petición no es JSON válido
- **THEN** la respuesta es `422`, no `500`
