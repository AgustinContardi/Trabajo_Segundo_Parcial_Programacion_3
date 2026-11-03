# Arquitectura Propuesta

## Patrones Arquitectónicos

### Patrones Aplicados

1. **Repository Pattern**: Cada módulo tiene su propio repositorio (`BaseRepository[T]` y `SoftDeleteRepository[T]`) que encapsula el acceso a datos. El repositorio conoce su clase de modelo y maneja toda la precarga relacionada.

2. **Unit of Work Pattern**: El `UnitOfWorkBase` confirma (`commit`) o revierte (`rollback`) en `__aexit__` y **no cierra** la sesión. El router construye el UoW; el servicio lo abre. Ningún servicio lo construye directamente.

3. **Dependency Injection (FastAPI)**: Las dependencias se construyen en `app/core/dependencies.py` y se inyectan en los handlers. El `get_session` lee el `sessionmaker` de `app.state`, no de un global.

4. **Service Layer**: La lógica de negocio vive en `app/modules/{modulo}/service.py`, no en los handlers (routers). Las dependencias se usan como parámetros de las funciones del servicio.

5. **Triggers a Nivel de BD**: Reglas críticas (solo-agregado, CHECKs, índices parciales) están implementadas como triggers en PostgreSQL, no en la aplicación.

## Estructura de Directorios Propuesta

```
app/
├── main.py                          # Entry point con lifespan
├── core/                            # Configuración central
│   ├── config.py                    # Settings con todos los parámetros
│   ├── database.py                  # Motor async, sessionmaker, lifespan
│   ├── security.py                  # bcrypt, JWT, validación de token
│   └── dependencies.py              # Inyección de dependencias FastAPI
├── modules/                         # Módulos por dominio (módulos de la consigna)
│   ├── health/                      # Módulo salud (solo router.py)
│   │   └── router.py
│   ├── usuarios/                    # Módulo usuarios
│   │   ├── router.py                # Endpoints HTTP
│   │   ├── service.py               # Lógica de negocio
│   │   ├── repository.py            # Acceso a datos
│   │   ├── unit_of_work.py          # Pattern UoW
│   │   ├── paginacion.py            # Paginación configurada
│   │   └── ...                      # Otros según necesidad
│   ├── clientes/                    # Módulo clientes (misma estructura)
│   ├── repuestos/                   # Módulo repuestos e inventario
│   ├── ordenes/                     # Módulo órdenes de servicio
│   └── health/                      # Ya existe, router solo
└── seed.py                          # Carga de datos iniciales
```

## Seguridad

### HTTP Cookie Properties (acceso_token)
- `HttpOnly`: Nunca viaja en el body ni se lee de `Authorization`
- `SameSite=Lax`: Protección contra CSRF cross-site
- `Max-Age`: Tiempo de vida de la cookie
- `Secure`: Según entorno (solo HTTPS en producción)

### Token Never Travels
- El token **nunca** viaja en el body de las peticiones
- El token **nunca** se lee de `Authorization` header
- El token se envía automáticamente vía cookie

### Rate Limiting
- Login: 429 con `Retry-After` antes que verificación de credenciales (RN-20)
- `LOGIN_MAX_INTENTOS` y `LOGIN_VENTANA_SEG` configurables desde Settings
- Uso de `to_thread` + semáforo para operaciones costosas (RN-21)

### Autoprotección de ADMIN
- NUNCA permitir que el sistema quede sin administradores
- Restricción en la eliminación del último admin

## Variables de Entorno (Settings)

Los siguientes parámetros son obligatorios desde `Settings`:

| Parámetro | Descripción | Obligatorio |
|-----------|-------------|-------------|
| `POSTGRES_USER` | Usuario de base de datos | ✓ |
| `POSTGRES_PASSWORD` | Contraseña de base de datos | ✓ |
| `POSTGRES_DB` | Nombre de base de datos | ✓ |
| `POSTGRES_HOST` | Host de base de datos | ✓ |
| `POSTGRES_PORT` | Puerto de base de datos | ✓ |
| `JWT_SECRET` | Secreto para firma de JWT | ✓ **(sin default, si falta, app no arranca)** |
| `ACCESS_TOKEN_TTL_MIN` | TTL en minutos del token | ✓ |
| `BCRYPT_ROUNDS` | Rounds para hash bcrypt | ✓ |
| `BCRYPT_MAX_CONCURRENCY` | Concurrencia máxima para bcrypt | ✓ |
| `LOGIN_MAX_INTENTOS` | Máximo intentos de login | ✓ |
| `LOGIN_VENTANA_SEG` | Ventana de tiempo para rate limit | ✓ |
| `POOL_SIZE` | Tamaño del pool de conexiones | ✓ |

## Computed Fields

### `@computed_field` - URL con driver async
- Arma la URL de conexión a base de datos a partir de los componentes de Settings
- Ejemplo: `postgresql+asyncpg://user:pass@host:port/db`
- Se evalúa una sola vez al arranque y no se cambia durante el ciclo de vida de la aplicación

## Módulo Health

Estructura mínima:
- `router.py` único (sin service/repository completos)
- Endpoint `GET /health` o similar para checks del sistema
- Exento de gating de autorización (RN-06 exención)