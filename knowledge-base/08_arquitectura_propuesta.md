# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| **Capas estrictas** | `router → service → unit_of_work → repository → model` | Cada capa sabe lo suyo y nada más; la corrección del parcial mira exactamente eso |
| **Unit of Work** | `app/core/unit_of_work.py` + `<módulo>/unit_of_work.py` | Una operación de negocio = una transacción; un fallo en el medio no deja datos a medias |
| **Repository** | `BaseRepository[T]`, `SoftDeleteRepository[T]` | Aísla consultas y precarga; `flush()` sin `commit()` |
| **Dependency Injection** | `Depends` de FastAPI para sesión, UoW, usuario y roles | El router construye el UoW y lo pasa; nada global |
| **DTO / Schema separation** | `<módulo>/schemas.py` con `extra="forbid"` | El contrato no es la tabla: nadie manda `rol` ni `stock` |
| **Soft delete** | `libro.borrado_en` + repositorio especializado | Las ventas viejas siguen apuntando a la fila |
| **Append-only ledger** | `movimiento_stock` + disparador | El stock tiene una sola vía de escritura y una auditoría completa |
| **Fail-fast config** | `Settings` sin defaults para secretos | Si falta la clave de firma, la aplicación no arranca |
| **Lazy resource creation** | Motor y `sessionmaker` en el `lifespan`, en `app.state` | Un recurso creado al importar nace antes del bucle de eventos |
| **BackgroundTasks** | Aviso del comprobante al registrar una venta | Corre en el mismo proceso, después de la respuesta |

## Estructura de directorios

```
parcial/
├── main.py                        # app, lifespan y los DOS grupos de rutas
├── seed.py                        # deja la base en el estado inicial conocido
├── requirements.txt
├── env.example                    # sin punto inicial, sin secretos
├── alembic.ini                    # SIN sqlalchemy.url con credenciales
├── README.md                      # integrantes + puesta en marcha desde cero
├── app/
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings) + @computed_field de la URL
│   │   ├── database.py            # motor + sessionmaker (los crea el lifespan) + get_session
│   │   ├── security.py            # bcrypt fuera del bucle, emisión y verificación del JWT
│   │   ├── dependencies.py        # usuario actual, roles vigentes, control de cambio, requiere_rol
│   │   ├── repository.py          # BaseRepository[T] y SoftDeleteRepository[T]
│   │   ├── paginacion.py          # envoltorio {items,total,page,size,pages}
│   │   └── unit_of_work.py        # UnitOfWork base: commit/rollback en __aexit__
│   └── modules/
│       ├── health/                # SÓLO router.py
│       │   └── router.py          # /health/live y /health/ready
│       ├── usuarios/              # Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── repository.py
│       │   ├── unit_of_work.py
│       │   ├── service.py
│       │   └── router.py
│       ├── editoriales/           # ídem seis capas
│       ├── generos/
│       ├── autores/
│       ├── libros/                # Libro, LibroAutor, MovimientoStock
│       ├── clientes/              # Cliente, PerfilCliente
│       └── ventas/                # Venta, RenglonVenta
├── migrations/
│   ├── env.py
│   └── versions/
│       ├── 0001_… (TP cap 1-4)
│       ├── 0002_… (TP cap 1-4)
│       ├── 0003_…_acceso_y_stock.py     # AUTOGENERADA, leída y comentada
│       └── 0004_…_append_only.py        # A MANO: disparador de movimiento_stock
├── test/
│   ├── *.http                     # casos C-01…C-16, un archivo por módulo
│   └── solo_agregado.sql          # caso C-14
├── tests/                         # sólo pytest (CV-04 / RD-01)
└── evidencia/                     # C-15 (consultas) y C-14 (psql)
```

`despliegue/` es un **proyecto aparte** (el TP de los capítulos 1 a 4 tal como se entregó) y no forma
parte de esta estructura. Ver `11_despliegue_y_devops.md`.

### Asignación de entidades a módulos (obligatoria)

| Entidad | Módulo |
|---|---|
| `Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad` | `usuarios` |
| `Libro`, `LibroAutor`, **`MovimientoStock`** | `libros` |
| `Cliente`, `PerfilCliente` | `clientes` |
| `Venta`, `RenglonVenta` | `ventas` |
| `Editorial` | `editoriales` |
| `Genero` | `generos` |
| `Autor` | `autores` |

## Qué puede y qué no puede cada capa

| Capa | Puede | **No puede** |
|---|---|---|
| `router.py` | Declarar ruta, dependencias, códigos; **construir** el UoW con una dependencia; llamar al servicio; traducir excepciones a HTTP | Abrir el UoW (`async with`), tocar el repositorio, contener reglas de negocio |
| `service.py` | Abrir el UoW (`async with uow`), aplicar reglas, decidir 403/409, escribir `evento_seguridad` | **Construir** el UoW, recibir una `AsyncSession`, hacer `commit()` |
| `unit_of_work.py` | Componer los repositorios del módulo con **una** sesión; commit en `__aexit__`; rollback con excepción; **no cerrar** la sesión | Cerrar la sesión que no creó |
| `repository.py` | Consultar, precargar (`selectinload` **sólo acá**), `add`/`update` con `flush()` | `commit()`, `rollback()`, construir el UoW |
| `models.py` | Tablas, columnas, `CHECK`, `UNIQUE`, índices parciales (`postgresql_where`), relaciones en los dos extremos | Lógica de negocio |

### El Unit of Work

```python
class UnitOfWork:                       # app/core/unit_of_work.py
    def __init__(self, session): self._session = session
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None: await self._session.commit()
        else:                await self._session.rollback()
        # NO cierra la sesión: no la creó
```

```python
class VentasUnitOfWork(UnitOfWork):     # app/modules/ventas/unit_of_work.py
    def __init__(self, session):
        super().__init__(session)
        self.ventas   = VentaRepository(session, Venta)
        self.renglones= RenglonVentaRepository(session, RenglonVenta)
        self.libros   = LibroRepository(session, Libro)   # para el punto único de stock
        self.clientes = ClienteRepository(session, Cliente)
```

```python
# router.py — CONSTRUYE, no abre
@router.post("/ventas", status_code=201)
async def crear_venta(dto: VentaCreate, uow: VentasUnitOfWork = Depends(get_ventas_uow),
                      actual: Usuario = Depends(requiere_rol("VENDEDOR", "ADMIN"))):
    return await service.registrar_venta(uow, dto, actual)

# service.py — ABRE, no construye
async def registrar_venta(uow: VentasUnitOfWork, dto: VentaCreate, actual: Usuario):
    async with uow:          # ← única frontera de transacción
        ...
```

### Los dos repositorios

| Clase | Constructor | Métodos |
|---|---|---|
| `BaseRepository[T]` | `(session, model_class)` — los genéricos se borran en runtime | `get_by_id`, `get_all`, `count`, `add`, `update`, `delete` |
| `SoftDeleteRepository[T]` | hereda | lo de arriba + `get_by_id_including_deleted`, `soft_delete`; **filtra los dados de baja** por defecto |

`add` y `update` hacen **`flush()`**, nunca `commit()`: «ningún repositorio confirma». La precarga
(`selectinload`) se declara **adentro del método que la necesita**, no en el modelo.

## Configuración — `Settings` (pydantic-settings)

| Variable | Descripción | Default | Sensible |
|---|---|---|---|
| `POSTGRES_USER` | Usuario de la base | **ninguno** | N |
| `POSTGRES_PASSWORD` | Contraseña de la base | **ninguno** (la app no arranca sin ella) | **S** |
| `POSTGRES_DB` | Nombre de la base | **ninguno** | N |
| `POSTGRES_HOST` | Host | **ninguno** | N |
| `POSTGRES_PORT` | Puerto | **ninguno** | N |
| `JWT_SECRET` | Clave de firma del token | **ninguno** (la app no arranca sin ella) | **S** |
| `ACCESS_TOKEN_TTL_MIN` | Duración del token en minutos (1800 s en el ejemplo) | 30 (CV-09) | N |
| `BCRYPT_ROUNDS` | Costo de bcrypt | 12 (CV-09) | N |
| `BCRYPT_MAX_CONCURRENCY` | Tamaño del semáforo de bcrypt | `min(4, cores)` (CV-09) | N |
| `LOGIN_MAX_INTENTOS` | Umbral de RN-07 | **5** (consigna) | N |
| `LOGIN_VENTANA_SEG` | Ventana de RN-07 | **60** (consigna) | N |
| `POOL_SIZE` | Tamaño del pool del motor | 5 (CV-09) | N |
| `SQL_ECHO` | Escribe cada consulta en el registro | `false` | N |
| `COOKIE_SECURE` | `Secure` de la cookie | `true` en producción (SU-06) | N |

La dirección de la base **no** es una variable: se arma con un `@computed_field`:

```
postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}
```

**Por qué no hay default para `JWT_SECRET` ni para `POSTGRES_PASSWORD`:** la clave de firma es el
secreto más importante del sistema — quien la tenga fabrica un token válido para cualquier usuario.
Y una clave inventada al arrancar tampoco sirve: cambia en cada reinicio y, con dos procesos
atendiendo, cada uno rechaza los tokens del otro.

El repositorio incluye `env.example` con todas las variables y **ningún secreto**, y `.gitignore` con
`.env`.

## Seguridad

| Aspecto | Decisión |
|---|---|
| **Hash** | bcrypt con costo declarado en `Settings` (no fijo en el código: es un valor que se sube con los años) |
| **Bloqueo del bucle** | Toda llamada a bcrypt corre con `to_thread` + **semáforo** que limita cuántas corren a la vez |
| **Hash fuera de la transacción** | El hash se calcula **antes** de abrir el `async with`: adentro, la conexión quedaría tomada los ~300 ms que tarda bcrypt sin usar la base |
| **Límite de 72 bytes** | Todo campo que termina en bcrypt (registro, alta de personal, login, cambio) acepta **como máximo 72 bytes** → si no, **422** en lugar de 500. Son **bytes**, no caracteres: una «ñ» ocupa dos |
| **Token** | JWT firmado (`PyJWT`) con `sub`, `exp` y los roles vigentes al emitirlo (informativos) |
| **Transporte** | Sólo cookie `access_token` con `HttpOnly`, `SameSite=Lax`, `Max-Age` = duración del token, `Secure` configurable. **Nunca** en el cuerpo, **nunca** leído de `Authorization` |
| **Sesión** | Login tradicional: dura hasta que el token vence o se cierra sesión. Cambiar la contraseña **no** invalida sesiones abiertas ni emite token nuevo |
| **Autorización** | `requiere_rol` consulta `asignacion_rol` **en cada petición**, con la misma sesión del UoW |
| **Anti-enumeración** | Mismo cuerpo y mismo tiempo exista o no el correo (hash ficticio calculado en el lifespan) |
| **Rate limit** | Conteo sobre `intento_acceso` (5 fallos / 60 s / mismo email+IP) → 429 + `Retry-After` sin calcular hash |
| **Errores** | Mensajes propios; nunca texto de la base ni traza; ningún input inválido termina en 500 |
| **SQL** | Siempre parámetros ligados, nunca concatenación |
| **Auditoría** | `evento_seguridad` en la misma transacción del cambio (RN-16) |
| **Secretos en la imagen** | El `.dockerignore` excluye `.env`, `.venv`, `.git` y `__pycache__`; la configuración entra por `--env-file` al correr |

## Ciclo de vida (`main.py` + `lifespan`)

```
lifespan (arranque)
  ├─ Settings()
  ├─ engine = create_async_engine(url, pool_size=POOL_SIZE, echo=SQL_ECHO)
  ├─ app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
  ├─ app.state.hash_ficticio  = bcrypt(HASH_DUMMY)   ← UNA vez, para RN-08
  └─ yield
lifespan (apagado)
  └─ await engine.dispose()
```

`get_session` toma la fábrica de **`app.state`**, entrega **una sesión por petición** y la cierra al
terminar. Nada se crea al importar: un recurso construido al importar nace antes de que exista el
bucle de eventos, y el síntoma —«anda al levantar el servidor y falla en las pruebas, o al revés»— no
señala la causa.

## Sondas de salud

| Endpoint | Qué hace | Código |
|---|---|---|
| `GET /health/live` | No toca la base; sólo confirma que el proceso responde | 200 |
| `GET /health/ready` | `SELECT 1` | 200 · **503** si la base no contesta |

El proceso puede estar **vivo** y no estar **listo**, y reiniciarlo no arregla una base caída. Esa
distinción es la que usa el `HEALTHCHECK` de la imagen.

## `BackgroundTasks` — el aviso del comprobante

Al registrar una venta se agenda el aviso al cliente:

```python
background_tasks.add_task(avisar_comprobante, venta.id)
```

```python
async def avisar_comprobante(venta_id: int) -> None:
    await asyncio.sleep(0.5)                      # simula el envío
    logging.getLogger("libreria.avisos").warning(  # visible con el logging por defecto
        "Comprobante de la venta %s enviado al cliente", venta_id)
```

Características y límites (todos de la consigna):

- Corre **después de enviar la respuesta** y **sólo si la operación se confirmó**.
- **Mismo proceso**: si el proceso se reinicia, el aviso se pierde y nadie lo reintenta. Se acepta
  porque es simulado; el capítulo 8 (colas con Redis) lo resuelve.
- **Tiene que verse en la consola con el comando de arranque normal de uvicorn**: con el registro por
  defecto, el logger de un módulo propio sin configurar **no aparece**. Hay que emitir con un logger
  que llegue al handler de uvicorn (o configurarlo), no con `print` a medias.

## Migraciones

| # | Origen | Contenido |
|---|---|---|
| 1, 2 | TP cap 1-4 | Catálogo, clientes y ventas |
| **3** | `alembic revision --autogenerate` | Tablas de acceso (`usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`), `movimiento_stock`, `cliente.usuario_id` y `libro.borrado_en` + los dos índices únicos parciales |
| **4** | **A mano** | Función y disparador de sólo agregado sobre `movimiento_stock` (RN-12) |

Reglas:

- Cada migración nueva **se lee antes de aplicarla** y lleva un **comentario que lo diga**; si la
  versión autogenerada tiene un problema (un tipo mal inferido, un índice que no generó), se corrige a
  mano y el comentario lo explica.
- `alembic upgrade head` sobre base vacía → `alembic downgrade base` → `upgrade head` tienen que
  funcionar. La cuarta migración necesita un `downgrade` que **borre el disparador y la función**.
- `alembic.ini` no lleva credenciales: `migrations/env.py` lee de `Settings`.
- **Nunca `create_all`.**

## Errores y códigos

| Código | Cuándo |
|---|---|
| **201** | Alta exitosa |
| **204** | Baja lógica de un libro (sin cuerpo) |
| **200** | Todo lo demás que sale bien |
| **401** | Sin cookie, token inválido/vencido, usuario inexistente o inactivo |
| **403** | Autenticado sin el rol, con cambio de contraseña pendiente, o recurso ajeno |
| **404** | El recurso **de la ruta** no existe |
| **409** | Choca con lo guardado (unicidad, stock, baja lógica, autoprotección) |
| **422** | Cuerpo o parámetros que no cumplen el contrato (incluye `{id}` no entero, `size` fuera de rango, página inexistente, fecha sin zona) |

`IntegrityError` se traduce por constraint a un mensaje propio; nunca se propaga el texto de
PostgreSQL.

## Estrategia de pruebas

| Nivel | Herramienta | Dónde |
|---|---|---|
| Casos de la consigna | archivos `.http` (`REST Client`) | `test/*.http`, con la respuesta esperada en un comentario |
| Sólo agregado | `psql` | `test/solo_agregado.sql` (C-14) |
| Evidencia de N+1 | consola con `SQL_ECHO=true` | `parcial/evidencia/` (C-15) |
| Suite automatizada | pytest contra PostgreSQL real | `tests/` (RD-01) |
| Despliegue | `docker …` + `curl`/`.http` | `despliegue/evidencia/` (D-01…D-08) |

Los `.http` se corren **después** de `python seed.py`. Con la extensión REST Client, cada login se
nombra con `# @name` y los pedidos de esa sesión llevan `# @no-cookie-jar` y el encabezado
`Cookie: {{loginAdmin.response.headers.Set-Cookie}}`, para tener dos sesiones a la vez en el mismo
archivo (lo necesita C-07).
