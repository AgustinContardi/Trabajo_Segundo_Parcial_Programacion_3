# CHANGES — Secuencia de Implementación

> Índice canónico de todos los cambios del proyecto Taller Mecánico Integral.
> Cada cambio es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

---

## Cómo usar este documento

1. **Identificar change** - Revisar el árbol de dependencias y seleccionar el próximo change disponible
2. **Leer KB** - Consultar `knowledge-base/0X_archivo.md` secciones indicadas en "Leer antes"
3. **Proponer** - Ejecutar `/opsx:propose C-NN-{nombre}`
4. **Implementar** - `/opsx:apply C-NN-{nombre}`
5. **Archivar** - `/opsx:archive C-NN-{nombre}` y marcar checkbox ✅

---

## Árbol de dependencias

```
C-01 foundation-setup                                   [ ] base
      │
      ├─> C-02 core-models                              [ ] repositorios base, schemas base
      │        │
      │        └─> C-03 auth-jwt                        [ ] JWT auth, cookies, rate limiting
      │                │
      │                └─> C-04 usuarios-rbac           [ ] roles, permisos, gating
      │                        
      │                         └─> C-05 clientes-vehiculos [ ] clientes, vehicles, 1:1 user-cliente
      │                                       
      │                                        └─> C-06 repuestos-catalogo [ ] catálogo repuestos, stock, CHECKs
      │
      └─> C-07 mod-usuarios                            [ ] CRUD usuarios completo
                  
                  └─> C-08 mod-clientes                      [ ] CRUD clientes con usuario linkage
                  
                        └─> C-09 mod-vehiculos                   [ ] CRUD vehículos, CHECK agno, patente UNIQUE
                        
                              └─> C-10 mod-repuestos               [ ] CRUD repuestos, movimiento stock
                              
                                    └─> C-11 mod-items          [ ] líneas de orden, ítems, precio_total generado
                                    
                                          └─> C-12 mod-ordenes-PENDIENTE [ ] crear orden, validaciones RN-08
                                              
                                                  └─> C-13 mod-ordenes-INICIO   [ ] PENDIENTE → EN_REPARACION, asignación mecánico
                                                      
                                                          └─> C-14 mod-ordenes-TERMINAR [ ] descuento stock, historial, validación stock suficiente
                                                                
                                                                └─> C-15 mod-ordenes-CANCELAR [ ] validaciones estado PENDIENTE, permisos
                                                                        
                                                                        └─> C-16 historial-precios [ ] tabla historial_precios, trigger cambios
																			
																					└─> C-17 mod-reportes         [ ] endpoints de reportes, estadísticas, paginación
																					
																					└─> C-18 admin-dashboard       [ ] vistas admin, estadísticas agregadas
																								
																									└─> C-19 refactor-ui           [ ] restyle visual, consistencia CSS
																										
																											└─> C-20 seed-data-final       [ ] seed idempotente con todos los datos de la consigna
```

---

## Paralelismo por fase (GATES)

GATE 0: Fundación completada (C-01 ✓)
  → C-02 core-models                    [Agente A - Backend Core]
  → C-03 auth-jwt                       [Agente B - Auth Specialist]
  → C-04 usuarios-rbac                  [Agente C - Security]

GATE 1: Modelos core y auth listos
  → C-05 clientes-vehiculos             [Agente A]
  → C-06 repuestos-catalogo             [Agente B]
  → C-07 mod-usuarios                    [Agente C]

GATE 2: ← FORK Múltiples ramas
  → C-08 mod-clientes                   [Agente A]
  → C-09 mod-vehiculos                  [Agente B]
  → C-10 mod-repuestos                  [Agente C]

GATE 3: ← FORK Múltiples ramas
  → C-11 mod-items                      [Agente A]
  → C-12 mod-ordenes-PENDIENTE          [Agente B]
  → C-13 mod-ordenes-INICIO             [Agente C — si C-12 ✓]

GATE 4: Flujo de órdenes consolidado
  → C-14 mod-ordenes-TERMINAR           [Agente A — si C-13 ✓]
  → C-15 mod-ordenes-CANCELAR           [Agente B — si C-12 ✓]

GATE 5: Historial y reports
  → C-16 historial-precios              [Agente A]
  → C-17 mod-reportes                   [Agente B]

GATE 6: Administración
  → C-18 admin-dashboard                [Agente A]
  → C-19 refactor-ui                    [Agente B — si C-18 ✓]

GATE 7: Finalización total
  → C-20 seed-data-final                [Agente A — si C-16, C-17 ✓]

---

## Camino crítico (9 changes — mínimo irreducible)

C-01 → C-03 → C-04 → C-05 → C-09 → C-12 → C-14 → C-16 → C-20

**Cambios en el camino crítico**: foundation, auth, RBAC, clientes, vehículo, creación orden, terminar orden, historial precios, seed final.

---

## Plan óptimo con 3 agentes

| Paso | Agente A (Backend Core) | Agente B (Backend Aux) | Agente C (Security/Frontend) |
|------|-------------------------|------------------------|------------------------------|
| 1 | C-01 foundation-setup | C-04 usuarios-rbac | C-03 auth-jwt |
| 2 | C-02 core-models | C-07 mod-usuarios | — |
| 3 | — | C-08 mod-clientes | C-05 clientes-vehiculos |
| 4 | C-06 repuestos-catalogo | C-09 mod-vehiculos | — |
| 5 | C-11 mod-items | C-10 mod-repuestos | C-12 mod-ordenes-PENDIENTE |
| 6 | C-13 mod-ordenes-INICIO | C-14 mod-ordenes-TERMINAR | C-15 mod-ordenes-CANCELAR |
| 7 | C-16 historial-precios | C-17 mod-reportes | C-18 admin-dashboard |
| 8 | C-20 seed-data-final | — | C-19 refactor-ui |

---

## FASE 1 — Fundación y Autenticación

> Cambios esenciales para que el sistema arranque y sea seguro.

### [C-01] foundation-setup
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Estructura de directorio `app/` completa
  - `main.py` con `lifespan` (motor + sessionmaker, dispose al apagar)
  - `config.py` con Settings obligatorios (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT, JWT_SECRET sin default, ACCESS_TOKEN_TTL_MIN, BCRYPT_ROUNDS, BCRYPT_MAX_CONCURRENCY, LOGIN_MAX_INTENTOS, LOGIN_VENTANA_SEG, POOL_SIZE)
  - `alembic.ini` sin `sqlalchemy.url` con credenciales; `migrations/env.py` lee de Settings
  - `.env.example` (sin punto inicial) y `.gitignore` con `.env`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.venv`
  - `requirements.txt` actualizado
  - `seed.py` estructura base (lista para correr después de migraciones)
- **Dependencias**: ninguna
- **Governance**: CRITICO — foundation sobre la cual todo lo demás depende
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — patrones y estructura de directorios
  - `knowledge-base/09_decisiones_y_supuestos.md` — decisiones D-01 a D-14

### [C-02] core-models
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `BaseRepository[T]` y `SoftDeleteRepository[T]` separados
  - Repositorio conoce su clase de modelo
  - Ningún repositorio hace `commit()`; solo `flush()`
  - Toda precarga vive en el repositorio
  - `UnitOfWorkBase` confirma/revierte en `__aexit__` y no cierra sesión
  - Router construye el UoW; servicio lo abre; ningún servicio lo construye
  - Schemas Pydantic con `extra="forbid"` en todas las operaciones (Create, Update, Read)
- **Dependencias**: C-01
- **Governance**: ALTO — patterns fundamentales, sin estos nada más puede avanzar
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — modelo entidad-relación y constraints
  - `knowledge-base/08_arquitectura_propuesta.md` — patterns Repository y UoW

### [C-03] auth-jwt
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Login POST `/login` con rate limiting (5 intentos/60s por IP+email, 429 con Retry-After)
  - Rate limit antes que verificación de credenciales (RN-20)
  - Mismo mensaje y mismo tiempo para correo existente/inexistente (hash ficticio)
  - Cookie `access_token`: HttpOnly, SameSite=Lax, Max-Age, Secure según entorno
  - Token nunca viaja en body ni se lee de Authorization header
  - Login devuelve `debe_cambiar_password` en nivel superior
  - `POST /auth/cambiar-password`: entrega cookie nueva, la anterior da 401
  - `iat` y `exp` numéricos (NumericDate), comparación con `password_cambiada_en` sin truncar
  - Rate limiting con `LOGIN_MAX_INTENTOS` y `LOGIN_VENTANA_SEG` desde Settings
  - bcrypt con `rounds` desde Settings, `to_thread` + semáforo para operaciones costosas
- **Dependencias**: C-01 (configuración), C-02 (schemas Pydantic para usuario)
- **Governance**: CRITICO — seguridad de acceso al sistema
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` — roles y rutas públicas exentas
  - `knowledge-base/05_reglas_de_negocio.md` — RN-20, RN-21, RN-22

---

## FASE 2 — Módulos de Datos Básicos

> Clientes, vehículos y catálogo de repuestos.

### [C-05] clientes-vehiculos
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelo `cliente` con `user_id` FK → users.id UNIQUE
  - Modelo `vehicle` con `cliente_id` FK → clientes.id, CHECK agno (1900-2026), patente UNIQUE, estado
  - Trigger `solo-agregado` bloquea UPDATE/DELETE en vehicles, repuestos, users
  - Índice en cada FK (consigna Anexo A)
  - Relación 1:1 usuario-cliente con acceso inverso
  - No se puede dar de baja vehículo con órdenes abiertas (RN-14)
- **Dependencias**: C-02 (repositorios Base/SoftDelete), C-01 (configuración)
- **Governance**: ALTO — modelo de datos core, restricciones de negocio
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — entidades vehicles, clientes, relaciones
  - `knowledge-base/05_reglas_de_negocio.md` — RN-03, RN-04, RN-14

### [C-06] repuestos-catalogo
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelo `repuesto` con nombre, descripción, precio_costo, precio_venta (CHECK > 0), stock (CHECK >= 0), stock_minimo (default 10)
  - Trigger `solo-agregado` en repuestos
  - Historial de precios: tabla `historial_precios` con repuesto_id, precio_anterior, precio_nuevo, cambio_tipo, usuario_id, fecha
  - Cada cambio de precio deja historial en misma transacción; sin cambio, sin línea (RN-13)
  - Mínimo stock 10, CHECKs de dominio
- **Dependencias**: C-02 (repositorios), C-01 (configuración)
- **Governance**: ALTO — inventario y precios son críticos
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — entidad repuestos y CHECKs
  - `knowledge-base/05_reglas_de_negocio.md` — RN-13, RN-14

---

## FASE 3 — Módulos de Operaciones

> Usuarios, clientes, módulos completos.

### [C-07] mod-usuarios
- **Estado**: `[ ]` pendiente
- **Scope**:
  - CRUD completo de usuarios (solo ADMIN)
  - `require_rol` como dependencia FastAPI, no dentro handler
  - Relee roles vigentes de `asignacion_rol` en cada request
  - Gating de rutas: `/auth/*` y `/health/*` exentas
  - `/mis-*` solo con sesión, dueño estricto, 403 si no es propio
  - `asignacion_rol` table para asociación user-role
- **Dependencias**: C-02 (schemas Pydantic), C-03 (auth funcionando), C-04 (RBAC structure)
- **Governance**: ALTO — gestión de usuarios es sensible
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` — tabla RBAC completa
  - `knowledge-base/05_reglas_de_negocio.md` — RN-01, RN-23, RN-24

### [C-08] mod-clientes
- **Estado**: `[ ]` pendiente
- **Scope**:
  - CRUD clientes (ADMIN completo, CLIENTE propio)
  - Validar que user tiene cliente asociado (o crear uno al registrarse)
  - Listar vehículos de un cliente
  - Exención `/mis-*` para cliente ver sus propios datos
- **Dependencies**: C-05 (vehículos creables), C-07 (auth y RBAC)
- **Governance**: MEDIO — datos de cliente, no tan críticos como auth
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` — relaciones cliente/usuario
  - `knowledge-base/07_flujos_principales.md` — flujos de cliente

### [C-09] mod-vehiculos
- **Estado**: `[ ]` pendiente
- **Scope**:
  - CRUD vehículos (ADMIN: completo, MECANICO: vehículos asignados, CLIENTE: solo propios)
  - CHECK agno (1900-2026), patente UNIQUE
  - No dar de baja vehículo con órdenes abiertas (RN-14)
  - Índice en FK vehicle→cliente
- **Dependencias**: C-05 (clientes creables), C-07 (auth RBAC para roles)
- **Governance**: ALTO — vehículos son recursos centrales
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — modelo vehicle completo
  - `knowledge-base/05_reglas_de_negocio.md` — RN-14

---

## FASE 4 — Catálogo y Órdenes

> Repuestos e inventario + flujo de órdenes completo.

### [C-10] mod-repuestos
- **Estado**: `[ ]` pendiente
- **Scope**:
  - CRUD repuestos (ADMIN: completo, MECANICO: consulta+movimientos autorizados, CLIENTE: sin acceso)
  - Validación stock: un único punto de escritura (alta, reposición, terminación)
  - Cada operación deja movimiento en historial_stock
  - Reposición de stock con registro de movimiento
  - Precio: historial en misma transacción; sin cambio, sin línea (RN-13)
- **Dependencias**: C-06 (catálogo base), C-03 (auth RBAC)
- **Governance**: ALTO — inventario y precios críticos
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — modelo repuestos completo
  - `knowledge-base/05_reglas_de_negocio.md` — RN-12, RN-13

### [C-11] mod-items
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelo `items` (líneas de orden) con FK → orden, FK → vehículo (opcional), FK → repuesto (opcional)
  - `nombre` denormalizado para búsquedas
  - `cantidad` CHECK (> 0), `precio_unitario` CHECK (> 0), `precio_total` GENERATED ALWAYS AS (cantidad * precio_unitario) STORED
  - No pueden haber repuestos repetidos en la misma orden
  - Item pertenece a una orden y opcionalmente a un vehículo
- **Dependencias**: C-10 (repuestos CRUD), C-09 (vehículos), C-12 (órdenes después)
- **Governance**: MEDIO — items son internas a las órdenes
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — modelo items y relaciones
  - `knowledge-base/07_flujos_principales.md` — flujo de creación de órdenes

### [C-12] mod-ordenes-PENDIENTE
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Endpoint POST `/orders` con validaciones RN-08
  - Estado inicial PENDIENTE
  - Al menos un ítem obligatorio
  - Sin repuestos repetidos en la misma orden
  - Precio copiado y total calculado
  - Historial inicial creado
  - Verificación de stock disponible (RN-12)
- **Dependencias**: C-11 (items), C-06 (repuestos para stock check), C-03 (auth), C-04 (RBAC)
- **Governance**: ALTO — creación de órdenes es el núcleo del negocio
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — flujo completo de orden
  - `knowledge-base/05_reglas_de_negocio.md` — RN-08, RN-09, RN-12

---

## FASE 5 — Flujo de Órdenes Completo

> Estados: PENDIENTE → EN_REPARACIÓN → COMPLETADA/REVERTIDA

### [C-13] mod-ordenes-INICIO
- **Estado**: `[ ]` pendiente
- **Scope**:
  - PATCH `/orders/{id}/iniciar`
  - Solo MECANICO puede iniciar (o ADMIN)
  - Orden debe estar PENDIENTE
  - Estado pasa PENDIENTE → EN_REPARACION
  - Orden queda asignada al mecánico
  - Validación de permiso (quién puede iniciar)
- **Dependencias**: C-12 (órdenes PENDIENTE creables), C-04 (RBAC MECANICO)
- **Governance**: ALTO — transición de estado crítica
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — flujo iniciar orden
  - `knowledge-base/05_reglas_de_negocio.md` — RN-11

### [C-14] mod-ordenes-TERMINAR
- **Estado**: `[ ]` pendiente
- **Scope**:
  - PATCH `/orders/{id}/terminar`
  - Solo MECANICO asignado o ADMIN
  - Orden debe estar EN_REPARACION
  - **Validación stock**: ¿hay suficiente stock para cada ítem?
  - **SI hay stock**: Descuenta stock de cada repuesto ítem, deja movimiento por ítem en historial_stock, deja línea de historial en la orden, actualiza estado
  - **SI no hay stock**: Nada queda escrito (transacción rollback), orden permanece EN_REPARACION
  - RN-09 crítica: stock o nada
- **Dependencies**: C-13 (órdenes EN_REPARACION), C-10 (repuestos stock), C-11 (items)
- **Governance**: CRITICO — RN-09 es "si falta stock, nada queda escrito", es el cambio más riesgoso
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — flujo terminar orden (el más complejo)
  - `knowledge-base/05_reglas_de_negocio.md` — RN-09 (la más importante)

### [C-15] mod-ordenes-CANCELAR
- **Estado**: `[ ]` pendiente
- **Scope**:
  - PATCH `/orders/{id}/cancelar`
  - Quién puede: el propio cliente, un administrador, o un mecánico asignado
  - La orden debe estar en estado PENDIENTE
  - Si no es PENDIENTE → 409, si no tiene permiso → 403
  - Cambia estado a CANCELADA, libera recursos si aplica
- **Dependencias**: C-12 (órdenes PENDIENTE), C-04 (RBAC)
- **Governance**: MEDIO — cancelación, importante pero no crítico como el flow de terminar
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — flow cancelar orden
  - `knowledge-base/05_reglas_de_negocio.md` — RN-10

---

## FASE 6 — Reportes y Administración

### [C-16] historial-precios
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelo `historial_precios` con repuesto_id FK, precio_anterior, precio_nuevo CHECK (>0), cambio_tipo (ENUM: SISTEMA, MANUAL), motivo TEXT, usuario_id FK, fecha DEFAULT NOW()
  - Cada cambio de precio deja historial (RN-13: sin cambio, sin línea)
  - Evento SISTEMA para cambios automáticos
  - Query de historial por repuesto
- **Dependencias**: C-10 (repuestos), C-01 (configuración), C-03 (auth para quién registra)
- **Governance**: MEDIO — histórico, no bloquea funcionalidad principal
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — modelo historial_precios
  - `knowledge-base/05_reglas_de_negocio.md` — RN-13

### [C-17] mod-reportes
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Endpoints de lista paginada con estructura `{items, total, page, size, pages}`
  - `page` desde 1, `size` 1..100 default 20
  - Página fuera de rango → 422
  - Cero resultados → página vacía con `items: []` y `total: 0`
  - Búsqueda con parámetros ligados (nunca concatenación) - RN-15
  - El `total` cuenta con los mismos filtros que la página de items - RN-19
  - Endpoints: reportes de órdenes, repuestos por stock bajo, estadísticas de mecánicos
- **Dependencias**: C-12 (órdenes), C-14 (terminar órdenes), C-16 (historial precios)
- **Governance**: BAJO — reports, útiles pero no críticos para el negocio
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — estructura paginación
  - `knowledge-base/05_reglas_de_negocio.md` — RN-18, RN-19

---

## FASE 7 — Administración y Finalización

### [C-18] admin-dashboard
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Endpoints estadísticas agregadas por rol
  - Órdenes por estado (PENDIENTE, EN_REPARACION, COMPLETADA, CANCELADA)
  - Repuestos stock bajo (por debajo de stock_minimo)
  - Usuarios activos y roles distribution
  - Ventas totales (suma total de órdenes completadas)
  - Solo ADMIN acceso
- **Dependencies**: C-14 (terminar órdenes), C-17 (reportes), C-04 (RBAC ADMIN)
- **Governance**: MEDIO — dashboard admin, vista consolidada
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — sección frontend y convenciones
  - `knowledge-base/07_flujos_principales.md` — estadísticas y reportes

### [C-19] refactor-ui
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Consistencia visual en formularios de login, registro, órdenes
  - Validaciones de UI alineadas con mensajes de error backend
  - Estilo en tabs de navegación (health, usuarios, clientes, repuestos, ordenes)
  - Responsive design para vistas de listado y detalle
  - Componente de rate limiting warning (mostrar Retry-After)
- **Dependencies**: C-18 (admin dashboard listo), C-03 (auth UI)
- **Governance**: BAJO — visual, último paso
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — sección frontend y convenciones
  - `knowledge-base/03_actores_y_roles.md` — exenciones de ruta y UI

---

## GATE de paralelismo detallado

GATE 0: Fundación completada (C-01 ✓)
  → C-02 core-models                    [Agente A - Backend Core]
  → C-03 auth-jwt                       [Agente B - Auth Specialist]  
  → C-04 usuarios-rbac                  [Agente C - Security]

GATE 1: Modelos core y auth listos
  → C-05 clientes-vehiculos             [Agente A]
  → C-06 repuestos-catalogo             [Agente B]
  → C-07 mod-usuarios                    [Agente C]

GATE 2: ← FORK Múltiples ramas
  → C-08 mod-clientes                   [Agente A]
  → C-09 mod-vehiculos                  [Agente B]
  → C-10 mod-repuestos                  [Agente C]

GATE 3: ← FORK Múltiples ramas
  → C-11 mod-items                      [Agente A]
  → C-12 mod-ordenes-PENDIENTE          [Agente B]
  → C-13 mod-ordenes-INICIO             [Agente C — si C-12 ✓]

GATE 4: Flujo de órdenes consolidado
  → C-14 mod-ordenes-TERMINAR           [Agente A — si C-13 ✓]
  → C-15 mod-ordenes-CANCELAR           [Agente B — si C-12 ✓]

GATE 5: Historial y reports
  → C-16 historial-precios              [Agente A]
  → C-17 mod-reportes                   [Agente B]

GATE 6: Administración
  → C-18 admin-dashboard                [Agente A]
  → C-19 refactor-ui                    [Agente B — si C-18 ✓]

GATE 7: Finalización total
  → C-20 seed-data-final                [Agente A — si C-16, C-17 ✓]

---

## CHANGES.md generado

✅ `CHANGES.md` creado en la raíz con **20 changes** organizados en **7 fases**.

**Camino crítico**: 9 changes (C-01 → C-03 → C-04 → C-05 → C-09 → C-12 → C-14 → C-16 → C-20)

**Gates de paralelismo**: 7 gates con asignaciones de agentes

**Primer change recomendado**: `C-01` (foundation-setup)

Para arrancar: `/opsx:propose C-01-foundation-setup`