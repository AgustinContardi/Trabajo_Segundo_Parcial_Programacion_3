# Funcionalidades

## Épica 1: Autenticación y Gestión de Sesión

### US-01: Login con rate limiting
- **Descripción**: Endpoint POST `/login` que primero aplica rate limit (429 con `Retry-After`), luego verifica credenciales.
- **Comportamiento**: Mismo mensaje y mismo tiempo de respuesta tanto si el correo existe como si no (hash ficticio).
- **Validaciones**: 
  - Rate limit activado antes que verificación de credenciales
  - `429` con encabezado `Retry-After`
  - Cookie `access_token` con propiedades HttpOnly, SameSite=Lax, Max-Age, Secure según entorno

### US-02: Login devuelve cambio de password obligatorio
- **Descripción**: Login devuelve `debe_cambiar_password` en el nivel superior del JSON de respuesta.
- **Consecuencia**: El usuario debe dirigirse a `/auth/cambiar-password` obligatoriamente.

### US-03: Cambiar password
- **Descripción**: Endpoint `POST /auth/cambiar-password` que entrega cookie nueva y invalida la anterior (anta cookie vieja da 401).
- **Validaciones**: 
  - Token `iat` y `exp` numéricos (NumericDate)
  - Comparación con `password_cambiada_en` sin truncar

### US-04: Logout (invalida cookie)
- **Descripción**: Endpoint que invalida la cookie `access_token` en el cliente.

## Épica 2: Autorización y Roles

### US-05: Require rol como dependencia
- **Descripción**: `require_rol` como dependencia FastAPI, no dentro del handler.
- **Comportamiento**: Relee roles vigentes de `asignacion_rol` en cada request.

### US-06: Permiso antes que estado
- **Descripción**: 403 antes que 409 en el orden de códigos de error.
- **Contexto**: El permiso se verifica antes que el estado de la operación.

### US-07: Reglas de recurso
- **Contexto**: 
  - Mecánico asignado a un vehículo puede operar en él.
  - Dueño del vehículo tiene acceso exclusivo.
- **Consecuencia**: 403 si no se cumplen las reglas de recurso.

### US-08: Gating por grupo de rutas
- **Contexto**: `/auth/*` y `/health/*` exentas de gating de RN-06.
- **Comportamiento**: Estas rutas no requieren verificación de rol/permiso.

## Épica 3: Módulo de Usuarios y Clientes

### US-09: CRUD de usuarios (gated)
- **Descripción**: Solo ADMIN puede crear/leer/actualizar/eliminar usuarios.
- **Endpoints**: `GET /usuarios`, `POST /usuarios`, `PUT /usuarios/{id}`, `DELETE /usuarios/{id}`

### US-10: Perfil de cliente
- **Descripción**: El cliente puede consultar su propio perfil y listar sus vehículos.
- **Endpoints**: `GET /mis-perfil`, `GET /mis-vehiculos`

### US-11: Crear cliente y asociar usuario
- **Descripción**: Flujo de onboarding donde un usuario se registra y se crea su registro de cliente asociado.
- **Validaciones**: `user_id` UNIQUE en tabla `clientes`.

## Épica 4: Módulo de Vehículos

### US-12: CRUD de vehículos (role-gated)
- **Descripción**: 
  - ADMIN: CRUD completo
  - MECANICO: CRUD con restricción de vehículos asignados
  - CLIENTE: Solo puede ver/gestionar sus propios vehículos
- **Endpoints**: `POST /vehicles`, `GET /vehicles`, `PUT /vehicles/{id}`, `DELETE /vehicles/{id}`

### US-13: Dar de baja vehículo
- **Descripción**: Solo está permitido si no hay órdenes abiertas (PENDIENTE o EN_REPARACION).
- **Consecuencia**: 403 si hay órdenes asociadas.

### US-14: Búsqueda de vehículos
- **Descripción**: Parámetros ligados, nunca concatenación SQL (RN-15).

## Épica 5: Módulo de Repuestos e Inventario

### US-15: CRUD de repuestos
- **Descripción**: 
  - ADMIN: CRUD completo sobre repuestos y precios
  - MECANICO: Solo consulta y movimientos autorizados
  - CLIENTE: Sin acceso directo

### US-16: Control de stock
- **Contexto**: Un único punto de escritura para alta, reposición y terminación de órdenes.
- **Regla**: RN-12 - stock: un único punto de escritura; alta, reposición y terminación dejan movimiento.
- **Consecuencia**: Modificación directa de stock fuera de estos puntos es rejection.

### US-17: Movimiento de stock
- **Descripción**: Cada operación de stock deja un registro en `historial_stock` o tabla similar.

### US-18: Reposición de stock
- **Contexto**: Carga de nuevo stock al inventario con registro de movimiento.

## Épica 6: Módulo de Órdenes de Servicio

### US-19: Crear orden
- **Contexto**: RN-08 - crear orden: PENDIENTE, al menos un ítem, sin repuestos repetidos, precio copiado, total calculado, historial inicial.
- **Endpoints**: `POST /orders`

### US-20: Consultar orden
- **Descripción**: Consultar por ID con validación de permisos (dueño o rol mayor).
- **Endpoints**: `GET /orders/{id}`

### US-21: Terminar orden
- **Contexto**: RN-09 - termina: descuenta stock, deja movimiento por ítem y línea de historial; si falta stock, nada queda escrito.
- **Endpoints**: `PATCH /orders/{id}/terminar`

### US-22: Cancelar orden
- **Contexto**: RN-10 - cancelar: recepción, admin o dueño; permiso antes que estado; solo desde PENDIENTE.
- **Endpoints**: `PATCH /orders/{id}/cancelar`

### US-23: Iniciar orden
- **Contexto**: RN-11 - iniciar: solo mecánico; queda asignado; PENDIENTE → EN_REPARACION.
- **Endpoints**: `PATCH /orders/{id}/iniciar`

### US-24: Paginación de órdenes
- **Contexto**: RN-18 - estructura `{items,total,page,size,pages}`, default size 20.
- **Endpoints**: `GET /orders?page=1&size=20`

### US-25: Búsqueda y filtrado de órdenes
- **Contexto**: Parámetros ligados (nunca concatenación). Búsqueda con `q` parameter.
- **Endpoints**: `GET /orders?q=term`

## Épica 7: Configuración y Settings

### US-25: Settings con todos los parámetros
- **Contexto**: `Settings` con `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`, `POOL_SIZE`.
- **Regla crítica**: `JWT_SECRET` obligatorio, sin default; la app no arranca si falta.

### US-26: URL computada con driver async
- **Contexto**: `@computed_field` que arma la URL con driver async a partir de los componentes de Settings.

### US-27: get_session lee de app.state
- **Contexto**: `get_session` lee el `sessionmaker` de `app.state`, no de un global.

### US-28: Motor y sessionmaker solo en lifespan
- **Contexto**: Motor y `sessionmaker` creados **solo** en `lifespan`; `dispose()` al apagar.

## Épica 8: Búsqueda y Paginación

### US-29: Parámetros de búsqueda
- **Contexto**: `q` parameter con parámetros ligados (nunca concatenación).
- **Regla**: RN-15 - búsqueda con parámetros ligados (nunca concatenación).

### US-30: Página fuera de rango
- **Contexto**: `page` fuera de rango retorna **422**.
- **Comportamiento**: `size` default **20**, rango 1..100.

### US-31: Cero resultados
- **Contexto**: `cero resultados` → `una página vacía` (con `items: []` pero `total: 0`).

## Épica 9: Triggers y Validaciones a Nivel BD

### US-32: Trigger solo-agregado
- **Contexto**: RN-07 y RN-25 - triggers bloquean UPDATE y DELETE en las tres tablas (`users`, `vehicles`, `repuestos`).
- **Implementación**: A nivel de base de datos, no en la aplicación.

### US-33: Migración manual de triggers
- **Contexto**: Migración manual de triggers de solo-agregado debe ejecutarse después de `alembic upgrade head`.
- **Consecuencia**: Sin triggers, la integridad de "solo-agregado" no está garantizada.