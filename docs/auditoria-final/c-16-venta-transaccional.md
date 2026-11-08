# Auditoría final — C-16 `venta-transaccional` + `c-16-fix-venta-transaccional`

- **Fecha:** 2026-11-08
- **Alcance:** `docs/CHECKLIST_ENTREGA.md` §8 (Ventas, stock y catálogo) y §9 (Errores y paginación), más los requisitos transversales del cambio (atomicidad, contrato estricto, orden de errores, `BackgroundTasks`, invariante de stock).
- **Cambios auditados:** `openspec/changes/archive/2026-11-07-c-16-venta-transaccional/` (original, con nota de reconciliación) y `openspec/changes/archive/2026-11-07-c-16-fix-venta-transaccional/` (correctivo).
- **Método:** lectura de código (`parcial/app/`), specs (`openspec/specs/venta-transaccional/spec.md`, `openspec/specs/ventas/spec.md`), evidencia registrada (`parcial/test/ventas_http_evidence.md`, `parcial/test/EVIDENCIA.md`, `parcial/test/ventas.http`, `parcial/test/evidencia/c-10-backgroundtasks.txt`), tests leídos sin ejecutar (`parcial/tests/test_ventas*.py`, `test_stock_invariante.py`, `test_errors_validation.py`), consultas `psql` **solo SELECT**, `alembic check`, y peticiones **solo lectura** in-process con `httpx.ASGITransport`. Ningún `POST /ventas`, `PATCH` o `DELETE` se ejecutó contra la DB compartida: los casos de escritura se verificaron por código + evidencia registrada. `pytest`, `seed.py` y `uvicorn` no se corrieron. Solo se escribió este informe.

---

## Veredicto global: **PASS** (33 PASS · 2 WARN · 0 FAIL)

Ningún ítem del alcance falla. Los dos WARN son (1) el defecto conocido `dd4a0e5e9cf7` (defaults `timestamptz` congelados, herencia de migración, no introducido por C-16 y mitigado en las columnas de venta/movimientos) y (2) la imposibilidad de re-ejecutar los casos 201/204 en esta auditoría (verificados por evidencia registrada, tests y código; no es un defecto).

---

## Tabla de verificación

### §8 — Ventas, stock y catálogo

| Ítem | Veredicto | Evidencia |
|---|---|---|
| No existe `PATCH /ventas/{id}` (RN-09) | **PASS** | `parcial/app/modules/ventas/router.py` sin `patch`; OpenAPI en vivo: `/ventas/` → GET,POST; `/ventas/{venta_id}` → GET únicamente (sin PATCH). Spec `ventas/spec.md` «No existe PATCH de ventas». |
| `POST /ventas` sólo acepta `cliente_id` + `renglones[{libro_id,cantidad}]`; `precio`/`total`/`fecha` → 422 | **PASS** | `ventas/schemas.py:14-26` (`VentaCreate`/`RenglonCreate` con `extra="forbid"`); tests `test_ventas_schemas.py::test_venta_create_rechaza_campos_extra`; evidencia `ventas_http_evidence.md` (422 `loc:["body","precio"]`); `EVIDENCIA.md` §5 C-16.3/16.4/16.5 observados 422. |
| ≥1 renglón y sin libros repetidos (RN-09) | **PASS** | `schemas.py:26` (`Field(min_length=1)`); duplicado → 422 en `service.py:116-119` («No se puede incluir el mismo libro dos veces en una venta»); `EVIDENCIA.md` C-16.1 (422 `too_short`) y C-16.2 (422). |
| Precio copiado del libro y total calculado en servidor (RN-09) | **PASS** | `service.py:121-138` (`total = Σ(cantidad × libro.precio)` con `Decimal`; `precio_unitario=libro.precio`); evidencia C-10: 201 con renglones `25000.00`/`22000.00`, total `47000.00`; seed: venta 1 `69000.00` (psql SELECT hoy). |
| Stock insuficiente → 409 sin ninguna escritura (RN-10) | **PASS** | `service.py:96-111` (stock agregado por libro, chequeo antes de escribir); un solo `async with uow` (`service.py:70`) con rollback en `__aexit__` (`core/unit_of_work.py:64-70`); `EVIDENCIA.md` C-11.1: 409 «Stock insuficiente para 'Bestiario'», conteos `venta/renglon/movimiento` 3·5·10 antes y después, invariante 0 filas. |
| Cliente inexistente, libro inexistente, libro de baja → 409 sin escrituras (RN-10, RN-13) | **PASS** | `service.py:72-94` (los tres 409 antes de cualquier `add`); evidencia `ventas_http_evidence.md` (los tres 409 con mensajes propios, conteos sin cambios) y `EVIDENCIA.md` C-12.1/12.2/12.4. |
| `POST /libros/{id}/reponer` 200 + movimiento; `GET /libros/{id}/movimientos` 200 (RN-11) | **PASS** | `libros/router.py:76-95` (`router_admin`); `libros/service.py:126-153` (`reponer` → `aplicar_movimiento(..., "Reposición", ...)`); `EVIDENCIA.md` C-13.3 (200 stock 5) y C-13.2 (movimiento «Stock inicial» listado). |
| `DELETE /libros/{id}` = baja lógica 204, sale de listados y detalle público (RN-13) | **PASS** | `libros/router.py:66-74` (status 204); `core/repository.py:104-111` (`soft_delete` escribe `borrado_en`); `EVIDENCIA.md` C-13.5 (204), C-13.6 (ausente del catálogo), C-13.7 (404 detalle). |
| Libro de baja no vendible ni reponible → 409 (RN-13) | **PASS** | `service.py:85-90` (baja → 409 en venta); `libros/service.py:133-137` (baja → 409 en reposición); `EVIDENCIA.md` C-12.4/C-13.11 («está dado de baja» 409) y C-13.12 (reponer 409). |
| Baja de un libro ya dado de baja o inexistente → 404 (RN-13) | **PASS** | `libros/service.py:116-120` (`dar_de_baja` → 404 si `get_by_id` None, que filtra dados de baja); `EVIDENCIA.md` C-13.13 (segundo DELETE 404). |
| Re-alta con ISBN de baja → 201; segundo vigente con ese ISBN → 409 (RN-01) | **PASS** | Constraint `uq_libro_isbn_vigente` (parcial, `WHERE borrado_en IS NULL`); `EVIDENCIA.md` C-13.9 (201 id 7) y C-13.10 (409 «Ya existe un libro con ese ISBN»). |
| `PATCH /libros/{id}` sólo título y precio; `stock` → 422; aplica solo lo enviado (RN-11) | **PASS** | `libros/schemas.py:59-63` (`LibroUpdate`: solo `titulo`/`precio`, `extra="forbid"`); `libros/service.py:88-97` (`model_dump(exclude_unset=True)`); `EVIDENCIA.md` C-16.7 (200, precio intacto) y C-16.8 (422 `extra_forbidden` en `stock`). |
| `POST /libros` recibe `stock_inicial` y deja movimiento «Stock inicial» (RN-11) | **PASS** | `libros/schemas.py:52-57` (`stock_inicial`, sin campo `stock`); `libros/service.py:37-60` (crea con `stock=0` y aplica movimiento «Stock inicial»); `EVIDENCIA.md` C-13.1/13.2. |
| Detalle de venta muestra título de libro dado de baja (RN-13) | **PASS** | `ventas/repository.py:30-45` (`selectinload(Venta.renglones).selectinload(RenglonVenta.libro)` sin filtro `borrado_en`); `EVIDENCIA.md` C-13.8 (200 con `titulo` del libro de baja). |
| Seed: venta 1 total 69000.00, movimientos y evento `SISTEMA`; invariante 0 filas | **PASS** | psql SELECT (esta auditoría): `total = 69000.00`; `movimiento_stock` = 7 filas; stocks 10/5/8/3/1; invariante 0 filas. Evento `SISTEMA` cubierto por `EVIDENCIA.md` §2 (1 fila `evento_seguridad`). |

### §9 — Errores y paginación

| Ítem | Veredicto | Evidencia |
|---|---|---|
| Listados devuelven `{items,total,page,size,pages}` | **PASS** | httpx en vivo: `GET /libros/` → 200 `keys: items,page,pages,size,total`; `GET /ventas/` (vendedor) → 200 mismo envoltorio; `core/paginacion.py:25-33`. |
| `page` desde 1; `size` 1..100 default 20 | **PASS** | `router.py` (`Query(1, ge=1)`, `Query(20, ge=1, le=100)`); httpx en vivo: sin `size` → `"size":20`; `size=500` → 422 (`less_than_equal`). |
| Página fuera de rango → 422 con mensaje propio | **PASS** | `core/paginacion.py:54-58`; httpx en vivo: `GET /libros/?size=2&page=4` → 422 «La página 4 no existe: hay 3». |
| `total` con los mismos filtros; cero resultados → una página vacía (`pages:1`) | **PASS** | `core/paginacion.py:49-52` (`count` sobre el subquery filtrado, `max(1, ceil)`); httpx en vivo: `titulo=ficc&size=1` → `total:1, pages:1`; `titulo=' OR '1'='1` → 200 `total:0, items:[]`. |
| Ningún error devuelve texto interno de la base ni trazas (RN-15) | **PASS** | `core/errors.py:102-146` (mensajes propios, `MENSAJE_ERROR_INTERNO`); handler global en `main.py:86-95`; evidencia `ventas_http_evidence.md` («Ninguna respuesta contiene nombres de tablas, columnas, constraints ni trazas»). |
| Ninguna entrada inválida termina en 500: id no entero, JSON malformado, NUL, size gigante (RN-15) | **PASS** | httpx en vivo: `GET /libros/abc` → 422 `int_parsing` sin consulta; `size=500` → 422; `SinNulMixin` (`errors.py:162-185`); `manejador_request_validation_error` nunca propaga; tests `test_ventas_schemas.py` (rango BIGINT/INT → `ValidationError`, nunca 500). |
| Búsqueda por título con parámetros ligados, sin distinguir mayúsculas; `' OR '1'='1` no rompe (RN-15) | **PASS** | `libros/repository.py:26-40` (`Libro.titulo.ilike(f"%{titulo}%")` — parámetro ligado, no concatenación SQL); httpx en vivo: 200, `total:0`, `items:[]`. |
| Schemas con `extra="forbid"`, PATCH con `exclude_unset`, códigos de la tabla de endpoints | **PASS** | `ventas/schemas.py` y `libros/schemas.py` (`extra="forbid"` en todos los de entrada); `libros/service.py:93` (`exclude_unset`); códigos: 201 alta, 204 baja, 404 recurso, 409 choque, 422 contrato (verificado en la tabla §8). |

### Requisitos transversales del brief (fuera del checklist literal)

| Requisito | Veredicto | Evidencia |
|---|---|---|
| Venta atómica: una UoW, venta + renglones + movimientos commit juntos; repos sin `commit()`, solo `flush()` | **PASS** | `service.py:70` único `async with uow` con todas las escrituras dentro (líneas 72-156); `except` fuera del bloque (líneas 157-170) para que `__aexit__` revierta; `core/unit_of_work.py:64-70` (commit solo en `__aexit__`); `core/repository.py` solo `flush()`. |
| Precios/movimientos en `Decimal`/`NUMERIC`, nunca `float` | **PASS** | `ventas/models.py:43` (`Numeric(12,2)`), `:72` (`Numeric(10,2)`); `schemas.py` `Decimal`; `service.py:121-124` suma con `Decimal`. |
| Stock SOLO vía `movimiento_stock` (`aplicar_movimiento`), motivo `Venta`, `usuario_id` del vendedor, append-only (RN-11/RN-12) | **PASS** | Único punto que toca `libro.stock`: `libros/repository.py:88-107` (`aplicar_movimiento`, suma y crea `MovimientoStock`); `service.py:141-148` (motivo `"Venta"`, `usuario_id=actual.usuario.id`, `venta_id`, cantidad negativa); trigger `movimiento_stock_no_modificable` presente (psql SELECT sobre `pg_proc`); `EVIDENCIA.md` C-14 (UPDATE/DELETE rechazados). |
| Orden de errores 401→403→409→422 | **PASS** | 401/403 en `core/dependencies.py` (`get_sesion_actual`, `requiere_rol`, `control_cambio_password`); en `service.py` cliente (409) → libros (409) → baja (409) → stock (409) → duplicado (422); evidencia `ventas_http_evidence.md` (duplicado + cliente inexistente → **409**); tests `test_ventas_crear_api.py::test_sin_sesion_401` / `test_rol_cliente_403`. En vivo: `GET /ventas/` sin cookie → 401; con cliente → 403 (sin escrituras). |
| 409 sin escrituras para los cuatro casos | **PASS** | `EVIDENCIA.md` C-11/C-12 (conteos idénticos antes/después); `ventas_http_evidence.md` (crecimiento +2/+3/+3 = solo las dos altas 201). |
| 422 en español para contrato estricto; IDs fuera de BIGINT → 422 nunca 500; cantidad ≥1 entero estricto | **PASS** | `schemas.py:9-12` (`strict=True, ge=1, le=BIGINT_MAX/INT_MAX`); `errors.py:120-146` (mensajes propios en español); evidencia: ID `10**30`/`2**63` → 422 «El valor supera el máximo permitido»; `cantidad:true`/`"1"`/`1.5` → 422 «Debe ser un número entero válido»; tests `test_ventas_schemas.py` parametrizados. |
| Sin 307 en `POST /ventas` (sin barra) | **PASS** | `router.py:125-126` (doble decorador `@router.post("", include_in_schema=False)` + `@router.post("/")`); `EVIDENCIA.md` C-10.2 (201 sin 307); captura `c-10-backgroundtasks.txt` (línea `POST /ventas HTTP/1.1" 201 Created`). |
| `BackgroundTasks` después del commit | **PASS** | `router.py:150-151` (`background_tasks.add_task(service.avisar_comprobante, venta.id)` tras `await service.registrar_venta(...)`); `service.py:173-177` (`asyncio.sleep(0.5)` + log); captura `c-10-backgroundtasks.txt`: la línea 201 precede a «Comprobante de la venta 2 enviado al cliente». |
| Invariante `libro.stock = SUM(movimiento_stock.cantidad)` en 0 | **PASS** | psql SELECT (esta auditoría): **0 filas**; `EVIDENCIA.md` (0 violaciones en todos los puntos medidos); `tests/test_stock_invariante.py` (incluye detección de escritura directa). |
| Concurrencia explícitamente fuera de alcance (RN-10/DD-14) | **PASS** | `archive/2026-11-07-c-16-venta-transaccional/design.md:43` («No implementar bloqueo de concurrencia (DD-14: fuera de alcance)») y `design.md:141` (riesgo documentado, no parcheado). |
| `alembic check` sin diferencias de esquema | **PASS** | Ejecutado en esta auditoría: «No new upgrade operations detected.» (exit 0). |

---

## Hallazgos

1. **WARN — Defecto conocido `dd4a0e5e9cf7` (defaults `timestamptz` congelados), de referencia.** El defecto es de la migración heredada 0003 (ver `CHANGES.md:523` y la migración `dd4a0e5e9cf7_acceso_y_stock.py`). En el alcance de C-16 no produce fallas nuevas: `Venta.fecha` usa `server_default="now()"` y el servicio la pasa explícita (`service.py:126-130`); `MovimientoStock.cuando` usa `server_default="now()"` (`libros/models.py:160-162`). No se convierte en FAIL; queda como referencia para cambios futuros que usen `default=` de Python en nuevas columnas `timestamptz`.
2. **WARN — Casos de escritura 201/204 no re-ejecutados en esta auditoría.** Por política anti-escritura sobre la DB compartida, `POST /ventas` (201/409/422), `POST/PATCH/DELETE /libros` y `POST /libros/{id}/reponer` no se ejecutaron en vivo. Se verificaron por código, por evidencia registrada con capturas y conteos SQL (`EVIDENCIA.md`, `ventas_http_evidence.md`, `c-10-backgroundtasks.txt`) y por tests leídos sin ejecutar (`test_ventas_api.py`, `test_ventas_crear_api.py`, `test_ventas_crear_service.py`, `test_ventas_service.py`). La evidencia de `EVIDENCIA.md` incluye pasada manual con httpyac 6.16.7 contra uvicorn + PostgreSQL 17.11 (20/20 en `ventas.http`), más fuerte que REST Client.
3. **INFO — `GET /ventas` (sin barra) responde 405 y `GET /libros`/`POST /libros` sin barra 307.** Comportamiento documentado en `EVIDENCIA.md` §8.3 como desvío conocido de Starlette (las rutas canónicas llevan barra). El ítem exigido por C-16 es solo `POST /ventas` sin barra → 201 sin 307, que SÍ se cumple (doble decorador). No es FAIL.
4. **INFO — `venta 1` del seed pertenece a Lucía, no a Ana.** En vivo, `GET /ventas/1` con `ana@example.com` da **403** — correcto (venta ajena; `EVIDENCIA.md` C-06.5). La venta de Ana en C-06.3 se crea durante el caso. No hay defecto.
5. **INFO — `GET /ventas/mis-ventas` de `vendedor@` (sin ficha) y de `ana@` (sin ventas en el seed) devuelven página vacía** `{items:[],total:0,pages:1}` — conforme a la spec (`ventas/spec.md`, «Usuario sin ficha de cliente»). Verificado en vivo en esta auditoría.

---

## Qué NO se pudo verificar independientemente

- **Ejecución de `pytest`:** prohibida por la auditoría (otros auditores comparten la DB). Los tests se leyeron sin ejecutar; su cobertura (contrato estricto, 401/403/409/422, atomicidad, rollback en la última escritura, invariante, traducción de `DataError`) es adecuada al alcance, y `tasks.md` de ambos cambios los declara en verde (325 pruebas según `CHANGES.md`).
- **Casos de escritura 201/204 en vivo** (hallazgo 2): verificados por evidencia registrada + código.
- **Pasada REST Client (GUI):** pendiente del usuario según `EVIDENCIA.md` §9; la pasada manual con httpyac cubre la ejecución real de los `.http`.
- **Concurrencia real de dos ventas simultáneas:** fuera de alcance por DD-14 (documentado).

---

## Fixes propuestos

1. **Defecto `dd4a0e5e9cf7` (WARN 1):** en un change futuro, normalizar cualquier columna `timestamptz` heredada que use `default=datetime.now` (sin zona ni servidor) a `server_default="now()"` vía migración nueva leída a mano; no toca C-16.
2. **`GET /ventas` sin barra (INFO 3):** si se desea simetría con `POST /ventas`, apilar también `@router.get("", include_in_schema=False)` sobre `listar_ventas`. Opcional: la consigna no lo exige (solo exige `POST /ventas` sin 307, que está cumplido).
3. **Sin acciones requeridas sobre C-16:** el cambio y su fix están completos y correctos respecto a §8 y §9; no se propone ninguna modificación de producción.
