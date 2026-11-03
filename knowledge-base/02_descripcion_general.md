# Descripción General

## Stack Tecnológico

- **Lenguaje**: Python 3.11+
- **Framework**: FastAPI (API asíncrona)
- **Base de Datos**: PostgreSQL con motor async
- **Migraciones**: Alembic
- **Autenticación**: bcrypt para contraseñas, JWT con cookies HttpOnly
- **Testing**: httpx TestClient para tests de endpoint, pytest para tests unitarios/integración
- **Validación**: Pydantic models con `extra="forbid"` en schemas de operación

## Arquitectura General

El sistema sigue una arquitectura de capas separadas por módulos:

```
app/
├── main.py          # Entry point con lifespan
├── core/            # Configuración central (database, security, dependencies)
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   └── dependencies.py
├── modules/         # Módulos por dominio (módulo salud, usuarios, clientes, repuestos, ordenes)
│   ├── router.py      # Endpoints HTTP
│   ├── service.py     # Lógica de negocio
│   ├── repository.py  # Acceso a datos
│   ├── unit_of_work.py # Pattern UoW
│   ├── paginacion.py  # Paginación configurada
│   └── ...            # Otros archivos por necesidad
└── seed.py          # Carga de datos iniciales
```

## Integraciones Externas

- **PostgreSQL**: Base de datos relacional principal
- **bcrypt**: Hash de contraseñas (rounds configurables desde Settings)
- **HTTP Client**: httpx para tests y llamadas HTTP externas

## Estructura de Directorios Clave

- `app/modules/{health,usuarios,clientes,repuestos,ordenes}/` - Cada módulo tiene sus 6 capas obligatorias
- `migrations/` - Gestión de esquema con Alembic
- `test/` - Archivos `.http` para testing manual/integration
- `tests/` - Tests pytest completos