# Auditoría C-06 — capas-editoriales-generos-autores

- **Fecha**: 2026-11-08
- **Auditor**: subagente de auditoría (solo lectura)
- **Criterio**: `docs/CHECKLIST_ENTREGA.md` §0, §1, §7, §9 · `CHANGES.md` `### [C-06]` · `openspec/changes/archive/2026-11-05-c-06-capas-editoriales-generos-autores/`
- **Método**: inspección de código (`parcial/app/modules/{editoriales,generos,autores}/`, `parcial/app/core/`) + greps de invariantes + ejecución **read-only** contra PostgreSQL 17.11 vía ASGITransport (GETs y 401 de POST/PATCH sin cookie; ninguna escritura: los POST/PATCH se auditaron por código y evidencia de tasks). DB verificada sin cambios tras la corrida (3 editoriales, 3 géneros, 6 autores, 5 libros, 0 filas `AUDIT%`).
- **Limitación declarada**: no se ejecutaron POST/PATCH con escritura (prohibido en auditoría); el 409 de duplicado y el 200/422 de PATCH se verifican por código y por los comandos de las tasks marcadas.

## Veredicto

**PASS 19/19 ítems verificables por lectura, 4 WARN, 0 FAIL.**

| # | Ítem | Fuente | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | Seis capas en `editoriales`, `generos`, `autores` | §1, CV-03 | **PASS** | `ls` muestra `models/schemas/repository/unit_of_work/service/router.py` en los tres módulos |
| 2 | Router construye el UoW (dependencia), servicio lo abre con `async with` | §0, CV-01 | **PASS** | Routers usan `Depends(get_*_uow)`; servicios usan `async with uow:`; grep `async with` en routers vacío |
| 3 | Ningún servicio recibe `AsyncSession` ni construye el UoW | §7 | **PASS** | grep `AsyncSession\|UnitOfWork(` en `service.py` solo matchea `usuarios/service.py` (sesión propia de `intento_acceso`, excepción declarada en el propio checklist); los 3 módulos limpios |
| 4 | Repositorios solo `flush()`, nunca `commit()` | §7, CV-02 | **PASS** | `BaseRepository` solo `flush()`; grep `commit()` en repos vacío; commit solo en `__aexit__` del UoW |
| 5 | UoW por módulo compone su repositorio con la misma sesión | §7 | **PASS** | `EditorialesUnitOfWork(session)`, `GenerosUnitOfWork`, `AutoresUnitOfWork` heredan `UnitOfWork` y pasan la sesión recibida; misma sesión del UoW que `get_usuario_actual`/`requiere_rol` (misma dependencia `get_session` cacheada por request) |
| 6 | Precarga solo en `repository.py` | §0, CV-02/CV-03 | **PASS** | grep `selectinload\|joinedload` fuera de `repository.py` solo aparece en docstrings; `libros_de()` con `joinedload(Libro.editorial/…genero)` dentro del repositorio |
| 7 | Listado devuelve `{items, total, page, size, pages}` | §9 | **PASS** | Runtime: `GET /editoriales` → 200 `{"items":[…],"total":3,"page":1,"size":20,"pages":1}`; igual en `/generos` (total 3) y `/autores` (total 6), coinciden con `SELECT count(*)` |
| 8 | `page` desde 1; `size` 1–100 default 20 | §9 | **PASS** | Runtime: sin `size` → `size: 20`; `size=500` → 422; `page=0` → 422; `size=abc` → 422; `page=2&size=2` → 1 ítem; `/autores?size=3&page=2` → 3 ítems |
| 9 | Página más allá de la última → 422 con mensaje propio | §9 | **PASS** | Runtime: `page=99` → 422 `"La página 99 no existe: hay 1"` |
| 10 | `total` con los mismos filtros; cero resultados → `pages: 1` | §9 | **PASS** | Listados sin filtros; `paginar()` cuenta con subquery del mismo `stmt` y `pages = max(1, ceil(total/size))` |
| 11 | Códigos: 201 al crear, 404 recurso de la ruta, 409 choque, 422 contrato | §9, RN-01 | **PASS** | Routers `status_code=201` en POST; runtime 404 `"Editorial no encontrada"` en id inexistente; `traducir_integrity_error` mapea `editorial_nombre_key` y `genero_nombre_key` → 409 con mensaje propio (por código; sin escritura en auditoría) |
| 12 | `extra="forbid"` y PATCH con `exclude_unset` | §9, CV-07 | **PASS** | Schemas de los 3 módulos con `extra="forbid"` (+`SinNulMixin`); `actualizar()` usa `model_dump(exclude_unset=True)` |
| 13 | POST/PATCH protegidos por rol ADMIN | RN-04, tabla de endpoints | **PASS** | `router_admin` con `Depends(requiere_rol("ADMIN"))` montado en el grupo protegido; runtime sin cookie: POST/PATCH de los 3 módulos → 401, sin escrituras (DB verificada) |
| 14 | `GET /{id}/libros` 404 si la entidad no existe | Scope C-06 | **PASS** | Runtime: `/editoriales/999999/libros` → 404; por código igual en géneros/autores |
| 15 | `GET /{id}/libros` excluye libros dados de baja | Scope C-06, RN-13 | **PASS** | `libros_de()` filtra `Libro.borrado_en.is_(None)` (editorial/género por columna; autor vía join `libro_autor`); runtime con 5 libros vigentes devuelve los esperados por entidad (Rayuela/Bestiario en Sudamericana y Cortázar, etc.); DB tiene 0 borrados hoy, por lo que el filtro se verificó por código |
| 16 | `PATCH /editoriales/{id}` y `PATCH /autores/{id}` aplican solo lo enviado | Scope C-06 | **PASS** | `setattr` por campo de `model_dump(exclude_unset=True)`; 404 previo; IntegrityError traducido (por código) |
| 17 | `POST` duplicado → 409 mensaje propio (RN-01) | Scope C-06 | **PASS** | Constraints `editorial_nombre_key`/`genero_nombre_key` existen en la base y están en `CONSTRAINTS` con mensaje propio; el `unique=True` del modelo los genera (por código; no ejecutado para no escribir) |
| 18 | Errores sin texto interno ni traza (RN-15) | §9 | **PASS** | Runtime: 422 de query inválida con `msg` propio en español, 404/401 propios; handlers globales `manejador_request_validation_error`/`manejador_dbapi_error` sin texto de PostgreSQL |
| 19 | Tasks y estado del change | workflow | **PASS** | `tasks.md` todas `[x]`; CHANGES.md `C-06` `[x]` archivado como `2026-11-05-c-06-capas-editoriales-generos-autores` |

## WARN

1. **`PATCH /autores/{id}` → 409 por unicidad es rama muerta.** El modelo `Autor` no tiene ningún `UNIQUE` (solo `nombre`, `nacionalidad` sin constraint); el `IntegrityError` de unicidad no puede dispararse al actualizar un autor, a diferencia de `editorial`/`genero` (`unique=True`). El scope de C-06 promete «409 unicidad» en PATCH autores, pero no es ejercitable. *Fix recomendado:* decidir si `autor` debe tener unicidad (p. ej. `(nombre, nacionalidad)`) con migración, o quitar la promesa de 409-unicidad del scope de PATCH autores.
2. **`GET /generos/{genero_id}` no existe** (solo `POST /generos`, listado y `/generos/{id}/libros`). No lo exige el scope de C-06, pero `GeneroService.obtener()` queda sin ruta (código muerto) y la colección de detalle es asimétrica frente a editoriales/autores. *Fix recomendado:* exponer `GET /generos/{genero_id}` o eliminar `obtener` del servicio.
3. **Numeración CV inconsistente entre documentos.** `editoriales/repository.py` (y `app/core/repository.py`, `main.py`) atribuyen la precarga a `CV-03` y el `flush()` a `CV-02`; el checklist §0 y `knowledge-base` atribuyen la precarga a `CV-02` y los paths a `CV-03`. Preexistente, sin impacto funcional; conviene unificar antes de entregar.
4. **Evidencia de task imprecisa:** task 5.2 declara verificar con `python -c "import app.main"`, pero `main.py` vive en `parcial/main.py` (no en `parcial/app/`): ese comando literal falla (`ModuleNotFoundError: app.main`). El equivalente correcto es `import main` con `PYTHONPATH=parcial`. No es defecto de código; ajustar la evidencia o el comando.

## Notas del auditor

- El enrutado usa `redirect_slashes` (default): `GET /editoriales` responde 307 a `/editoriales/`; con cliente que sigue redirects todo funciona. No contraviene la tabla de endpoints, pero los `.http` de evidencia deberían usar las rutas con barra final.
- La dependencia `get_usuario_actual`/`requiere_rol` y el UoW comparten la misma instancia de sesión por petición (misma dependencia `get_session` cacheada), cumpliendo «una conexión por petición autenticada» (§7).
- El cambio no introdujo migraciones ni cambios de esquema (consistente con el proposal).
