# Auditoría — C-10 capas-ventas-lecturas

- **Fecha**: 2026-11-08
- **Auditor**: agente auditor (solo lectura; sin pytest, sin uvicorn, sin INSERT/UPDATE/DELETE;
  solo `SELECT` vía psql y peticiones HTTP de lectura vía `httpx.ASGITransport`; los logins de
  verificación fueron autorizados por el brief de auditoría y dejan solo filas de `intento_acceso`).
- **Método**: lectura de código (`router/service/repository/unit_of_work/schemas` de `ventas` y
  núcleo `core/`), greps de invariantes de capas, `SELECT` en PostgreSQL local y verificación
  runtime con `from main import app` + `httpx.ASGITransport` + cookie del login
  (`admin@example.com`, `vendedor@example.com`, `ana@example.com`).
- **Base verificada**: PostgreSQL local con estado del seed (venta 1: Lucía, 1×Rayuela + 2×Ficciones,
  total 69000.00; 5 libros vigentes, ninguno dado de baja; ana = cliente 3 con `usuario_id`).
- **Contexto de cierre**: C-10 archivado como `2026-11-06-c-10-capas-ventas-lecturas`; CHANGES.md
  `### [C-10]` en `[x]`. El cableado de autorización real (401/403) llegó con C-11/C-13.

## Veredicto

**FAIL** — 1 FAIL (ruta de `GET /mis-ventas`), 1 WARN menor de proceso. El resto PASS.

## Tabla por ítem

| Ítem (CHECKLIST_ENTREGA.md / specs C-10) | Resultado | Evidencia |
|---|---|---|
| §6 — `GET /ventas/{id}` **no** lleva `requiere_rol` | PASS | `router.py:105-112`: la ruta depende de `get_sesion_actual`, no de `requiere_rol`; `requiere_rol` solo aparece en `_solo_personal` (listado) y en `POST /ventas`. |
| §6 — detalle: personal 200, dueño 200, ajeno 403, inexistente 404 (decisión en el servicio, RN-14) | PASS | Runtime: admin 200, vendedor 200, ana (no dueña) sobre venta 1 → `403 {"detail":"No autorizado"}`, id 99999 → `404 {"detail":"Venta no encontrada"}`. `service.obtener` hace el 404 antes del 403 y decide con `_es_personal` / `cliente.usuario_id`. (Caso dueño-200 verificado por código y por los tests del repo; en la base actual ana no tiene ventas propias.) |
| §6 — `/mis-ventas` solo pide estar autenticado y devuelve solo lo propio | **FAIL** | La ruta quedó montada como `/ventas/mis-ventas` (el router tiene `prefix="/ventas"` y el handler `@router.get("/mis-ventas")`). `GET /mis-ventas` → **404** `{"detail":"Not Found"}` (runtime y `openapi.json`: solo existe `/ventas/mis-ventas`). La consigna (tabla de rutas: `GET /mis-ventas (page, size)`, RN-14), la KB (`02_descripcion_general.md`, `03_actores_y_roles.md`, `05_reglas_de_negocio.md`, `06_funcionalidades.md`) y el propio checklist §6 piden el path `/mis-ventas`. La funcionalidad sí existe en `/ventas/mis-ventas`: sin cookie → 401, ana → 200 `{items:[],total:0,...}`, vendedor (sin ficha) → 200 página vacía (SU-05). |
| §8 — No existe `PATCH /ventas/{id}` | PASS | `grep -i patch app/modules/ventas/router.py` vacío; `openapi.json`: rutas PATCH = solo `/autores/{id}`, `/clientes/{id}`, `/editoriales/{id}`, `/libros/{id}`. |
| §8 — `GET /ventas` paginado para VENDEDOR/ADMIN con envoltorio y orden estable | PASS | Runtime: admin 200 y vendedor 200 con `{items,total,page,size,pages}`; `size=2` respetado; orden `Venta.id.desc()` en `repository.listar`; cliente (ana) → 403. |
| §8 — detalle con renglones, `precio_unitario` copiado del libro y total del servidor | PASS | Runtime venta 1: renglón 1 `precio_unitario 25000.00` = `libro 1 (Rayuela)`, renglón 2 `22000.00` = `libro 3 (Ficciones)`; `subtotal` derivado; `total 69000.00` = 1×25000 + 2×22000. |
| §8 — el detalle muestra el título de un libro dado de baja (RN-13) | PASS (por código) | `VentaRepository.get_by_id` hace `select(Venta)` sin filtro de `borrado_en` + `selectinload(Venta.renglones).selectinload(RenglonVenta.libro)` sin filtro. No verificable en runtime con la base actual (ningún libro dado de baja y la auditoría no puede escribir). |
| Spec — precarga fija sin N+1 (3 SELECT, no crece con renglones) | PASS (por código) | `selectinload` anidado declarado adentro de `get_by_id` (`repository.py:33-42`); listado y `ventas_de_cliente` con `selectinload(Venta.cliente)` + `paginar()`. |
| §7 — repositorios sin `commit()` (solo `flush()`) | PASS | `grep "commit()"` sobre `app/core/repository.py` y `app/modules/*/repository.py`: vacío. |
| §7 — servicio sin `AsyncSession` ni construcción de UoW | PASS | `grep "AsyncSession\|UnitOfWork(" app/modules/ventas/service.py`: vacío; recibe `VentasUnitOfWork` y abre con `async with`. (El `AsyncSession` que aparece en `usuarios/service.py` es el `intento_acceso` en sesión/transacción propias, ítem propio del checklist, fuera del scope de C-10.) |
| §7 — UoW del módulo compone sus repositorios con la misma sesión | PASS | `VentasUnitOfWork(session)` pasa la misma sesión a `VentaRepository`, `ClienteRepository`, `LibroRepository`, `RenglonVentaRepository`; dependencia `get_ventas_uow` sobre `get_session`. |
| §7 — UoW base: commit en `__aexit__` sin excepción, rollback con excepción, no cierra la sesión | PASS | `core/unit_of_work.py:51-56`: `commit()` / `rollback()`, `return False`, sin `close()`; `get_session` cierra. |
| §7 — precarga solo en `repository.py` (CV-03) | PASS | `grep "selectinload\|joinedload"` en `app/modules/ventas/service.py` y `router.py`: vacío; todo vive en `ventas/repository.py`. |
| §7 — router sin lógica de negocio ni `commit`/`rollback` (CV-01/CV-05) | PASS | Router solo construye el UoW por dependencia, delega al servicio y mapea a schemas; sin `AsyncSession` ni `commit()`/`rollback()`. |
| Spec — módulo `ventas` con las seis capas | PASS | `models, schemas, repository, unit_of_work, service, router` presentes. |
| Spec — sin `VentaUpdate` ni cambios de esquema/migraciones | PASS | `schemas.py` solo expone `VentaRead`, `VentaDetailRead`, `RenglonRead`, `ClienteRef`, `VentaCreate`, `RenglonCreate` con `extra="forbid"`; no se observan versiones nuevas de migración atribuibles a C-10. |
| §9 — envoltorio canónico `{items,total,page,size,pages}` y mensajes de página propios | PASS | Runtime en todas las rutas de listado; `paginacion.py` valida size/page y usa `max(1, ceil(total/size))`. |

## FAIL

1. **`GET /mis-ventas` no existe: la ruta quedó en `/ventas/mis-ventas`.** Consigna (tabla de rutas,
   `GET /mis-ventas (page, size)` y RN-14), checklist §6, KB y el propio proposal/tasks de C-10
   (task 5.4: «`GET /mis-ventas` → 200») piden el path standalone `/mis-ventas`. El handler se
   declaró dentro del router con `prefix="/ventas"`, por lo que `GET /mis-ventas` responde
   **404 `Not Found`** (verificado en runtime y en `openapi.json`, donde solo aparece
   `/ventas/mis-ventas`). La lógica del endpoint (401 sin cookie, solo lo propio, página vacía sin
   ficha) funciona correctamente en el path equivocado, y los tests del repo
   (`test_ventas_authorization.py`, `test_cambio_password_api.py`) usan también el path equivocado,
   por lo que la suite no lo detecta.

   **Fix recomendado**: mover el handler a un router sin el prefijo `/ventas` (o a su propio
   `APIRouter(prefix="/mis-ventas")`) montado en el grupo protegido de `main.py`, dejando
   `GET /mis-ventas` como ruta canónica; corregir en consecuencia los tests y la evidencia `.http`
   (caso C-06) que referencian `/ventas/mis-ventas`. La KB y el checklist ya están bien; solo falta
   el código y las pruebas.

## WARN

1. **`design.md` no registra la decisión del design stage.** Es un change sin UI y el documento no
   contiene la sección «UI Mockups / `Decision: no (no UI)`» que pide la política global del
   proyecto. Proceso, no afecta la nota funcional: registrar la decisión en el design archivado.

## Notas de alcance

- No se auditaron escrituras (`POST /ventas` es de C-16): solo se verificó por código que usa el
  mismo `VentasUnitOfWork`, un único `async with`, `flush()` vía repositorio y traducción de
  `IntegrityError`; el ítem §8 de precios copiados/total se verificó sobre la venta 1 del seed.
- El caso «dueño 200» de `GET /ventas/{id}` no es reproducible con la base actual (ningún cliente
  con ventas propias y `usuario_id` ligado en el seed); quedó verificado por código y por la suite
  del repo, no por runtime de esta auditoría.
