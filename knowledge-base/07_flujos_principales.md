# Flujos Principales

## Flujo 1: Ciclo de Vida de una Orden de Servicio

### 1. Crear Orden (POST /orders)
- **Precondiciones**: 
  - Usuario autenticado con rol CLIENTE o MECANICO/ADMIN
  - Datos válidos: ítem(s) con repuesto y cantidad
  - No hay repuestos repetidos en la misma orden
- **Flujo**:
  1. Validación de negocio (RN-08): estado PENDIENTE, al menos un ítem
  2. Verificación de stock disponible (RN-12)
  3. Creación de la orden con estado PENDIENTE
  4. Cálculo y almacenamiento del total
  5. Inicialización del historial de precios (si aplica)
  6. **Éxito**: Orden creada con ID retornado

### 2. Iniciar Orden (PATCH /orders/{id}/iniciar)
- **Precondiciones**: 
  - Solo MECANICO puede iniciar
  - Orden debe estar en estado PENDIENTE
- **Flujo**:
  1. Verificación de permiso (RN-11): ¿Soy el mecánico asignado o soy ADMIN?
  2. Validación de estado: `PENDIENTE` → `EN_REPARACION`
  3. Asignación del mecánico a la orden
  4. **Éxito**: Estado actualizado, orden asignada

### 3. Terminar Orden (PATCH /orders/{id}/terminar)
- **Precondiciones**: 
  - Rol: MECANICO asignado o ADMIN
  - La orden debe estar en estado EN_REPARACION
- **Flujo**:
  1. Verificación de permiso y estado
  2. Validación de stock disponible (RN-09): ¿Hay suficiente stock para cada ítem?
  3. **SI hay stock suficiente**:
     - Descuenta stock de cada repuesto ítem
     - Deja un movimiento por ítem en historial_stock
     - Deja una línea de historial en la orden
     - Actualiza estado a COMPLETADA o regresa a PENDIENTE según convenio
     - **Éxito**: Todo actualizado en la misma transacción
  4. **SI no hay stock suficiente**:
     - **Nada queda escrito** (transacción rollbackearse)
     - La orden permanece en EN_REPARACION con stock original
     - **Éxito**: Fallo controlado, consistencia garantizada

### 4. Cancelar Orden (PATCH /orders/{id}/cancelar)
- **Precondiciones**: 
  - Quién puede: el propio cliente, un administrador, o un mecánico asignado
  - La orden debe estar en estado PENDIENTE
- **Flujo**:
  1. Verificación de permiso (RN-10): ¿Soy quién me corresponde?
  2. Validación de estado: ¿Es PENDIENTE?
  3. Si sí: Cambia estado a CANCELADA, libera recursos si aplica
  4. Si no: Retorno 409 (estado incorrecto) o 403 (sin permiso)

## Flujo 2: Autenticación Completa

### 5. Flujo de Login
- **Paso 1**: Cliente envía credenciales a `POST /login`
- **Paso 2**: Sistema aplica rate limit (si excede → 429 con `Retry-After`)
- **Paso 3**: Verificación de credenciales contra bcrypt hash
- **Paso 4**: Si credenciales inválidas → mensaje idéntico al caso exitoso (por seguridad)
- **Paso 5**: Generación de token JWT con `iat` y `exp` numéricos
- **Paso 6**: Cookie `access_token` configurada con:
  - `HttpOnly`
  - `SameSite=Lax`
  - `Max-Age` (según configuración)
  - `Secure` según entorno (producción vs desarrollo)
- **Paso 7**: Respuesta incluye `debe_cambiar_password` si corresponde (RN related)

### 6. Flujo de Cambio de Password
- **Paso 1**: Usuario autenticado accede a `POST /auth/cambiar-password`
- **Paso 2**: Verificación de token actual (iat/exp contra password_cambiada_en)
- **Paso 3**: Nueva password hasheada con bcrypt (mismo rounds configuración)
- **Paso 4**: Actualización de `password_cambiada_en` timestamp
- **Paso 5**: Cookie nueva entregada, la anterior invalida (da 401 si se usa)

## Flujo 3: Búsqueda y Paginación

### 7. Búsqueda de Órdenes o Repuestos
- **Paso 1**: Parámetro `q` en query string
- **Paso 2**: Validación de que no hay concatenación SQL (usar parámetros ligados)
- **Paso 3**: Ejecución de query con filtros vinculados
- **Paso 4**: Retorno de resultados con estructura `{items, total, page, size, pages}`
- **Regla**: RN-15 y RN-19 - total debe usar los mismos filtros

### 8. Paginación de Listados
- **Paso 1**: Parámetros `page` (default: no especificar, usa 1) y `size` (default: 20, rango 1..100)
- **Paso 2**: Cálculo de `offset` = `(page - 1) * size`
- **Paso 3**: Query con `LIMIT size OFFSET offset`
- **Paso 4**: Cálculo de `total` con los mismos filtros de búsqueda
- **Paso 5**: Cálculo de `pages = ceil(total / size)`
- **Validaciones**:
  - `page` fuera de rango → 422
  - Cero resultados → página vacía con `items: []` y `total: 0`

## Flujo 4: Configuración y Arranque

### 9. Arranque de Aplicación (lifespan)
- **Paso 1**: Crear motor async de PostgreSQL
- **Paso 2**: Crear `sessionmaker` vinculado al motor
- **Paso 3**: `yield` / `await` - aplicación está lista
- **Paso 4**: Al apagar: `dispose()` sobre motor y sessionmaker
- **Regla**: Motor y sessionmaker creados **solo** en `lifespan` (RN-28)

### 10. Carga de Datos Iniciales (seed)
- **Paso 1**: Ejecutar `seed.py` después de `alembic upgrade head`
- **Paso 2**: Cargar catálogo de estados primero (por dependencia)
- **Paso 3**: Cargar usuarios de la consigna (admin1, admin2, mecanico1, mecanico2, nuevo)
- **Paso 4**: Cargar clientes específicos (Laura, Jorge, y otros de prueba)
- **Paso 5**: Cargar catálogo de repuestos (filtro 10, pastillas 4, bujía 2, aceite 20)
- **Paso 6**: Cargar órdenes de prueba (orden 1 PENDIENTE, orden 2 EN_REPARACION)
- **Paso 7**: Cargar historial de precios (8000 → 8500, evento SISTEMA)
- **Validación**: Un test afirma estos valores leyendo la base

## Flujo 5: Migraciones y Deploy

### 11. Flujo de Migración
- **Paso 1**: `alembic upgrade head` para aplicar nuevas migraciones
- **Paso 2**: Verificar `alembic check` sin operaciones nuevas (idempotente)
- **Paso 3**: Verificar `alembic upgrade head` / `downgrade base` / `upgrade head` sin error
- **Paso 4**: Revisar migración generada: comentario sobre qué se revisó y qué se cambió a mano (RN-06)
- **Paso 5**: Aplicar triggers manuales de solo-agregado (post-migración)
- **Paso 6**: Ejecutar seed.py para cargar datos iniciales
- **Paso 7**: Verificar que la aplicación arranca correctamente

### 12. Deploy Limpio
- **Pre-requisitos**: 
  - `git status` limpio y `HEAD == origin/main`
  - Sin `.env` en el repo
  - `.gitignore` incluye `.env`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.venv`
- **Pasos**:
  1. `zip` generado desde el commit final
  2. README con: integrantes, comisión, instalación, migraciones, seed, tests, ejecución
  3. `git status` limpio
  4. Zip entregado al evaluador