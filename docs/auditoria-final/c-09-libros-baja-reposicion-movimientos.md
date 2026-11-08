# Auditoría — C-09 libros-baja-reposicion-movimientos

- **Fecha**: 2026-11-08
- **Auditor**: subagente (solo lectura; sin pytest, sin seed, sin escrituras a la base)
- **Veredicto**: **PASS** — 15/15 ítems cumplidos, 1 WARN, 0 FAIL
- **Alcance**: `docs/CHECKLIST_ENTREGA.md` §8 (baja lógica, reposición, movimientos, re-alta, PATCH), §7 (punto único de stock, capas), §4 (invariante) y §10 C-13, contra `parcial/app/modules/libros/{router,service,repository,schemas}.py`, la base PostgreSQL real y el change archivado `openspec/changes/archive/2026-11-06-c-09-libros-baja-reposicion-movimientos/`.

## Método

- Inspección de `libros/{router,service,repository,schemas,models,unit_of_work}.py`, `app/core/repository.py` (`SoftDeleteRepository`), `app/core/errors.py` y `ventas/repository.py` (venta vieja).
- `psql` (solo SELECT) contra `127.0.0.1:5432`, db `libreria`.
- Evidencia registrada: `CHANGES.md` §[C-09], `tasks.md` (todas `[x]`), `design.md`, `specs/libros/spec.md`, `test/libros.http` (C-13.1…C-13.14), `test/EVIDENCIA.md` (corrida equivalente + pasada manual httpyac 25/25 OK).
- No se ejecutó pytest, seed.py, ninguna escritura, ni uvicorn.

## Resultado por ítem

| # | Ítem (CHECKLIST) | Resultado | Evidencia |
|---|---|---|---|
| 1 | §8 `POST /libros/{id}/reponer` → **200**, sube el stock y deja su movimiento | PASS | `service.reponer` → `aplicar_movimiento(obj, cantidad, "Reposición", usuario_id)` (punto único, `libro.stock += cantidad` + `flush()` en `repository.py`). Evidencia C-13.3: **200** `"stock":5` tras +2; pasada httpyac 25/25. |
| 2 | §8 `GET /libros/{id}/movimientos` → **200** con los movimientos del libro | PASS | `MovimientoStockRead` con `cantidad` firmada, `motivo`, `cuando`, `usuario_id`, `venta_id` nulo si no es venta; `LibroRepository.movimientos` ordena por `cuando, id`. Evidencia C-13.2: **200** `motivo:"Stock inicial"`, `cantidad:3`, `venta_id:null`. |
| 3 | §8 `DELETE /libros/{id}` baja lógica: **204**, escribe `borrado_en`, la fila **no** se borra | PASS | `dar_de_baja` usa `SoftDeleteRepository.soft_delete` (`borrado_en = now(timezone.utc)` + `flush()`), sin `delete()`. Evidencia C-13.5 **204**; C-13.14 control SQL: fila con `borrado_en` no nulo y stock intacto. |
| 4 | §8 el libro dado de baja desaparece de **todos** los listados y del detalle público | PASS | Filtro `borrado_en IS NULL` en `get_by_id` y `listado_stmt`. Evidencia C-13.6 (`total: 5`, id ausente) y C-13.7 (**404** «Libro no encontrado»). |
| 5 | §8 un libro dado de baja no se puede vender ni reponer → **409** | PASS | `reponer` usa `get_by_id_including_deleted` + chequeo `borrado_en` → **409** «El libro está dado de baja»; la venta lo rechaza en `ventas` (C-10/C-12). Evidencia C-13.11 y C-13.12, ambos **409** observados. |
| 6 | §8 dar de baja un libro ya dado de baja o inexistente → **404** | PASS | `get_by_id` filtra borrados → `None` → **404**; no es idempotente. Evidencia C-13.13 **404**. |
| 7 | §8 re-alta con el ISBN de un libro dado de baja → **201**; segundo **vigente** con ese ISBN → **409** | PASS | Índice único parcial `uq_libro_isbn_vigente (isbn) WHERE borrado_en IS NULL` en `models.py` y en la DB (sin `libro_isbn_key`); garantía de la base, no de una consulta previa. `errors.py` mapea el constraint → **409** «Ya existe un libro con ese ISBN». Evidencia C-13.9 **201** (id 7) y C-13.10 **409**. |
| 8 | §8 `PATCH /libros/{id}` sólo título y precio; mandar `stock` da **422** | PASS | `LibroUpdate` declara `titulo` y `precio` con `extra="forbid"`; `stock` → 422. Evidencia C-16.8 observado **422** `extra_forbidden`. |
| 9 | §8 `POST /libros` recibe `stock_inicial` (no `stock`) y deja el movimiento «Stock inicial» | PASS | `LibroCreate.stock_inicial` + `crear` → `aplicar_movimiento(..., "Stock inicial", usuario_id)`. Evidencia C-13.1 **201** `"stock":3` y C-13.2 movimiento «Stock inicial». |
| 10 | §8 la venta vieja sigue mostrando el título de un libro dado de baja | PASS | `VentaRepository.get_by_id` precarga `selectinload(RenglonVenta.libro)` **sin** filtrar `borrado_en` (CV-03: precarga sólo en `repository.py`). Evidencia C-13.8 **200** con `titulo:"Libro de baja y re-alta C-13"` en el renglón. |
| 11 | §4 invariante `libro.stock = SUM(movimiento_stock.cantidad)` | PASS | Query del checklist sobre la base actual → **0 filas** en desacuerdo; `test/EVIDENCIA.md` mide 0 violaciones tras cada venta/baja/reposición. |
| 12 | §7 el stock se escribe en un único punto, usado por alta, reposición y venta | PASS | `grep -rn "stock"`: la única escritura sobre un libro persistido es `libro.stock += cantidad` en `LibroRepository.aplicar_movimiento`; alta («Stock inicial»), reposición («Reposición») y venta («Venta») lo reusan. |
| 13 | §7 capas: router construye el UoW, servicio lo abre, repos sin `commit()` | PASS | `router.py` sólo `Depends(get_libros_uow)` + HTTP; `service.py` abre `async with uow`; `grep "AsyncSession\|UnitOfWork(" app/modules/libros/service.py` vacío; repositorio sólo `flush()`. |
| 14 | §10 **C-13** completo y corrido tras `python seed.py` | PASS | `test/libros.http` C-13.1…C-13.13 con `# Esperado:` + C-13.14 control SQL; `EVIDENCIA.md` registra corrida equivalente (status observado por bloque) y pasada manual httpyac **25/25 OK**. |
| 15 | Estado del seed canónico intacto | PASS | `psql`: libros 1…5 vigentes con stock **10/5/8/3/1**, 7 movimientos (5 «Stock inicial» + 2 «Venta»), invariante 0 filas. |

## WARN

- **Movimiento atribuido al primer usuario de la tabla, no al autenticado.** `reponer_libro` (y también `crear_libro`) reciben `_sesion: IdentidadActual` con `usuario`, pero llaman `service.reponer(uow, libro_id, data.cantidad)` **sin** pasar `usuario_actual`. El servicio cae al fallback `SELECT id FROM usuario LIMIT 1`, de modo que `movimiento_stock.usuario_id` queda asociado al primer usuario de la tabla, no al ADMIN que operó. Con el seed funciona (id 1 = admin, coincidente con el `"usuario_id":1` esperado de C-13.2), pero es frágil ante cualquier orden distinto y contradice D-2/D-7 («el cableado se completa en C-13 sin cambiar la firma»: quedó sin cablear). No viola ningún ítem del checklist (§8 no exige el usuario del movimiento), por eso es WARN y no FAIL. **Fix recomendado**: `await service.reponer(uow, libro_id, data.cantidad, usuario_actual=_sesion.usuario)` (ídem `crear`), que `_usuario_id` ya resuelve.

## Notas

- `GET /libros/{id}/movimientos` responde **404** para un libro dado de baja (`get_by_id` filtra borrados). El spec delta de C-09 lo exige explícitamente y el checklist §8 no lo contradice; consistente con el detalle público.
- `reponer` duplica la validación `cantidad <= 0` en el servicio (el schema `ReponerCreate.cantidad: int = Field(gt=0)` ya la garantiza en 422). Defensa inofensiva, no se penaliza.
- El orden de validación es el correcto: contrato 422 (schema) → 404 (inexistente) → 409 (dado de baja).
- Las tres rutas nuevas viven en `router_admin` con `requiere_rol("ADMIN")`, coherente con el diseño D-7 y con C-13 (que corre con cookie ADMIN). El montaje en `main.py` (grupo abierto antes que protegido) no genera colisión de rutas: `/{libro_id}` (público) no compite con `/{libro_id}/movimientos` ni `/{libro_id}/reponer`.

## Veredicto

**PASS** — el change C-09 cumple todos los ítems relevantes de §4, §7, §8 y §10 (C-13) del checklist, verificado por inspección de código, evidencia registrada (corrida equivalente + httpyac) y la base PostgreSQL real. Un solo WARN (usuario del movimiento vía fallback SQL en lugar del autenticado), sin impacto en la aceptación.
