# Auditoría C-05 — errores-paginacion-contratos

- **Fecha**: 2026-11-08
- **Auditor**: subagente auditor (solo lectura: sin pytest, sin seed, sin escrituras en la base, sin servidor)
- **Change**: `2026-11-05-c-05-errores-paginacion-contratos` (archivado, `[x]` en CHANGES.md)
- **Método**: lectura de código + `httpx.ASGITransport` contra `main:app` (lifespan ejecutado manualmente, solo GETs y POSTs cuyo body nunca parsea) + validación de schemas en proceso (sin DB) + traducción unitaria de errores con excepciones sintéticas. Base de datos solo con `SELECT`.
- **Estado de la base**: sembrada (5 libros, 3 editoriales, 3 géneros, 6 autores, 3 clientes, 1 venta).

## Veredicto

**PASS 8/8 ítems de §9, PASS §0 (password_hash), PASS C-01 (422). Sin FAIL. 3 WARN (2 de calidad/documentación + 1 límite de la auditoría).**

## Tabla por ítem (docs/CHECKLIST_ENTREGA.md)

| Ítem | Estado | Evidencia |
|---|---|---|
| §9.1 Todo listado devuelve `{items, total, page, size, pages}` | **PASS** | Runtime: `GET /libros/?size=2` → 200, keys exactas, total 5, pages 3. `GET /editoriales/?size=2`, `/generos/?size=2`, `/autores/?size=2` → 200 con las 5 keys. Por código: ventas (`GET /ventas/` y `/mis-ventas`, `Pagina`), eventos (`GET /eventos/`, `Pagina`), `/clientes/{id}/ventas` (`Pagina`). |
| §9.2 `page` desde 1; `size` 1..100, default 20 | **PASS** | Runtime: sin `size` → `size: 20`; `size=500` → 422 «El valor supera el máximo permitido»; `size=0` → 422; `size=abc` → 422 «Debe ser un número entero válido»; `page=0` → 422. Routers: `Query(1, ge=1)` / `Query(20, ge=1, le=100)`; `paginar()` además valida 1..100. |
| §9.3 Página fuera de rango → 422 con mensaje propio | **PASS** | Runtime: `GET /libros/?page=999&size=2` → 422 `{"detail": "La página 999 no existe: hay 3"}` (formato exacto «La página X no existe: hay Y»). `titulo=ficc&size=1&page=2` → 422 «La página 2 no existe: hay 1». |
| §9.4 `total` con los mismos filtros; cero resultados → una página vacía | **PASS** | Runtime: `titulo=ficc&size=1` → `total: 1, pages: 1, items: [Ficciones]`; `titulo=zzz-no-existe` → `total: 0, pages: 1, items: []`; `titulo=' OR '1'='1` → `total: 0, pages: 1, items: []`. `paginar()` cuenta sobre `stmt.subquery()` (mismos filtros). |
| §9.5 Ningún error devuelve texto interno de la base ni traza | **PASS** | 422/404 observados sin texto de PostgreSQL («Libro no encontrado», mensajes propios). `traducir_integrity_error` unit: `uq_usuario_email` → 409 «Ya existe un usuario con ese email»; `ck_libro_precio_positivo` → 422; constraint desconocido → 409 genérico sin texto interno; `DataError` → 422 genérico; handler global `DBAPIError` → 500 genérico. **Límite**: el 409 por unicidad/FK no se disparó en runtime (prohibido insertar); verificado por unit + código (servicios capturan `IntegrityError` y traducen). |
| §9.6 Ninguna entrada inválida termina en 500 (id no entero, JSON malformado, NUL, size gigante, contraseña 73 bytes) | **PASS** | Runtime: `GET /libros/abc` → 422 «Debe ser un número entero válido» (sin ejecutar handler de negocio); `POST /auth/registro` con `{"email": "x` → 422 `json_invalid`; `size=500` → 422. Schemas (sin DB): `UsuarioCreate` con NUL en `nombre` → ValidationError; con password de 73 bytes → ValidationError. |
| §9.7 Búsqueda ligada, case-insensitive, inyección no rompe | **PASS** | Código: `Libro.titulo.ilike(f"%{titulo}%")` (parámetro ligado por SQLAlchemy). Runtime: `titulo=FICCIONES` → `total: 1` (insensible a mayúsculas); `titulo=' OR '1'='1` → 200, `total: 0`, sin devolver todo. |
| §9.8 `extra="forbid"` + `exclude_unset` + códigos de la tabla | **PASS** | 38 `extra="forbid"` en schemas de los 7 módulos; schemas Create/Update/Read por entidad presentes. Runtime de validación: campo extra rechazado en los 7 `Create` (tipo `extra_forbidden`). `exclude_unset` en los 4 PATCH existentes (editoriales, autores, libros, clientes). Códigos: 201 en todos los creates, 204 en la baja de libros, 404 en lecturas de detalle, 409/422 traducidos por constraint. |
| §0 «Ninguna respuesta incluye `password_hash`» | **PASS** | `grep password_hash app/modules/*/schemas.py` → vacío; `UsuarioRead` = `{id, email, nombre, activo, debe_cambiar_password}`. |
| §10 C-01 `GET /libros/abc` → 422 sin ejecutar el handler | **PASS (parcial)** | El 422 se reproduce contra la app real con cuerpo estable (`loc`/`msg`/`type` en español). El «log sin la query» no es verificable sin levantar el servidor (prohibido en esta auditoría); el handler no se alcanza porque FastAPI valida antes. |

## WARN

1. **Mensajes por tipo incorrectos** (`parcial/app/core/errors.py` líneas 166-167): `bool_type` y `float_type` mapean a «Debe ser un número entero válido», mensaje que no describe el tipo real. No viola RN-15 (sin texto interno) ni el 422, pero es engañoso para el cliente. Fix recomendado: mensajes propios por tipo («Debe ser un valor booleano válido», «Debe ser un número válido»).
2. **CV-08 no documentado en todos los servicios** (task 5.1): el orden explícito `404 → 403 → 409 → 422` aparece en `clientes` y `editoriales` (variantes en `usuarios` y `ventas`), pero **falta el comentario de contrato en `autores`, `generos` y `libros`** (solo tienen los `raise` 404). Desviación de documentación, sin impacto funcional.
3. **409 runtime no ejercitado**: la auditoría es solo lectura; la traducción de unicidad/FK/CHECK se verificó unitariamente y por código, no end-to-end. El caso C-02/C-12 (409 propios) queda para la verificación con `.http` que sí escribe.

## Observaciones (no bloqueantes)

- `GET /clientes/` y `GET /usuarios/` no exponen listado (405); `clientes.repository.listado` y `usuarios.repository.listado` están paginados pero sin ruta que los use hoy. No es ítem de C-05 («listados existentes» al momento del cambio: libros, editoriales, géneros, autores, ventas, eventos — todos con `Pagina`).
- Sin `create_all` en `parcial/` (task 6.1) ✓.
- `test/` contiene los `.http` de evidencia (auth, libros, registro, roles, ventas); no ejecutados en esta auditoría (requieren escritura).
