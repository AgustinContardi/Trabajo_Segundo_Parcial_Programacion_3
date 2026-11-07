# Spec Delta — cambio-password

## Purpose

Define el contrato de `POST /auth/cambiar-password` como la ruta de salida del estado de cambio obligatorio de contraseña, sin emitir token nuevo ni rotar la cookie, y deja una línea de auditoría en `evento_seguridad` en la misma transacción que el cambio de hash.

## ADDED Requirements

### Requirement: Cambio de contraseña exitoso devuelve 200

El sistema SHALL aceptar `POST /auth/cambiar-password` con contraseña actual y nueva (cada una ≤ 72 bytes) de un usuario autenticado con sesión válida, hashear la nueva fuera de la transacción y escribir `password_hash`, `debe_cambiar_password = false` y la línea de `evento_seguridad` en un solo UoW.

#### Scenario: Contraseña actual correcta y nueva válida

- **WHEN** una petición autenticada envía `POST /auth/cambiar-password` con contraseña actual correcta y contraseña nueva de 40 bytes
- **THEN** la respuesta es `200` y en la base `password_hash` se actualizó, `debe_cambiar_password = false` y existe una fila de `evento_seguridad` con `actor = email` del usuario

### Requirement: Contraseña actual incorrecta devuelve 401

El sistema SHALL responder `401` cuando la contraseña actual no coincida con el hash almacenado, sin escribir en `intento_acceso` y sin tratar la petición como un login.

#### Scenario: Contraseña actual incorrecta

- **WHEN** una petición autenticada envía contraseña actual incorrecta a `POST /auth/cambiar-password`
- **THEN** la respuesta es `401`, no se inserta ninguna fila en `intento_acceso` y no se emite token

### Requirement: Contraseña mayor a 72 bytes devuelve 422

El sistema SHALL rechazar con `422` cualquier contraseña (actual o nueva) que supere los 72 bytes, antes de ejecutar bcrypt, sin escribir en la base.

#### Scenario: Contraseña nueva de 73 bytes

- **WHEN** el cuerpo de `POST /auth/cambiar-password` trae una contraseña nueva de 73 bytes
- **THEN** la respuesta es `422` y no se ejecuta ninguna operación bcrypt ni escritura en la base

#### Scenario: Contraseña actual de 73 bytes

- **WHEN** el cuerpo de `POST /auth/cambiar-password` trae una contraseña actual de 73 bytes
- **THEN** la respuesta es `422` y no se ejecuta ninguna operación bcrypt ni escritura en la base

### Requirement: No emite token nuevo ni rota la cookie (IN-03)

El sistema SHALL no emitir un JWT nuevo y no modificar la cookie `access_token` tras un cambio de contraseña exitoso; la misma cookie sigue siendo válida para el grupo protegido con `200` porque el estado vive en la base.

#### Scenario: Misma cookie sigue funcionando tras el cambio

- **WHEN** se completa `POST /auth/cambiar-password` exitosamente y la misma cookie `access_token` se envía a una ruta del grupo protegido
- **THEN** la ruta protegida responde `200` sin iniciar sesión de nuevo y sin cookie nueva

#### Scenario: No se emite token nuevo

- **WHEN** `POST /auth/cambiar-password` responde `200`
- **THEN** el cuerpo no contiene token ni JWT y no hay encabezado `Set-Cookie` con un valor de `access_token` distinto
