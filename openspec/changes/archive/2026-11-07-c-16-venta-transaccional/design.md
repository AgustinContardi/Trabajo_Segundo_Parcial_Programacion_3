# Design — C-16 venta-transaccional

## Context

Ver `proposal.md` para la motivación y `specs/venta-transaccional/spec.md` para el contrato observable.

Estado actual relevante en `parcial/`:

- `app/modules/ventas/router.py` ya tiene `GET /ventas/mis-ventas`, `GET /ventas/` y `GET /ventas/{id}`. El router construye `VentasUnitOfWork` vía `Depends(get_ventas_uow)` y no abre el UoW (`CV-01`).
- `app/modules/ventas/schemas.py` ya tiene `VentaCreate` con `cliente_id`, `renglones: List[RenglonCreate] = Field(min_length=1)` y `extra="forbid"`; `RenglonCreate` con `libro_id`, `cantidad = Field(gt=0)` y `extra="forbid"`. Falta el rechazo de `libro_id` repetido (a nivel de servicio, 422).
- `app/modules/ventas/service.py` ya tiene `listar`, `obtener` y `mis_ventas`. Falta `registrar_venta`.
- `app/modules/ventas/unit_of_work.py` (`VentasUnitOfWork`) compone `ventas` + `clientes`. Falta agregar `libros` y `renglones`.
- `app/modules/ventas/repository.py` (`VentaRepository`) tiene `get_by_id`, `listar`, `ventas_de_cliente`. Falta agregar `RenglonVentaRepository` y un método para obtener varios libros por ids.
- `app/modules/libros/repository.py` (`LibroRepository`, `SoftDeleteRepository`) ya tiene `get_by_id` (filtra `borrado_en IS NULL`), `aplicar_movimiento(libro, cantidad, motivo, usuario_id, venta_id)` — el **punto único de escritura de stock** de C-08 — y `movimientos`.
- `app/modules/libros/models.py` ya tiene `Libro` y `MovimientoStock`.
- `app/modules/clientes/repository.py` (`ClienteRepository`) ya tiene `get_by_id` y `get_by_usuario_id`.
- `app/core/dependencies.py` ya tiene `requiere_rol('VENDEDOR','ADMIN')` (lee `asignacion_rol` vigente en cada petición, `RN-04`) y `get_sesion_actual`.
- `app/core/unit_of_work.py` (`UnitOfWork`) confirma en `__aexit__` sin excepción y revierte con excepción; no cierra la sesión.
- `app/core/errors.py` (`traducir_integrity_error`, `CONSTRAINTS`) traduce `IntegrityError` a 409/422 con mensaje propio (`RN-15`).
- El esquema ya tiene `venta`, `renglon_venta`, `libro`, `cliente`, `movimiento_stock` con sus FKs e índices. **No hay migraciones en este change.**

Restricciones de arquitectura que el diseño debe respetar: router construye el UoW y el servicio lo abre (`CV-01`); repositorios sólo `flush()` (`CV-02`); servicios reciben el UoW, nunca la sesión; `selectinload` sólo en `repository.py` (`CV-03`); sin lógica de negocio en el router; `timestamptz` para fechas; `NUMERIC`/`Decimal` para dinero; bcrypt fuera del event loop (no aplica directamente, pero el semáforo existe); no crear migraciones (exactamente 4 en `migrations/versions/`).

## Governance

**CRÍTICO.** `RN-10` es la regla más riesgosa del parcial: un descuento parcial deja el invariante roto y hace fallar C-10, C-11 y C-12 a la vez; además es el 16 % de repositorios/UoW. El usuario ya aprobó el alcance de C-16 en `CHANGES.md` (FASE 7). Este change no reabre el alcance ni pide una nueva aprobación de negocio. Cualquier desvío del contrato de la consigna queda registrado abajo como decisión de implementación, nunca como regla nueva.

## Goals / Non-Goals

**Goals:**

- Concentrar las cuatro clases de escritura de `RN-10` (`venta`, `renglon_venta`, `libro.stock`, `movimiento_stock`) en una única transacción, con el router como único constructor del UoW y el servicio como único que lo abre.
- Garantizar el rollback completo ante falta de stock: ninguna escritura queda si un libro no alcanza (la garantía es el `async with uow`, no el chequeo previo).
- Reutilizar el punto único de escritura de stock (`aplicar_movimiento`, C-08) para el descuento y su movimiento.
- Dejar el endpoint en el grupo protegido ya existente, sin tocar `main.py`.
- `VentaCreate` rechaza campos extra (`precio`, `total`, `fecha` → 422) con `extra="forbid"`.

**Non-Goals:**

- No crear migraciones, columnas, constraints ni reglas de negocio nuevas.
- No tocar `despliegue/` ni `parcial/migrations/`.
- No emitir token nuevo ni rotar la cookie tras la venta.
- No implementar bloqueo de concurrencia (DD-14: fuera de alcance).
- No agregar `PATCH /ventas/{id}` (RN-09: las ventas no se modifican).
- No escribir `stock` directamente (sólo vía `movimiento_stock`, RN-11/RN-12).

## Decisions

### 1. `VentasUnitOfWork` compuesto por `ventas`, `renglones`, `libros` y `clientes` sobre una sola sesión

Se agregan `libros: LibroRepository(session, Libro)` y `renglones: RenglonVentaRepository(session, RenglonVenta)` a `VentasUnitOfWork` en `app/modules/ventas/unit_of_work.py`, todos construidos con la **misma** `AsyncSession` que entrega `get_session`. Se expone `get_ventas_uow` (ya existente) como dependencia para el router.

Por qué no crear un UoW aparte: el patrón del proyecto es un UoW por operación de negocio que compone repositorios de varios módulos (el docstring de `app/core/unit_of_work.py` ya documenta `VentasUnitOfWork` con esta composición).

Alternativa descartada: importar `LibroRepository` dentro del servicio; eso rompería la capa (el servicio no conoce repositorios directamente, los usa a través del UoW).

### 2. Repositorio `RenglonVentaRepository` nuevo en `ventas/repository.py`

Se agrega `RenglonVentaRepository(BaseRepository[RenglonVenta])` con el `add()` heredado (sólo `flush()`). Vive en `app/modules/ventas/repository.py` junto a `VentaRepository`, porque `RenglonVenta` pertenece al módulo `ventas` (asignación de entidades a módulos, `08_arquitectura_propuesta.md`).

### 3. Orden de escrituras dentro del único `async with uow`

El servicio `registrar_venta(uow, dto, actual)` ejecuta, en este orden:

1. `cliente = await uow.clientes.get_by_id(dto.cliente_id)` → `None` → `HTTPException(409)`.
2. `libros = await uow.libros.get_by_ids([r.libro_id for r in dto.renglones])` → faltante → `HTTPException(409)`. (Nueva consulta de repositorio: trae todos los libros de un golpe para evitar N consultas.)
3. Para cada libro: `libro.borrado_en IS NOT NULL` → `HTTPException(409)`.
4. Para cada renglón: `libro.stock < dto.cantidad` → `HTTPException(409)`.
5. `venta = await uow.ventas.add(Venta(cliente_id=dto.cliente_id, total=Σ(cantidad × libro.precio)))` → `flush()` asigna `venta.id`.
6. Para cada renglón: `await uow.renglones.add(RenglonVenta(venta_id=venta.id, libro_id=..., cantidad=..., precio_unitario=libro.precio))` → `flush()`.
7. Para cada renglón: `await uow.libros.aplicar_movimiento(libro, -cantidad, 'Venta', actual.id, venta_id=venta.id)` → `flush()`.

El `except IntegrityError` va **fuera** del `async with`: si se atrapara adentro, `__aexit__` vería una salida normal y **confirmaría** las filas parciales. Al atrapar afuera, la excepción sale del bloque, `__aexit__` ejecuta `rollback()` y recién después se traduce.

Por qué el cliente va primero: es la validación más barata y el contrato pide 409 si no existe. Por qué los libros se traen de golpe: una consulta en lugar de N, y evita el N+1 en la lectura de stock y precio.

### 4. `VentaCreate` ya cumple el contrato; queda el duplicado de `libro_id`

`VentaCreate` tiene `extra="forbid"` (rechaza `precio`, `total`, `fecha` → 422) y `renglones` con `min_length=1` (cero renglones → 422) y `RenglonCreate.cantidad = Field(gt=0)` (cantidad <= 0 → 422). Falta el rechazo de `libro_id` repetido: el servicio detecta duplicados en memoria y responde `422` antes de cualquier escritura.

Decisión de implementación: validar duplicados en el servicio antes de abrir el UoW, con `extra="forbid"` ya aplicado por Pydantic.

### 5. Router sin lógica de negocio

Se agrega al router existente de `ventas`:

```python
@router.post("/", response_model=VentaDetailRead, status_code=201)
async def crear_venta(
    dto: VentaCreate,
    background_tasks: BackgroundTasks,
    uow: VentasUnitOfWork = Depends(get_ventas_uow),
    actual: IdentidadActual = Depends(requiere_rol("VENDEDOR", "ADMIN")),
):
    venta = await service.registrar_venta(uow, dto, actual)
    background_tasks.add_task(avisar_comprobante, venta.id)
    return _to_detail(venta)
```

El router sólo construye el UoW (por dependencia), delega la autorización a `requiere_rol`, llama al servicio y agenda el aviso tras el commit. No tiene lógica de negocio ni abre transacciones. `main.py` ya monta este router en el grupo protegido, así que **no cambia**.

`avisar_comprobante` se define en `service.py`:

```python
async def avisar_comprobante(venta_id: int) -> None:
    await asyncio.sleep(0.5)
    logging.getLogger("libreria.avisos").warning(
        "Comprobante de la venta %s enviado al cliente", venta_id
    )
```

### 6. Estrategia de atomicidad y rollback

Toda la escritura ocurre dentro de un único `async with uow`. Si cualquier paso lanza `HTTPException(409)` (falta de stock, cliente/libro inexistente, libro dado de baja), la excepción sale del bloque, `__aexit__` ejecuta `rollback()` y no queda ninguna fila: ni venta, ni renglones, ni descuentos de stock, ni movimientos. El chequeo de stock es una cortesía para devolver un 409 legible; la garantía última es el rollback (RN-10).

No se usa `commit()` en ningún repositorio ni en el servicio: sólo `flush()` a través de `BaseRepository.add()` y `aplicar_movimiento()`. La confirmación es exclusiva de `__aexit__` del UoW (CV-02).

### 7. Estrategia de `BackgroundTasks`

El aviso del comprobante se agenda con `FastAPI BackgroundTasks` **después** de que el router retorne (FastAPI ejecuta las tareas de fondo tras enviar la respuesta). Corre una vez y sólo si la operación se confirmó (`__aexit__` hizo commit). `await asyncio.sleep(0.5)` simula el envío y `logging.getLogger("libreria.avisos").warning(...)` escribe en el registro visible con el logging por defecto de uvicorn (DD-13, D-08).

No se emite token nuevo ni se rota la cookie: el aviso es independiente de la sesión de autenticación.

### 8. Estrategia de tests: TDD estricto (RED → GREEN → triangulación → refactor)

Cada requisito se cubre con una prueba antes de escribir el código que la hace pasar:

- **RED**: escribir la prueba que falla por la razón correcta (función inexistente, contrato ausente, comportamiento incorrecto).
- **GREEN**: implementar lo mínimo en `parcial/` para que la prueba pase.
- **Triangulación**: añadir casos límite (stock justo, un renglón, muchos renglones, libro al límite) y verificar que el comportamiento no cambia.
- **Refactor**: eliminar duplicación y clarar nombres sin cambiar comportamiento; volver a correr la suite.

Nivel de pruebas:

1. **Unitarias (sin PostgreSQL)**: schemas (`VentaCreate` rechaza extra, duplicado de `libro_id`, cero renglones), servicio con UoW falso (orden de escrituras, `except` fuera del bloque, rollback al lanzar excepción).
2. **Integración (PostgreSQL real, nunca SQLite)**: API con `httpx.AsyncClient` + `ASGITransport` sobre `main.app`; comparar **status + body**, no `model_dump()` (CV-12). Casos: 201 con precios copiados y total, 409 sin escrituras (invariante 0 filas), 409 de cliente/libro inexistente/dado de baja, 422 de contrato, 403 de CLIENTE, 401 sin sesión.
3. **Manual (evidencia)**: `parcial/test/ventas.http` con los casos C-10, C-11, C-12 y el ítem de `BackgroundTasks`, ejecutado tras `python seed.py` contra `uvicorn main:app`.

## Risks / Trade-offs

- [El chequeo de stock dentro de la transacción no protege contra concurrencia real (DD-14)] → Documentado, no parcheado. Dos ventas simultáneas del último ejemplar pueden leer el mismo stock.
- [Atrapar `IntegrityError` dentro del bloque confirmaría filas parciales] → El `except` vive fuera del `async with`; hay una prueba de servicio que verifica que el UoW recibe la excepción.
- [Un `IntegrityError` deja la sesión en estado inválido hasta el rollback] → No se ejecuta ninguna consulta tras el error; el `rollback()` del `__aexit__` es la única operación posterior.
- [El aviso del comprobante se pierde si el proceso se reinicia] → Aceptado (DD-13): el aviso es simulado; el capítulo 8 (colas con Redis) lo resuelve.
- [`venta.usuario_id` (vendedor) es SU-07/AB-02, abierto] → El modelo actual de `Venta` no declara `usuario_id`; el dato «registrada por» vive en `movimiento_stock.usuario_id`. Si la cátedra exige `venta.usuario_id`, se agrega la columna y se llena con `actual.id` sin cambiar el contrato ni las reglas.
- [El 409 de «libro dado de baja» vs «libro inexistente» no se distinguen con `get_by_id` de `SoftDeleteRepository`] → Ambos dan 409 para C-16; si se necesitan mensajes distintos, se usa `get_by_id_including_deleted` + chequeo de `borrado_en`.

## Migration Plan

Sin migraciones de base ni cambios de configuración: las tablas, constraints, `Settings` y `lifespan` ya existen. El despliegue consiste en agregar el schema, los repositorios, el UoW, el servicio y la ruta, y reiniciar la aplicación. Rollback: retirar la ruta `POST /ventas` y las piezas nuevas; los datos ya registrados quedan válidos (venta + renglones + movimientos) porque se escribieron en una transacción confirmada. No se toca `parcial/migrations/` (siguen exactamente 4 versiones).

## Open Questions

- `AB-02` / `SU-07`: ¿`venta` guarda columna `usuario_id` (vendedor) o el dato «registrada por» vive sólo en `movimiento_stock.usuario_id`? Bloquea el detalle de venta y el seed, pero no el contrato de `POST /ventas` (el `usuario_id` del movimiento sí va en `movimiento_stock.usuario_id = actual.id`).

## UI Mockups

- Design system mode: `off` (`pending_inputs.visual_design.mode` en `.active-orchestrator-state.json`; `Mode: off` en `design-system/README.md` si existiera).
- Decision: no (no UI)
- Fecha: 2026-11-07
- Motivo: API pura (sin interfaz); el change agrega un endpoint JSON y no produce pantallas, componentes ni estilos. Política del proyecto: `visual_design.mode = off`.
