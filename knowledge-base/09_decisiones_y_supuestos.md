# Decisiones y Supuestos

## Decisiones de Diseño Tomadas

### D-01: PostgreSQL obligatorio, SQLite prohibido
- **Decisión**: El sistema debe usarse siempre con PostgreSQL versión de la cátedra. No hay soporte para SQLite en ningún caso.
- **Motivo**: Cumplimiento estricto de la consigna, características de PostgreSQL necesarias (triggers, CHECKs parciales, tipos de dominio).

### D-02: Migraciones con Alembic, sin edición manual de credenciales
- **Decisión**: `alembic.ini` debe quedar sin `sqlalchemy.url` con credenciales hardcodeadas. El `migrations/env.py` debe leer las credenciales de `Settings` (variables de entorno).
- **Motivo**: Seguridad - ninguna credencial en código fuente ni archivos de config visibles. Cumplimiento de RN-11 y política de seguridad.

### D-03: Patrón Unit of Work con confirmación en `__aexit__`
- **Decisión**: El `UnitOfWorkBase` confirma (`commit`) o revierte (`rollback`) en `__aexit__` y **no cierra** la sesión. El router construye el UoW; el servicio lo abre; ningún servicio lo construye.
- **Motivo**: Garantiza que la sesión siempre sea confirmada o revertida, aunque ocurra una excepción. Evita fugas de conexiones.

### D-04: Schemas Pydantic con `extra="forbid"`
- **Decisión**: Cada schema por operación (`Create`, `Update`, `Read`) debe tener `extra="forbid"` para rechazar campos de más con código 422.
- **Motivo**: Seguridad y validación estricta. Cualquier campo no definido en el schema es rechazado automáticamente.

### D-05: Triggers `solo-agregado` a nivel de base de datos
- **Decisión**: Triggers a nivel de BD bloquean UPDATE y DELETE en `users`, `vehicles`, `repuestos` para registros "solo-agregados". Implementación puramente en PostgreSQL.
- **Motivo**: Integridad de datos garantizada a nivel de base de datos, independientemente de la aplicación que la use. No depende de recordar implementar validaciones en el código.

### D-06: Arquitectura de módulos independientes
- **Decisión**: Cada módulo (health, usuarios, clientes, repuestos, ordenes) tiene sus 6 capas propias: router, service, repository, unit_of_work, paginación, y archivos adicionales según necesidad.
- **Motivo**: Separación de responsabilidades, facilitación de tests y escalabilidad. Cada equipo o desarrollador puede trabajar en módulos independientes.

### D-07: Lifespan sobre startup/shutdown events
- **Decisión**: Usar `lifespan` en FastAPI en lugar de `on_event("startup")` / `on_event("shutdown")`.
- **Motivo**: FastAPI recomienda `lifespan` para la versión 0.+ y permite mejor gestión de recursos asíncronos.

### D-08: JWT en cookie HttpOnly, nunca en body/header
- **Decisión**: El token JWT se almacena en una cookie HttpOnly y nunca se envía en el body de las peticiones ni se lee de `Authorization` header.
- **Motivo**: Seguridad mejorada - previene XSS (token no accesible via JavaScript) y CSRF (mismoSite=Lax).

### D-09: Paginación estandarizada `{items,total,page,size,pages}`
- **Decisión**: Todos los endpoints de listado deben retornar la estructura estandarizada de paginación.
- **Motivo**: Consumo consistente por parte del frontend, documentación clara, facílite caching.

### D-10: Rate limiting antes que verificación en login
- **Decisión**: En el endpoint de login, aplicar rate limit (429 con Retry-After) **antes** que verificar credenciales.
- **Motivo**: Previene ataques de fuerza bruta y enumeración de cuentas. El mensaje y tiempo de respuesta deben ser idénticos tanto si el correo existe como si no (RN-20).

### D-11: Estructura de respuesta HTTP codificada
- **Decisión**: Orden de códigos de respuesta: 404 → 403 → 409 → 422, en ese orden.
- **Motivo**: Jerarquía clara de errores: primero "no encontrado", luego "sin permiso", luego "conflicto", finalmente "invalid input".

### D-12: Seed idempotente después de migraciones
- **Decisión**: `seed.py` debe ejecutarse después de `alembic upgrade head` sin error, y debe ser idempotente (puede correrse múltiples veces sin efectos secundarios).
- **Motivo**: Facilita deploys múltiples y reparación de bases de datos.

### D-13: Sin `.env` en el repositorio
- **Decisión**: El repositorio nunca debe contener archivo `.env`. Las variables de entorno vienen del entorno de despliegue.
- **Motivo**: Seguridad y buenas prácticas de despliegue.

### D-14: `get_session` lee de `app.state`, no de global
- **Decisión**: La dependencia `get_session` debe leer el `sessionmaker` de `app.state` durante el lifespan, no usar un global de módulo.
- **Motivo**: Evita problemas de concurrencia y pruebas más fiables.

## Supuestos Inferidos

### S-01: Entorno de despliegue con PostgreSQL disponible
- **Supuesto**: El entorno donde se despliega el sistema tiene PostgreSQL accesible y la versión requerida por la cátedra.
- **Confianza**: Alta - es requisito de la materia.

### S-02: bcrypt rounds configurables pero dentro de un rango razonable
- **Supuesto**: Los `BCRYPT_ROUNDS` vienen configurados desde Settings y están en un rango que permite funcionamientoacceptable (no excesivamente altos para producción sin semáforo).
- **Confianza**: Alta - configurable, pero valores muy altos podrían impactar performance.

### S-03: El rate limiting se implementa a nivel de aplicación FastAPI
- **Supuesto**: El rate limiting no está a nivel de reverse proxy (NGINX/Traefik) sino en la propia aplicación FastAPI mediante middleware o dependencia.
- **Confianza**: Media - depende de la implementación específica.

### S-04: Los módulos de la consigna siguen el patrón de 6 capas
- **Supuesto**: Cada módulo tiene las 6 capas obligatorias: router, service, repository, unit_of_work, paginación, y al menos un archivo más según necesidad.
- **Confianza**: Alta - es la estructura impuesta por la consigna.

### S-05: Los desarrolladores conocen SQL básico pero usarán ORM/Patterns
- **Supuesto**: El equipo usará SQLAlchemy core/ORM con los patterns definidos (Repository, UoW) en lugar de queries SQL puros.
- **Confianza**: Alta - es la pauta del curso.

### S-06: Deployment en entorno único (no microservicios distribuidos)
- **Supuesto**: El sistema se despliega como una sola aplicación, no como microservicios con comunicación de red interna compleja.
- **Confianza**: Alta - es un TP de una materia, no un sistema enterprise distribuido.

### S-07: Un solo usuario por cliente (relación 1:1 obligatoria)
- **Supuesto**: La regla de negocio de `Usuario.cliente` uni-direccional y su inversa es estricta 1:1, nunca 1:N ni N:M en la práctica del TP.
- **Confianza**: Alta - definida en la consigna y modelo de datos.

### S-08: El trigger `solo-agregado` existe inicialmente en las migraciones
- **Supuesto**: Los triggers de solo-agregado se agregan manualmente después de `alembic upgrade head`, pero se da por granted que existirán para las operaciones de validación.
- **Confianza**: Media - requiere paso manual de migración que podría omitirse.

### S-09: Python 3.11+ con typing completo
- **Supuesto**: El proyecto usa Python 3.11 o superior con typing completo en los schemas Pydantic y funciones.
- **Confianza**: Alta - versión de curso típica.

### S-10: Tests contra PostgreSQL real, nunca SQLite
- **Supuesto**: Todos los tests deben correr contra PostgreSQL real, nunca contra SQLite como sustituto.
- **Confianza**: Alta - es un requisito explícito de la consigna (ver checklist item 24 y 124).