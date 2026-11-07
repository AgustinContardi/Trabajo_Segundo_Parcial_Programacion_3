# Proposal — C-16 venta-transaccional

## Why

La API ya permite listar y consultar ventas (C-10) y autorizar por rol vigente (C-13, C-14), pero no existe forma de registrar una venta nueva. Sin `POST /ventas`, el circuito de ventas queda incompleto: no hay forma de cobrar, descontar stock ni dejar el movimiento de sólo agregado que certifica el invariante `stock = SUM(movimiento_stock.cantidad)`. `RN-10` es la regla más riesgosa del parcial: cuatro clases de escritura en una sola transacción, y un descuento parcial deja el invariante roto y hace fallar C-10, C-11 y C-12 a la vez.

## What Changes

- Agregar `POST /ventas` en el grupo protegido de `ventas`, con `requiere_rol('VENDEDOR','ADMIN')` → **201**.
- `VentaCreate` acepta **sólo** `cliente_id` y `renglones: [{libro_id, cantidad}]`, `extra="forbid"`: `precio`, `total` o `fecha` dan **422**; cero renglones o `libro_id` repetido dan **422**.
- Orden de verificación (CV-08): 1) cliente existente (409) → 2) libros existentes y vigentes (`borrado_en IS NULL`, 409) → 3) stock suficiente por renglón (409) → 4) `total = Σ(cantidad × precio_unitario)` calculado por el servidor → 5) copia de `precio_unitario` en cada renglón → 6) descuento de stock con el punto único de C-08 (`aplicar_movimiento`), un movimiento negativo por renglón con `usuario_id` del vendedor.
- Un solo `async with uow`: cliente → libros → stock → venta → renglones → movimientos. Si un libro no alcanza, **no queda ninguna escritura** (ni venta, ni renglones, ni descuentos, ni movimientos): la garantía es el rollback del `__aexit__`, no el chequeo previo.
- `requiere_rol('VENDEDOR','ADMIN')`: un CLIENTE → **403**; sin sesión → **401**.
- `BackgroundTasks`: tras el commit, `add_task(avisar_comprobante, venta.id)` con `await asyncio.sleep(0.5)` y un log visible con el arranque normal de uvicorn. No emite token nuevo ni rota la cookie.

## Capabilities

### New Capabilities

- `venta-transaccional`: registro atómico de una venta con sus renglones, descuento de stock y movimientos, en una sola transacción, con contrato de entrada cerrado y garantía de rollback ante falta de stock.

### Modified Capabilities

- `ventas` (espec global `openspec/specs/ventas/spec.md`): se añade la operación de escritura `POST /ventas` al módulo que hasta ahora sólo tenía lecturas (`GET /ventas/`, `GET /ventas/{id}`, `GET /ventas/mis-ventas`). No se modifican los endpoints existentes.

## Impact

- Código nuevo/ampliado en `parcial/app/modules/ventas/`: `router.py` (agrega `POST /ventas`), `service.py` (agrega `registrar_venta`), `repository.py` (agrega `RenglonVentaRepository` y método de obtención de varios libros), `unit_of_work.py` (agrega `libros` y `renglones` a `VentasUnitOfWork`), `schemas.py` (revisar `VentaCreate`: ya tiene `extra="forbid"` y `min_length=1`; queda pendiente el rechazo de `libro_id` repetido a nivel de servicio).
- Reutiliza `parcial/app/modules/libros/repository.py` (`LibroRepository`, `aplicar_movimiento` — el punto único de C-08) y `parcial/app/modules/libros/models.py` (`Libro`, `MovimientoStock`).
- Reutiliza `parcial/app/modules/clientes/repository.py` (`ClienteRepository.get_by_id`).
- Reutiliza `parcial/app/core/dependencies.py` (`requiere_rol`, `get_sesion_actual`), `parcial/app/core/errors.py` (`traducir_integrity_error`) y `parcial/app/core/unit_of_work.py` (`UnitOfWork`).
- **No requiere migraciones**: el esquema ya tiene `venta`, `renglon_venta`, `libro`, `cliente`, `movimiento_stock` y las FKs con sus índices.
- Pruebas nuevas en `parcial/tests/` (TDD estricto) y evidencia manual en `parcial/test/ventas.http` (casos C-10, C-11, C-12 y el ítem de `BackgroundTasks`).
- Habilita C-17 (seed) y C-18/C-19 (casos `.http` y suite pytest); no toca `despliegue/`.
- Dependencias ya cumplidas: C-08 (punto único de stock), C-10 (lecturas de ventas), C-13 (autorización por rol).
