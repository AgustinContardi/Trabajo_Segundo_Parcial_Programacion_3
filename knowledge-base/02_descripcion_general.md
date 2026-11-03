# Descripción General

## Stack tecnológico

Versiones mínimas exigidas por la consigna («Requisitos técnicos», p. 3-4):

| Capa | Tecnología | Versión mínima | Uso declarado |
|---|---|---|---|
| Lenguaje | Python | 3.12 | Lenguaje base (el contenedor usa `python:3.12-alpine`) |
| Framework web | FastAPI | 0.111 | Framework web; **todos** los handlers con `async def` |
| Modelos de tabla | SQLModel | 0.0.24 | Modelos de tabla |
| ORM | SQLAlchemy (asincrónico) | 2.0 | Motor, sesión y carga anticipada |
| Driver | asyncpg | 0.30 | Controlador asincrónico de PostgreSQL |
| Base de datos | PostgreSQL | 16 | Base de datos; en el despliegue, la que ya tiene el servidor |
| Migraciones | Alembic | 1.13 (plantilla asincrónica) | Migraciones |
| Configuración | pydantic-settings | 2.0 | Configuración leída del entorno |
| Hash | bcrypt | 4.0 | Hash de las contraseñas |
| Token | PyJWT | 2.8 | Token firmado |
| Servidor ASGI | uvicorn | el que instala `fastapi[standard]` | Servidor ASGI |
| Contenedor | Docker | 20.10 | Construir la imagen y correr el contenedor del TP cap 1-4 |

Decisiones de stack que la consigna fija y no son negociables:

- **Dinero en `NUMERIC` y `Decimal`, nunca `float`.**
- **Todas las fechas nuevas son `timestamptz`** (con zona horaria).
- **Driver `postgresql+asyncpg`**, con la URL armada desde variables sueltas.
- **Sin `create_all`**: el esquema se crea exclusivamente con Alembic.
- **bcrypt siempre fuera del bucle de eventos** (`to_thread` + semáforo).
- **El token viaja sólo en cookie**, nunca en el cuerpo ni leído de `Authorization`.

## Arquitectura general

Monolito modular, API-first, asincrónico de punta a punta, organizado **por módulo funcional** con
las mismas capas en todos los módulos:

```
Cliente HTTP
    │
    ▼
router.py            rutas HTTP: construye el Unit of Work, llama al servicio, traduce errores
    │
    ▼
service.py           reglas de negocio: abre el UoW con `async with`, nunca lo construye
    │
    ▼
unit_of_work.py      confirma al salir del bloque, revierte con excepción, no cierra la sesión
    │
    ▼
repository.py        consultas y precarga; `add`/`update` hacen flush(), nunca commit()
    │
    ▼
models.py            tablas, restricciones y relaciones (SQLModel)
    │
    ▼
PostgreSQL 16
```

Justificación de las decisiones de alto nivel:

- **Una sesión por petición y una sola para todo**: las dependencias de usuario actual y de
  verificación de rol reciben la **misma sesión** que el Unit of Work. Sin esa unificación, cada
  petición autenticada tomaría dos conexiones del pool.
- **El router construye, el servicio abre**: el router arma el UoW con una dependencia y se lo pasa
  al servicio **sin abrirlo**; el servicio lo abre con `async with`. Ningún servicio construye su
  UoW.
- **Las garantías viven en la base cuando la base puede darlas**: unicidad, claves foráneas,
  `CHECK`, índices únicos parciales y el disparador de sólo agregado. No se verifica con una consulta
  previa (RN-15 y requisito no funcional «Unicidad»).
- **Precarga declarada en el repositorio**, nunca carga perezosa: toda respuesta con datos de una
  relación los obtiene con carga anticipada declarada en el método del repositorio que la necesita.

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| PostgreSQL 16 (del VPS o local) | Persistencia; el despliegue usa la base que provee la cátedra | Conexión TCP con `asyncpg` |
| Docker Engine 20.10+ | Construir y correr la imagen del TP cap 1-4 | CLI (`docker build`, `docker run`) |
| Ninguna otra | No hay pasarela de pago, ni mail real, ni Redis, ni storage externo | — |

El «aviso del comprobante al cliente» **no** es una integración: es simulado con `BackgroundTasks`,
`await asyncio.sleep(0.5)` y un mensaje en el registro.

## API REST — resumen

El grupo **abierto** no pide sesión (el catálogo es público y `/auth` tiene que poder usarse para
iniciarla). El **protegido** lleva el control del cambio obligatorio de contraseña montado una sola
vez. Detalle completo y códigos en `02` (tabla siguiente) y en `06_funcionalidades.md`.

### Grupo abierto

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| GET | `/health/live` | Cualquiera | 200 |
| GET | `/health/ready` | Cualquiera | 200, 503 |
| POST | `/auth/registro` | Cualquiera | 201, 409, 422 |
| POST | `/auth/login` | Cualquiera | 200, 401, 422, 429 |
| POST | `/auth/logout` | Cualquiera | 200 |
| GET | `/auth/yo` | Autenticado | 200, 401 |
| POST | `/auth/cambiar-password` | Autenticado | 200, 401, 422 |
| GET | `/libros` (`page`, `size`, `titulo`, `genero_id`) | Cualquiera | 200, 422 |
| GET | `/libros/{id}` | Cualquiera | 200, 404, 422 |
| GET | `/editoriales`, `/generos` (`page`, `size`) | Cualquiera | 200, 422 |
| GET | `/editoriales/{id}/libros`, `/generos/{id}/libros`, `/autores/{id}/libros` | Cualquiera | 200, 404 |

### Grupo protegido

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| POST | `/usuarios` (alta de personal, con contraseña provisoria) | ADMIN | 201, 409, 422 |
| GET | `/usuarios/{id}/roles` | ADMIN | 200, 404 |
| POST | `/usuarios/{id}/roles` | ADMIN | 201, 404, 409, 422 |
| DELETE | `/usuarios/{id}/roles/{rol}` | ADMIN | 200, 404, 409 |
| GET | `/eventos` (`page`, `size`) | ADMIN | 200, 422 |
| POST | `/editoriales`, `/generos`, `/autores` | ADMIN | 201, 409, 422 |
| PATCH | `/editoriales/{id}`, `/autores/{id}` | ADMIN | 200, 404, 409, 422 |
| POST | `/libros` (con `autores` y `stock_inicial`) | ADMIN | 201, 409, 422 |
| PATCH | `/libros/{id}` (título y precio; el stock no) | ADMIN | 200, 404, 409, 422 |
| DELETE | `/libros/{id}` | ADMIN | 204, 404 |
| POST | `/libros/{id}/reponer` | ADMIN | 200, 404, 409, 422 |
| GET | `/libros/{id}/movimientos` | ADMIN | 200, 404 |
| POST | `/clientes` | VENDEDOR, ADMIN | 201, 409, 422 |
| GET, PATCH | `/clientes/{id}` (con su perfil) | VENDEDOR, ADMIN | 200, 404, 409, 422 |
| POST | `/clientes/{id}/perfil` | VENDEDOR, ADMIN | 201, 404, 409 |
| GET | `/clientes/{id}/ventas` | VENDEDOR, ADMIN | 200, 404 |
| POST | `/ventas` (con `renglones`) | VENDEDOR, ADMIN | 201, 409, 422 |
| GET | `/ventas` (`page`, `size`) | VENDEDOR, ADMIN | 200, 422 |
| GET | `/ventas/{id}` | El personal, o el cliente dueño | 200, 403, 404 |
| GET | `/mis-ventas` (`page`, `size`) | Autenticado | 200, 422 |

Toda ruta del grupo protegido responde además **401** sin sesión y **403** con el cambio de
contraseña pendiente.

Dos ausencias deliberadas: **no hay `PATCH /ventas/{id}`** (RN-09: las ventas no se modifican) y
**no hay `PATCH` que toque el stock** (RN-11: el stock sólo cambia por movimientos).

## Listados: envoltorio único

Todos los listados devuelven:

```json
{ "items": [], "total": 5, "page": 1, "size": 2, "pages": 3 }
```

- `page` empieza en **1**; `size` va de **1 a 100**, por defecto **20**.
- Pedir una página más allá de la última da **422** («La página 4 no existe: hay 3»).
- `total` cuenta con **los mismos filtros** que la página.
- Con cero resultados hay **una página, vacía** (`pages` = 1, `items` = []).
- La búsqueda de libros por título usa **parámetros ligados** y no distingue mayúsculas.

## Órdenes de magnitud

Un grupo de cátedra, una sola base PostgreSQL, decenas de usuarios y miles de ventas como techo
razonable; sin multi-tenant, sin colas, sin cache. La escala no es el punto del parcial: la
corrección mira capas, transacciones, restricciones y despliegue.
