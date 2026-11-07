# Tasks — C-16 venta-transaccional

## 1. Contract schema de entrada (`RN-09`, `RN-15`, `CHECKLIST §4`, `§8`)

- [ ] 1.1 **RED** — Escribir `parcial/tests/test_ventas_schemas.py` con los casos del contrato: `precio`/`total`/`fecha` dan `ValidationError` (`extra="forbid"`), cero renglones dan `ValidationError` (`min_length=1`), `libro_id` repetido dan error de servicio (422), `cantidad <= 0` dan `ValidationError` (`gt=0`), y `cliente_id` + `renglones` válidos se aceptan. Correr `python -m pytest tests/test_ventas_schemas.py -q` desde `parcial/` y confirmar que falla por la razón correcta (no por error de importación). **Rastrea:** RN-09, CHECKLIST §8.
- [ ] 1.2 **GREEN** — Confirmar que `VentaCreate` y `RenglonCreate` ya tienen `extra="forbid"` y `min_length=1`/`gt=0` en `parcial/app/modules/ventas/schemas.py`; si faltan, agregarlos. Volver a correr `python -m pytest tests/test_ventas_schemas.py -q` → verde. **Rastrea:** RN-09, CHECKLIST §8.
- [ ] 1.3 **Triangulación y refactor** — Agregar los casos límite que falten (renglones con un solo elemento, `cantidad` muy grande, cuerpo vacío, JSON malformado → 422) y refactorizar sin cambiar comportamiento. Verificar con `python -m pytest tests/test_ventas_schemas.py -q`. **Rastrea:** RN-15, CHECKLIST §9.

## 2. Repositorio y Unit of Work de ventas (`RN-10`, `RN-11`, `CV-01`, `CV-02`, `CV-03`)

- [ ] 2.1 Crear `RenglonVentaRepository(BaseRepository[RenglonVenta])` en `parcial/app/modules/ventas/repository.py`, usando sólo `flush()` heredado y sin `commit()`. Verificar con `grep -n "commit()" parcial/app/modules/ventas/repository.py` (sin resultados). **Rastrea:** RN-11, CV-02, CHECKLIST §7.
- [ ] 2.2 Agregar `libros: LibroRepository(session, Libro)` y `renglones: RenglonVentaRepository(session, RenglonVenta)` a `VentasUnitOfWork` en `parcial/app/modules/ventas/unit_of_work.py`, todos sobre la misma sesión. Verificar desde `parcial/` que los cuatro repositorios comparten `_session`. **Rastrea:** CV-01, CHECKLIST §7.
- [ ] 2.3 Agregar método de repositorio para obtener varios libros por ids (evitar N consultas) y/o usar `get_by_id` por libro. Verificar que la precarga (`selectinload`) sólo vive en `repository.py`. **Rastrea:** CV-03, CHECKLIST §7, §10 (C-15).

## 3. Servicio atómico de venta (TDD estricto: `RN-09`, `RN-10`, `RN-11`, `RN-13`, `CHECKLIST §7`, `§8`)

- [ ] 3.1 **RED** — Escribir `parcial/tests/test_ventas_service.py` con un UoW falso (registra `__aenter__`/`__aexit__` y las llamadas a `add`) y casos: cliente inexistente → 409; libro inexistente → 409; libro dado de baja → 409; stock insuficiente → 409; orden de escrituras `cliente → libros → stock → venta → renglones → movimientos`; un `IntegrityError` en cualquier escritura se traduce a 409 fuera del bloque y el UoW falso recibe la excepción (revierte). Correr `python -m pytest tests/test_ventas_service.py -q` y confirmar el fallo (función inexistente). **Rastrea:** RN-10, RN-11, CHECKLIST §7.
- [ ] 3.2 **GREEN** — Implementar `service.registrar_venta(uow, dto, actual)` con el único `async with uow`, el orden de escrituras fijado, la copia de `precio_unitario`, el `total = Σ(cantidad × precio)`, el descuento vía `uow.libros.aplicar_movimiento(..., cantidad=-cantidad, motivo='Venta', usuario_id=actual.id, venta_id=venta.id)` y el `except IntegrityError → traducir_integrity_error` **fuera** del bloque. Verificar con `python -m pytest tests/test_ventas_service.py -q` → verde. **Rastrea:** RN-09, RN-10, RN-11, CHECKLIST §7, §8.
- [ ] 3.3 **Triangulación y refactor** — Añadir escenarios de stock justo (stock == cantidad), un solo renglón, varios renglones del mismo libro (rechazado), y fallo en la última escritura (movimiento) para verificar rollback completo. Refactorizar sin cambiar comportamiento y verificar con `python -m pytest tests/test_ventas_service.py -q`. **Rastrea:** RN-10, CHECKLIST §7.

## 4. Endpoint `POST /ventas` y `BackgroundTasks` (`RN-09`, `RN-10`, `DD-13`, `CHECKLIST §8`, `§10`)

- [ ] 4.1 Agregar la ruta `POST /ventas` en `parcial/app/modules/ventas/router.py` con `response_model=VentaDetailRead`, `status_code=201`, recibiendo `VentaCreate`, `BackgroundTasks` y el UoW por `Depends(get_ventas_uow)`, y `actual` por `Depends(requiere_rol("VENDEDOR", "ADMIN"))`. Verificar desde `parcial/` que la ruta existe con el método, código y modelo esperados. **Rastrea:** RN-09, CHECKLIST §8.
- [ ] 4.2 Agregar `avisar_comprobante(venta_id)` con `await asyncio.sleep(0.5)` y un log visible (`logging.getLogger("libreria.avisos").warning`), y agenda `background_tasks.add_task(avisar_comprobante, venta.id)` tras el commit en el router. Verificar que el handler no tiene lógica de negocio (no hashea, no consulta, no abre ni cierra transacciones, no emite cookie). **Rastrea:** DD-13, CHECKLIST §8, §10 (Ítem BackgroundTasks).
- [ ] 4.3 Comprobar que `requiere_rol('VENDEDOR','ADMIN')` da 403 a un CLIENTE y 401 sin sesión (ya cubierto por `dependencies.py`; verificar con el router que la dependencia está aplicada). **Rastrea:** RN-04, CHECKLIST §6.

## 5. Integración con PostgreSQL real (`CHECKLIST §7`, `§8`, `§10`)

- [ ] 5.1 Alta válida: `POST /ventas` con cliente y libros válidos vía `httpx.AsyncClient` + `ASGITransport` → `201`, precios copiados, total calculado, stock bajado, un movimiento por renglón con `cantidad < 0`, `motivo='Venta'`, `usuario_id` del vendedor. Verificar además en SQL las filas de `venta`, `renglon_venta` y `movimiento_stock`. Correr `python -m pytest tests/test_ventas_api.py -q -k "alta_valida"`. **Rastrea:** RN-09, RN-10, RN-11, CHECKLIST §8, §10 (C-10).
- [ ] 5.2 Contrato en la API: `precio`/`total`/`fecha` → `422`; cero renglones → `422`; `libro_id` repetido → `422`; y en todos los casos `count(venta)`, `count(renglon_venta)` y `count(movimiento_stock)` no cambian. Correr `python -m pytest tests/test_ventas_api.py -q -k "contrato"`. **Rastrea:** RN-09, RN-15, CHECKLIST §8, §9.
- [ ] 5.3 Stock insuficiente: libro con stock menor que la cantidad → `409` y `count(venta)`, `count(renglon_venta)`, `count(movimiento_stock)` no crecen; el invariante `stock = SUM(movimiento_stock.cantidad)` da 0 filas. Correr `python -m pytest tests/test_ventas_api.py -q -k "stock_insuficiente"`. **Rastrea:** RN-10, RN-11, CHECKLIST §7, §8, §10 (C-11).
- [ ] 5.4 Cliente inexistente, libro inexistente y libro dado de baja → `409` en los tres, sin escrituras. Correr `python -m pytest tests/test_ventas_api.py -q -k "inexistente_o_baja"`. **Rastrea:** RN-10, RN-13, CHECKLIST §8, §10 (C-12).
- [ ] 5.5 CLIENTE → `403`; sin sesión → `401`. Correr `python -m pytest tests/test_ventas_api.py -q -k "rol_o_sesion"`. **Rastrea:** RN-04, CHECKLIST §6, §10 (C-06).
- [ ] 5.6 Aislamiento: cada prueba borra al final los datos que creó; correr la suite dos veces seguidas da el mismo resultado. Verificar con `python -m pytest tests/test_ventas_api.py -q` dos veces. **Rastrea:** CHECKLIST §10.

## 6. Evidencia manual y aceptación del change (`CHECKLIST §7`, `§8`, `§10`, §4)

- [ ] 6.1 Crear `parcial/test/ventas.http` con los casos C-10 (201 con dos renglones, precios copiados, total, stock, movimientos, aviso en el registro), C-11 (409 sin escrituras, invariante 0 filas) y C-12 (tres 409 sin escrituras), más el ítem de `BackgroundTasks` (log visible tras la respuesta), cada uno con el cuerpo esperado en un comentario y las consultas de control. **Rastrea:** CHECKLIST §8, §10.
- [ ] 6.2 Ejecutar el `.http` contra `uvicorn main:app` con PostgreSQL real y registrar la salida (códigos, cuerpos y resultados de las consultas) como evidencia de aceptación. **Rastrea:** CHECKLIST §10.
- [ ] 6.3 Correr la suite completa desde `parcial/` con `POSTGRES_*` apuntando a la base de prueba: `python -m pytest -q` → sin fallos y sin pruebas nuevas saltadas. **Rastrea:** CHECKLIST §10.
- [ ] 6.4 Revisar las reglas duras con `grep`: `grep -rn "commit()" parcial/app/modules/*/repository.py` (vacío), `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/ventas/service.py` (vacío), `grep -rn "selectinload" parcial/app/ | grep -v repository.py` (vacío). **Rastrea:** CV-01, CV-02, CV-03, CHECKLIST §0, §7.
- [ ] 6.5 Confirmar que el change no agrega migraciones: `alembic check` desde `parcial/` y `git status --short parcial/migrations` (sin versiones nuevas; siguen exactamente 4). **Rastrea:** CV-10, CHECKLIST §3.
- [ ] 6.6 Verificar el invariante de stock: `SELECT l.id FROM libro l LEFT JOIN movimiento_stock m ON m.libro_id=l.id GROUP BY l.id, l.stock HAVING l.stock <> COALESCE(SUM(m.cantidad),0);` → 0 filas tras cada venta. **Rastrea:** RN-11, CHECKLIST §4, §7.

## 7. Cierre del change

- [ ] 7.1 Archivar el change y marcar `C-16` como `[x]` en `CHANGES.md` según el flujo del proyecto. C-17 consume el seed y la venta transaccional; no duplicar datos.
