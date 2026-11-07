# Spec Delta — roles-de-usuario

## Purpose

Otorgar, listar y revocar roles de usuario con vigencia opcional e historial permanente, garantizando una única asignación abierta por rol, la autoprotección del administrador y la auditoría en la misma transacción.

## ADDED Requirements

### Requirement: Otorgar un rol con vigencia opcional

El sistema SHALL exponer `POST /usuarios/{id}/roles` para que un administrador otorgue un rol. El cuerpo SHALL aceptar exclusivamente `rol` y `vence_en`; cualquier campo adicional MUST responder `422`. `rol` SHALL ser uno de `ADMIN`, `VENDEDOR` o `CLIENTE`. `vence_en` SHALL ser opcional; si viene, MUST incluir zona horaria y MUST estar en el futuro: una fecha sin zona o en el pasado MUST responder `422` (no `409`). La respuesta SHALL ser `201` con `id`, `usuario_id`, `rol`, `desde`, `vence_en`, `revocada_en` y `otorgada_por`, con `desde` en el momento de la operación y `otorgada_por` igual al administrador que otorga.

#### Scenario: Otorgar sin vencimiento

- **WHEN** un administrador envía `POST /usuarios/{id}/roles` con `rol = "VENDEDOR"` y sin `vence_en`
- **THEN** la respuesta es `201` con `vence_en = null`, `revocada_en = null` y `otorgada_por` igual al id del administrador

#### Scenario: Otorgar con vencimiento futuro y con zona

- **WHEN** se envía `vence_en` con zona horaria y una fecha futura
- **THEN** la respuesta es `201` y la asignación conserva esa fecha y zona

#### Scenario: Vencimiento sin zona horaria

- **WHEN** se envía `vence_en` sin información de zona
- **THEN** la respuesta es `422` y no se crea ninguna asignación

#### Scenario: Vencimiento en el pasado

- **WHEN** se envía `vence_en` con zona horaria y una fecha anterior al momento de la petición
- **THEN** la respuesta es `422` y no se crea ninguna asignación

#### Scenario: Rol inexistente o campo de más

- **WHEN** se envía un `rol` fuera de `ADMIN`/`VENDEDOR`/`CLIENTE`, o un campo no declarado
- **THEN** la respuesta es `422` y no se crea ninguna asignación

#### Scenario: Usuario inexistente

- **WHEN** el `id` del usuario no existe
- **THEN** la respuesta es `404` y no se crea ninguna asignación

#### Scenario: Segunda asignación abierta del mismo rol

- **WHEN** el usuario ya tiene una asignación abierta y vigente de ese rol
- **THEN** la respuesta es `409`, no se escribe ninguna fila nueva y la asignación existente queda intacta

#### Scenario: Roles distintos en simultáneo

- **WHEN** el usuario tiene `ADMIN` abierto y se otorga `VENDEDOR`
- **THEN** la respuesta es `201` y el usuario queda con dos asignaciones abiertas distintas

### Requirement: Reasignar un rol vencido cierra la fila anterior

Cuando la única asignación abierta del rol pedido ya venció (`vence_en` anterior al momento de la petición y `revocada_en = null`), el sistema SHALL cerrar esa fila escribiendo `revocada_en` y SHALL abrir una nueva asignación, ambas escrituras en la misma transacción. El historial MUST conservar la fila cerrada. Una asignación revocada previamente no impide volver a otorgar el mismo rol.

#### Scenario: Reasignación tras el vencimiento

- **WHEN** un administrador otorga un rol cuya asignación abierta anterior ya venció
- **THEN** la respuesta es `201`, la fila anterior queda con `revocada_en` no nulo y existe una fila nueva abierta del mismo rol

#### Scenario: Ninguna fila se pierde en la reasignación

- **WHEN** se compara `GET /usuarios/{id}/roles` antes y después de una reasignación
- **THEN** la cantidad de filas del rol aumentó en una y la fila anterior sigue presente

#### Scenario: Reasignar un rol previamente revocado

- **WHEN** el usuario tuvo ese rol y su única fila está revocada
- **THEN** se puede otorgar otra vez con `201` y quedan las dos filas en el historial

#### Scenario: Reasignar mientras la asignación sigue vigente

- **WHEN** la asignación abierta del rol todavía no venció
- **THEN** la respuesta es `409` y no se escribe ninguna fila nueva

### Requirement: Revocar un rol sin borrar la fila

El sistema SHALL exponer `DELETE /usuarios/{id}/roles/{rol}` para revocar. La operación SHALL escribir `revocada_en` en la asignación abierta del rol y SHALL responder `200` con esa asignación ya revocada. La fila MUST NOT borrarse ni modificarse en ningún otro campo. Un `rol` fuera de `ADMIN`/`VENDEDOR`/`CLIENTE` en la ruta MUST responder `422`; un usuario inexistente o un rol que nunca se asignó a ese usuario MUST responder `404`; una asignación ya revocada MUST responder `409`. Revocar una asignación abierta pero ya vencida SHALL responder `200` y escribir su `revocada_en`.

#### Scenario: Revocación exitosa

- **WHEN** un administrador revoca un rol que el usuario tiene abierto
- **THEN** la respuesta es `200` con `revocada_en` no nulo y el resto de los campos sin cambios

#### Scenario: La fila sigue existiendo

- **WHEN** se cuentan las filas de `asignacion_rol` para ese usuario antes y después de revocar
- **THEN** la cantidad es la misma y la fila revocada sigue apareciendo en `GET /usuarios/{id}/roles`

#### Scenario: Rol nunca asignado

- **WHEN** el usuario no tiene ninguna fila de ese rol
- **THEN** la respuesta es `404`

#### Scenario: Asignación ya revocada

- **WHEN** el usuario tiene ese rol pero su única fila ya está revocada
- **THEN** la respuesta es `409` y no se escribe nada

#### Scenario: Revocar una asignación vencida

- **WHEN** la asignación abierta del rol ya venció pero no fue revocada
- **THEN** la respuesta es `200` y la fila queda con `revocada_en`

### Requirement: El efecto de la revocación es inmediato sobre la sesión abierta

Revocar un rol SHALL quitar el permiso en la petición siguiente del usuario afectado, sin esperar el vencimiento del token y sin invalidar ni rotar la cookie.

#### Scenario: Sesión abierta pierde el permiso

- **WHEN** un usuario con rol `VENDEDOR` inicia sesión, un administrador revoca ese rol y el mismo usuario repite con la misma cookie una petición que exigía `VENDEDOR`
- **THEN** la petición siguiente responde `403`

#### Scenario: La identidad no cambia

- **WHEN** el usuario afectado consulta su propia identidad con la misma cookie después de la revocación
- **THEN** la respuesta es `200` y sus roles vigentes ya no incluyen el rol revocado

### Requirement: Autoprotección del administrador

El sistema SHALL impedir con `409` que un administrador revoque su propio rol `ADMIN`, y SHALL impedir con `409` que la operación deje el sistema sin ningún administrador vigente, aunque la ejecute otro administrador. Solo cuentan como vigentes las asignaciones `ADMIN` con `revocada_en = null` y (`vence_en = null` o `vence_en` futuro). Una asignación `ADMIN` vencida o revocada no cuenta.

#### Scenario: Revocar el propio ADMIN

- **WHEN** un administrador autenticado intenta revocar su propio rol `ADMIN`
- **THEN** la respuesta es `409` y su asignación queda intacta

#### Scenario: Revocar el último ADMIN vigente

- **WHEN** otro administrador intenta revocar el único `ADMIN` vigente del sistema
- **THEN** la respuesta es `409` y esa asignación queda intacta

#### Scenario: Revocar un ADMIN cuando hay otro vigente

- **WHEN** existen dos administradores vigentes y uno revoca el `ADMIN` del otro
- **THEN** la respuesta es `200`

#### Scenario: Un ADMIN vencido no cuenta como vigente

- **WHEN** el sistema tiene un `ADMIN` vigente y otro con `vence_en` pasado, y se intenta revocar el vigente
- **THEN** la respuesta es `409`

### Requirement: Historial de roles de un usuario

El sistema SHALL exponer `GET /usuarios/{id}/roles` y responder `200` con todas las asignaciones del usuario, incluidas las vigentes, las vencidas y las revocadas, ordenadas de la más reciente a la más antigua por `desde` e `id`. La respuesta MUST NOT contener `password_hash`. Un usuario inexistente MUST responder `404`.

#### Scenario: Historial completo

- **WHEN** un usuario tuvo un rol revocado y luego otro vigente y un administrador consulta `GET /usuarios/{id}/roles`
- **THEN** la respuesta es `200` e incluye las dos filas, con su `desde`, `vence_en` y `revocada_en`

#### Scenario: Usuario inexistente en el historial

- **WHEN** se consulta `GET /usuarios/{id}/roles` con un `id` que no existe
- **THEN** la respuesta es `404`

### Requirement: Auditoría de cambios de rol en la misma transacción

Cada asignación, revocación y reasignación SHALL escribir una línea en `evento_seguridad` dentro de la misma transacción que el cambio, con `actor` igual al `email` del administrador que la ejecuta y una `accion` que identifique la operación, el rol y el usuario afectado.

#### Scenario: Asignación auditada

- **WHEN** un administrador otorga un rol con `201`
- **THEN** existe una línea de `evento_seguridad` con `actor` igual al email del administrador que menciona el rol otorgado

#### Scenario: Revocación auditada

- **WHEN** un administrador revoca un rol con `200`
- **THEN** existe una línea de `evento_seguridad` con `actor` igual al email del administrador que menciona la revocación

#### Scenario: Un rechazo no deja auditoría

- **WHEN** la operación responde `404`, `409` o `422`
- **THEN** no se escribe ninguna línea de `evento_seguridad` ni se modifica la asignación

#### Scenario: Un fallo de la transacción revierte también la auditoría

- **WHEN** se fuerza un error después de escribir el cambio de rol y antes de confirmar
- **THEN** no queda ni el cambio en `asignacion_rol` ni la línea de `evento_seguridad`

### Requirement: Control de acceso de la administración de roles

Las rutas de administración de roles SHALL exigir sesión válida y rol `ADMIN` vigente, y SHALL estar dentro del grupo de rutas protegido.

#### Scenario: Sin sesión

- **WHEN** se llama cualquiera de las rutas de roles sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: Autenticado sin rol ADMIN

- **WHEN** un usuario con rol vigente `VENDEDOR` o `CLIENTE` llama cualquiera de las rutas de roles
- **THEN** la respuesta es `403`

#### Scenario: Administrador con cambio de contraseña pendiente

- **WHEN** un usuario con rol `ADMIN` y `debe_cambiar_password = true` llama cualquiera de las rutas de roles
- **THEN** la respuesta es `403`
