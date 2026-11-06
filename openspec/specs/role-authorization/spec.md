# role-authorization Specification

## Purpose

Define cómo la API decide permisos por rol vigente en la base en cada petición, expone la identidad y ambos conjuntos de roles, y aplica la matriz RBAC de las rutas de personal sin confundir autenticación (`401`) con autorización (`403`).

## Requirements

### Requirement: Los roles vigentes se leen de la base en cada petición

Toda decisión de rol SHALL consultar `asignacion_rol` en la petición actual y considerar vigente sólo la fila con `revocada_en IS NULL` y `vence_en` nulo o posterior a `now()`. El claim `roles` del token no SHALL otorgar ni quitar permisos (`RN-04`).

#### Scenario: Rol vigente en la base autoriza

- **WHEN** una petición autenticada exige `ADMIN` y el usuario tiene una asignación `ADMIN` vigente
- **THEN** la petición continúa al handler de la ruta

#### Scenario: Revocación con la misma cookie abierta

- **WHEN** se revoca el rol exigido después de emitido el token y la misma cookie vuelve a pedir la ruta
- **THEN** la respuesta es `403` sin esperar el vencimiento del token

#### Scenario: Rol vencido no autoriza

- **WHEN** la única asignación del rol exigido tiene `vence_en <= now()`
- **THEN** la respuesta es `403`

#### Scenario: El token dice un rol que la base ya no tiene

- **WHEN** el claim `roles` incluye `ADMIN` pero la base no tiene una asignación `ADMIN` vigente
- **THEN** la respuesta es `403`

#### Scenario: La base otorga un rol que el token no declara

- **WHEN** el token fue emitido sin `ADMIN` pero la base tiene una asignación `ADMIN` vigente al momento de la petición
- **THEN** la petición continúa al handler de la ruta

### Requirement: La falta de rol se deniega por defecto

Cuando la identidad es válida pero no tiene ninguno de los roles exigidos, el sistema SHALL responder `403` con un cuerpo genérico que no enumere los roles del usuario ni detalles internos. La dependencia no SHALL abrir la ruta si se configura sin roles.

#### Scenario: Autenticado sin el rol exigido

- **WHEN** un usuario autenticado con rol `CLIENTE` pide una ruta que exige `ADMIN`
- **THEN** la respuesta es `403` con un mensaje genérico

#### Scenario: El cuerpo no revela los roles del usuario

- **WHEN** la respuesta es `403` por falta de rol
- **THEN** el cuerpo no incluye la lista de roles vigentes ni el nombre de los roles que sí tiene

#### Scenario: Configuración sin roles no abre la ruta

- **WHEN** se intenta construir la dependencia de rol sin ningún rol exigido
- **THEN** la construcción falla y la ruta no queda accesible

### Requirement: 401 es autenticación y 403 es autorización

Sin cookie, con token inválido o vencido, o con usuario inexistente o inactivo, el sistema SHALL responder `401` antes de evaluar roles. Una identidad válida sin permiso SHALL responder `403`. El encabezado `Authorization: Bearer` no SHALL autenticar una petición sin cookie.

#### Scenario: Sin cookie en una ruta de rol

- **WHEN** se pide una ruta que exige rol sin `access_token`
- **THEN** la respuesta es `401`

#### Scenario: Token inválido en una ruta de rol

- **WHEN** se pide una ruta que exige rol con un JWT inválido o vencido
- **THEN** la respuesta es `401` sin detalles criptográficos

#### Scenario: Identidad válida sin permiso

- **WHEN** la cookie resuelve un usuario activo que no tiene el rol exigido
- **THEN** la respuesta es `403`

#### Scenario: Authorization no sustituye la cookie

- **WHEN** la petición lleva `Authorization: Bearer <token>` válido pero no lleva cookie
- **THEN** la respuesta es `401`

### Requirement: /auth/yo expone la identidad y ambos conjuntos de roles

`GET /auth/yo` SHALL responder `200` con los campos `usuario`, `roles` y `roles_token`. `usuario` SHALL incluir `id`, `email`, `nombre`, `activo` y `debe_cambiar_password`; `roles` SHALL ser los vigentes leídos de la base y `roles_token` los del claim. No SHALL incluir `password_hash` ni el token. Sin identidad válida SHALL responder `401`.

#### Scenario: Roles de la base y del token difieren

- **WHEN** un usuario autenticado tiene un rol revocado después de emitido el token y consulta `GET /auth/yo`
- **THEN** la respuesta es `200` y `roles` ya no contiene ese rol mientras `roles_token` sí lo conserva

#### Scenario: Sin cookie

- **WHEN** se consulta `GET /auth/yo` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: La respuesta no filtra el hash ni el token

- **WHEN** `GET /auth/yo` responde `200`
- **THEN** el cuerpo no contiene `password_hash` ni el valor de `access_token`

### Requirement: Las mutaciones de catálogo y stock exigen ADMIN

Las rutas `POST /editoriales`, `PATCH /editoriales/{id}`, `POST /generos`, `POST /autores`, `PATCH /autores/{id}`, `POST /libros`, `PATCH /libros/{id}`, `DELETE /libros/{id}`, `POST /libros/{id}/reponer` y `GET /libros/{id}/movimientos` SHALL exigir rol `ADMIN`.

#### Scenario: ADMIN opera el catálogo

- **WHEN** un `ADMIN` autenticado llama una mutación de catálogo o stock con un cuerpo válido
- **THEN** la respuesta es la que define el contrato del endpoint (`201`, `200` o `204`)

#### Scenario: Personal de ventas no administra el catálogo

- **WHEN** un `VENDEDOR` autenticado llama una mutación de catálogo o stock
- **THEN** la respuesta es `403`

#### Scenario: Cliente no administra el catálogo

- **WHEN** un `CLIENTE` autenticado llama una mutación de catálogo o stock
- **THEN** la respuesta es `403`

#### Scenario: Sin sesión no se administra el catálogo

- **WHEN** se llama una mutación de catálogo o stock sin cookie válida
- **THEN** la respuesta es `401`

### Requirement: Las rutas de clientes exigen VENDEDOR o ADMIN

`POST /clientes`, `GET /clientes/{id}`, `PATCH /clientes/{id}`, `POST /clientes/{id}/perfil` y `GET /clientes/{id}/ventas` SHALL exigir rol `VENDEDOR` o `ADMIN`. Sin cookie válida SHALL responder `401`; un `CLIENTE` SHALL responder `403`; un usuario con cualquiera de los dos roles SHALL continuar al contrato del endpoint.

#### Scenario: VENDEDOR atiende clientes

- **WHEN** un `VENDEDOR` autenticado llama una ruta de clientes con datos válidos
- **THEN** la respuesta es la que define el contrato del endpoint

#### Scenario: ADMIN atiende clientes

- **WHEN** un `ADMIN` autenticado llama una ruta de clientes con datos válidos
- **THEN** la respuesta es la que define el contrato del endpoint

#### Scenario: CLIENTE no accede a rutas de clientes

- **WHEN** un `CLIENTE` autenticado llama `GET /clientes/{id}/ventas` con un cliente existente
- **THEN** la respuesta es `403` y no se devuelve ninguna venta

#### Scenario: Sin sesión no se accede a clientes

- **WHEN** se llama cualquier ruta de clientes sin cookie válida
- **THEN** la respuesta es `401`

### Requirement: Las lecturas de ventas separan personal de propiedad

`GET /ventas` SHALL exigir rol `VENDEDOR` o `ADMIN`. `GET /ventas/{id}` y `GET /mis-ventas` SHALL exigir sólo autenticación y no SHALL llevar una exigencia de rol, porque la propiedad la decide el servicio (`RN-14`).

#### Scenario: El personal lista ventas

- **WHEN** un `VENDEDOR` o `ADMIN` autenticado pide `GET /ventas`
- **THEN** la respuesta es `200` con el envoltorio paginado

#### Scenario: Un CLIENTE no lista todas las ventas

- **WHEN** un `CLIENTE` autenticado pide `GET /ventas`
- **THEN** la respuesta es `403`

#### Scenario: El dueño consulta su venta sin rol de personal

- **WHEN** el `CLIENTE` dueño de una venta pide `GET /ventas/{id}`
- **THEN** la respuesta es `200`

#### Scenario: Otro cliente no consulta una venta ajena

- **WHEN** un `CLIENTE` que no es dueño pide `GET /ventas/{id}` existente
- **THEN** la respuesta es `403`, decidida por el servicio y no por una exigencia de rol

#### Scenario: Mis ventas sólo pide sesión

- **WHEN** se pide `GET /mis-ventas` sin cookie válida
- **THEN** la respuesta es `401`; con sesión de un usuario sin ficha de cliente la respuesta es `200` con página vacía

### Requirement: La autorización comparte la sesión del UoW

La autenticación, la lectura de roles y el Unit of Work del router SHALL usar la misma sesión de la petición, de modo que una petición autenticada que autoriza y luego consulta datos de negocio no SHALL tomar una segunda conexión del pool.

#### Scenario: Una sola sesión por petición

- **WHEN** se instrumenta la dependencia de sesión en una petición autenticada que también construye un UoW
- **THEN** la dependencia de sesión se invoca una sola vez y ambas piezas reciben la misma instancia

#### Scenario: La sesión se cierra al terminar

- **WHEN** la petición termina, con éxito o con error
- **THEN** la sesión compartida se cierra una sola vez
