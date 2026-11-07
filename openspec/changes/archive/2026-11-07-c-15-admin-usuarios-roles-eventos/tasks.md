# Tasks — C-15 admin-usuarios-roles-eventos

Ciclo obligatorio por tarea de código (**Strict TDD**): red de seguridad (correr los tests existentes de los archivos que se tocan y anotar el baseline) → **RED** (test que falla y nombra comportamiento del spec) → **GREEN** (mínimo código para pasar) → **triangulación** (al menos un caso más, con entradas distintas) → **refactor** (tests verdes después de cada paso). Cada tarea dice cómo se verifica; la trazabilidad cita `RN-xx` (consigna), `CV-xx` (convención), `DD-xx`/`SU-xx` (decisiones y supuestos) o un ítem de `docs/CHECKLIST_ENTREGA.md` (§ / fuente). Todo el trabajo vive en `parcial/`; `despliegue/` no se toca.

## 1. Red de seguridad y desbloqueo del módulo `usuarios`

- [x] 1.1 Correr la suite completa de `parcial/tests` contra PostgreSQL local y anotar el baseline (`N passed, M errors`) antes de tocar nada. **Verificación:** comando `python -m pytest parcial/tests -q` ejecutado y baseline registrado en el resumen de apply; si aparece el `NameError` de 1.2, queda registrado como fallo **preexistente** y no se atribuye a este change. Trazable: `RD-01`.

- [x] 1.2 RED del import roto: agregar `parcial/tests/test_usuarios_repository_import.py` con un test que importe `app.modules.usuarios.repository.EventoSeguridadRepository` y verifique que la anotación de `listado` resuelve. **Verificación:** el test falla hoy con `NameError: name 'Pagina' is not defined` (RED confirmado por ejecución). Trazable: hallazgo verificado del `design.md` §10, CHECKLIST §9.

- [x] 1.3 GREEN: agregar `Pagina` al import de `app.core.paginacion` en `parcial/app/modules/usuarios/repository.py` (sin otros cambios). **Verificación:** el test de 1.2 pasa y `python -c "import app.modules.usuarios.repository"` no falla. Trazable: `CV-02`, `design.md` §10.

- [x] 1.4 Re-correr la suite y confirmar que el baseline de 1.1 se recupera (misma cantidad de passed, 0 errors). **Verificación:** comparación numérica baseline vs. post-fix en el resumen de apply. Trazable: `RD-01`.

## 2. Schemas de administración — TDD

- [x] 2.1 RED de contratos: escribir `parcial/tests/test_admin_schemas.py` con los casos que deben fallar: `PersonalCreate` con `rol="CLIENTE"` → error de validación; con campo extra → error; con `password` de 73 bytes → error; `email` se normaliza a minúsculas y sin espacios. `AsignacionRolCreate` con `vence_en` sin zona → error; con `vence_en` en el pasado → error; con `rol` inválido → error. **Verificación:** los tests fallan por `ImportError`/`ValidationError` ausente (RED confirmado). Trazable: `alta-de-personal`, `roles-de-usuario`; `SU-02`, `DD-17`.

- [x] 2.2 GREEN: crear en `parcial/app/modules/usuarios/schemas.py` `PersonalCreate` (`email` con `_normalizar_email`, `nombre`, `password` con `validar_password_bytes`, `rol: Literal["ADMIN","VENDEDOR"]`, `extra="forbid"`, `SinNulMixin`), `AsignacionRolCreate` (`rol: Literal["ADMIN","VENDEDOR","CLIENTE"]`, `vence_en: AwareDatetime | None` con validador de futuro) y los schemas de salida `AsignacionRolRead` y `EventoSeguridadRead` (`from_attributes=True`, sin `password_hash`). **Verificación:** los tests de 2.1 pasan. Trazable: `RN-15`, `CV-07`, `design.md` §6.

- [x] 2.3 Triangulación de contratos: agregar casos con entradas distintas — `vence_en` a +1 día y a −1 día, `vence_en` con offset `-03:00`, `email` con mayúsculas y espacios, `rol="VENDEDOR"` válido, `password` de exactamente 72 bytes (válido) y 73 (422), NUL en `nombre` (422). **Verificación:** todos pasan y ningún caso es tautológico (cada uno compara un valor esperado distinto). Trazable: `CV-15`, `RN-15`, `RN-03`.

- [x] 2.4 Refactor: extraer el validador de `vence_en` futuro a una función reutilizable dentro de `schemas.py` si quedó duplicado; verificar que `UsuarioRead` no cambió y que ningún schema expone `password_hash`. **Verificación:** `test_admin_schemas.py` sigue verde y `grep -rn "password_hash" parcial/app/modules/usuarios/schemas.py` no devuelve nada. Trazable: `CV-07`.

## 3. Repositorios y Unit of Work de administración — TDD

- [x] 3.1 RED de repositorio: escribir `parcial/tests/test_admin_repository.py` con sesión fake/real para: `get_abierta` devuelve `vigente=False` cuando `vence_en` ya pasó y `vigente=True` cuando es futuro o `NULL`; `get_abierta` ignora filas con `revocada_en` no nulo; `listar_por_usuario` ordena por `desde DESC, id DESC` e incluye revocadas y vencidas; `contar_admins_vigentes` excluye la fila indicada, las revocadas y las vencidas; `cerrar` escribe `revocada_en` y hace `flush` sin `commit`; `abrir` agrega y hace `flush`. **Verificación:** los tests fallan por métodos inexistentes (RED confirmado). Trazable: `RN-03`, `RN-05`, `CV-02`.

- [x] 3.2 GREEN: implementar en `parcial/app/modules/usuarios/repository.py` el dataclass `AbiertaRol`, `get_abierta` (con `vigente` calculado en SQL con `now()`), `listar_por_usuario`, `contar_admins_vigentes(excluir_id, bloquear)` y `cerrar`; agregar `abrir` a `AsignacionRolRepository`. Ninguna consulta hace `commit`; `selectinload` solo aparece en `repository.py`. **Verificación:** los tests de 3.1 pasan. Trazable: `RN-03`, `RN-05`, `CV-02`, `CV-03`, `design.md` §3.

- [x] 3.3 GREEN del UoW: agregar `AdminUnitOfWork` (repositorios `usuarios`, `roles`, `eventos` sobre la misma sesión) y `get_admin_uow` en `parcial/app/modules/usuarios/unit_of_work.py`; test que verifica que los tres repositorios comparten la misma sesión y que la dependencia la resuelve una sola vez por petición. **Verificación:** el test de composición pasa y `python -c "import app.modules.usuarios.unit_of_work"` no falla. Trazable: `CV-01`, CHECKLIST §7.

- [x] 3.4 Triangulación contra PostgreSQL real: test que crea un usuario con una asignación abierta, la marca vencida y verifica que `get_abierta` la reporta vencida y que `cerrar` + `abrir` en la misma transacción **no** viola `uq_asignacion_rol_abierta`; y test que sin el `flush` intermedio la inserción sí falla (documenta por qué existe el `flush`). **Verificación:** ambos pasan con PostgreSQL local. Trazable: `RN-03`, índice `uq_asignacion_rol_abierta`, `design.md` §4.

- [x] 3.5 Refactor: verificar que `contar_admins_vigentes(bloquear=True)` emite `FOR UPDATE` (test que inspecciona el SQL compilado) y que el conteo sin bloqueo no lo emite; sin `commit()` en el módulo. **Verificación:** test de SQL compilado pasa y `grep -n "commit(" parcial/app/modules/usuarios/repository.py` no devuelve nada. Trazable: `RN-05`, `CV-02`, `design.md` §3.

## 4. Servicio de alta de personal — TDD

- [x] 4.1 RED: escribir `parcial/tests/test_admin_alta_service.py` con UoW fake: un alta exitosa crea el usuario con `debe_cambiar_password=True`, una asignación inicial con `otorgada_por` igual al admin y una línea de `evento_seguridad` con `actor` igual al email del admin; si la escritura del rol falla, no queda usuario y no queda evento. **Verificación:** los tests fallan por `AttributeError` del servicio inexistente (RED confirmado). Trazable: `RN-16`, `alta-de-personal`, CHECKLIST §7.

- [x] 4.2 GREEN: implementar `service.alta_personal(uow, data, *, admin, settings, semaphore)` con el hash **antes** del `async with uow` (`to_thread` + semáforo) y las tres escrituras dentro de un solo `async with`. Devuelve el `Usuario`. **Verificación:** los tests de 4.1 pasan (GREEN confirmado). Trazable: `RN-08`, `RN-16`, `CV-01`.

- [x] 4.3 Triangulación: casos con entradas distintas — correo ya existente (la traducción de `uq_usuario_email` produce `409` y no queda rol ni evento), rol inicial `VENDEDOR`, email con mayúsculas (se guarda normalizado), y fallo forzado en el `add` del evento (no queda usuario). **Verificación:** los cuatro pasan con el mismo servicio. Trazable: `RN-01`, `RN-16`, `CV-08`.

- [x] 4.4 Refactor: comprobar que el servicio recibe el UoW y **no** la sesión, que no construye el UoW y que el hash no corre dentro del `async with` (test de orden con espías). **Verificación:** los tres asserts pasan y la suite del grupo 4 sigue verde. Trazable: `CV-01`, `RN-08`.

## 5. Servicio de roles: asignar, revocar y listar — TDD

- [x] 5.1 RED de asignación: `parcial/tests/test_admin_roles_service.py` con casos que fallen: asignación nueva escribe la fila con `otorgada_por` del admin y su evento; usuario inexistente → `404`; asignación abierta **vigente** del mismo rol → `409` sin escribir evento; asignación abierta **vencida** → cierra la anterior y abre la nueva, con dos filas en el historial y una sola línea de evento para la operación. **Verificación:** los tests fallan por servicio inexistente (RED confirmado). Trazable: `RN-03`, `RN-16`, `roles-de-usuario`.

- [x] 5.2 RED de revocación: revocar escribe `revocada_en`, no modifica otros campos, no borra la fila y deja evento; rol nunca asignado → `404`; asignación ya revocada → `409`; usuario inexistente → `404`; revocar una fila abierta pero vencida → `200`. **Verificación:** fallan por servicio inexistente (RED confirmado). Trazable: `RN-16`, `SU-12`, `roles-de-usuario`.

- [x] 5.3 RED de `RN-05`: revocar el propio `ADMIN` → `409`; revocar el único `ADMIN` vigente (con otro admin autenticado) → `409`; con dos `ADMIN` vigentes, revocar el del otro → `200`; con un `ADMIN` vigente y otro vencido, revocar el vigente → `409`; en todos los `409` no se escribe evento ni se modifica la fila. **Verificación:** fallan por servicio inexistente (RED confirmado). Trazable: `RN-05`, `roles-de-usuario`, CHECKLIST §6.

- [x] 5.4 GREEN: implementar `service.asignar_rol`, `service.revocar_rol` y `service.listar_roles` en `parcial/app/modules/usuarios/service.py`, con el orden `404 → 409 → RN-05 → escritura`, `cerrar` + `flush` antes de `abrir` en la reasignación y `contar_admins_vigentes(bloquear=True)` antes de revocar un `ADMIN`. **Verificación:** los tests de 5.1, 5.2 y 5.3 pasan. Trazable: `RN-03`, `RN-05`, `RN-16`, `CV-08`, `design.md` §4 y §5.

- [x] 5.5 Triangulación: casos adicionales — reasignar un rol previamente revocado (201, dos filas), revocar un rol `VENDEDOR` cuando el usuario también tiene `ADMIN` (no se pierde el `ADMIN`), y listar el historial de un usuario sin filas (200 con lista vacía). **Verificación:** los tres pasan. Trazable: `RN-03`, `RN-05`.

- [x] 5.6 Integración contra PostgreSQL real: dos sesiones concurrentes que intentan revocar los dos últimos `ADMIN` — una obtiene `200` y la otra `409`, y queda exactamente un `ADMIN` vigente. **Verificación:** el test pasa de forma estable al correrlo cinco veces seguidas. **Hallazgo:** la primera versión de `contar_admins_vigentes(bloquear=True)` excluía la fila objetivo también del `FOR UPDATE`, dejando bloqueos disjuntos; se corrigió para bloquear todas las filas y excluir en memoria, y `test_el_conteo_con_bloqueo_serializa_dos_sesiones` fija la garantía (la segunda sesión debe esperar). Trazable: `RN-05`, `design.md` §3 y §5 (bloqueo de filas).

- [x] 5.7 Refactor: sin lógica de negocio en el router (se completa al montar las rutas en 6.2), sin `AsyncSession` en las firmas de los servicios de administración, sin `commit()` en repositorios. **Verificación:** `grep` sin resultados sobre las funciones de administración (`alta_personal`, `asignar_rol`, `revocar_rol`, `listar_roles`) y sobre `repository.py`; `service.py` conserva `AsyncSession`/`commit()` **solo** en `registrar_intento_acceso`, la escritura fuera de la transacción que autoriza `DD-05`. Trazable: `CV-01`, `CV-02`.

## 6. Rutas de administración y montaje protegido — TDD

- [x] 6.1 RED de API: `parcial/tests/test_admin_usuarios_api.py` con `201` en `POST /usuarios`, `409` por correo repetido, `422` por campo extra y por `rol` inválido, `401` sin cookie, `403` con `VENDEDOR` y `403` con `ADMIN` y `debe_cambiar_password=true`. **Verificación:** las rutas devuelven `404` (no existen) y los tests fallan (RED confirmado). Trazable: `alta-de-personal`, CHECKLIST §5, §6.

- [x] 6.2 GREEN: crear `parcial/app/modules/usuarios/router_admin.py` con `router_usuarios` (`POST /usuarios`, `GET|POST /usuarios/{id}/roles`, `DELETE /usuarios/{id}/roles/{rol}`) usando `Depends(get_admin_uow)`, `Depends(requiere_rol("ADMIN"))` y traducción de `IntegrityError`; montarlo en el grupo protegido de `parcial/main.py`. **Verificación:** los tests de 6.1 pasan y `python -c "import main"` no abre conexiones. Trazable: `RN-04`, `RN-16`, `CV-01`, `design.md` §1 y §2.

- [x] 6.3 RED+GREEN de la API de roles: `parcial/tests/test_admin_roles_api.py` con `201` al asignar (con y sin `vence_en`), `422` por fecha sin zona y por fecha pasada, `404` por usuario inexistente, `409` por segunda asignación abierta, `200` al revocar con `revocada_en` en el cuerpo, `404` por rol nunca asignado, `409` por revocación del propio `ADMIN` y `200` en `GET /usuarios/{id}/roles` con las dos filas del historial. **Verificación:** el ciclo completo (rojo antes de 6.2, verde después) queda evidenciado por ejecución. Trazable: `RN-03`, `RN-05`, `SU-12`, CHECKLIST §6.

- [x] 6.4 RED+GREEN de `GET /eventos`: `parcial/tests/test_admin_eventos_api.py` con `200` y envoltorio `{items,total,page,size,pages}` por defecto (`page=1`, `size=20`), `size=500` → `422`, `page` fuera de rango → `422`, lista vacía → `pages=1`, orden del más reciente al más antiguo, ítem con `actor="SISTEMA"` y `403`/`401` según corresponda. **Verificación:** el test del envoltorio falla antes de montar la ruta y pasa después. Trazable: `RN-16`, `DD-18`, `eventos-seguridad`.

- [x] 6.5 Integración de auditoría: test contra PostgreSQL real que da de alta, asigna y revoca, y verifica que `GET /eventos` muestra las tres líneas con `actor` igual al email del admin; y test que fuerza rollback en el alta y confirma que no queda línea. **Verificación:** ambos pasan. Trazable: `RN-16`, CHECKLIST §7.

- [x] 6.6 Refactor: los tres routers nuevos no contienen lógica de negocio; el UoW se construye una sola vez por petición; `requiere_rol("ADMIN")` aparece en cada ruta y `control_cambio_password` solo a nivel de router protegido. **Verificación:** `grep -c "Depends(control_cambio_password)" parcial/main.py` devuelve 1 y ningún router de módulo lo repite. Trazable: `RN-04`, `RN-06`, CHECKLIST §1.

## 7. Catálogo bajo la puerta del cambio obligatorio — TDD

- [x] 7.1 RED: `parcial/tests/test_catalogo_protegido.py` con el comportamiento nuevo que hoy falla: un `ADMIN` con `debe_cambiar_password=true` recibe `403` en `POST /libros`, `PATCH /libros/{id}`, `DELETE /libros/{id}`, `POST /libros/{id}/reponer` y `GET /libros/{id}/movimientos`, y también en las mutaciones de editoriales, géneros y autores; y un test de tabla de rutas que fija paths y métodos del catálogo (para detectar movimientos accidentales). **Verificación:** los casos de `403` fallan hoy (devuelven `200`/`404` de negocio) — RED confirmado. Trazable: CHECKLIST §5, `grupos-de-rutas`.

- [x] 7.2 GREEN: separar en `parcial/app/modules/{editoriales,generos,autores,libros}/router.py` un `router` (solo lecturas públicas) y un `router_admin` (mutaciones `ADMIN`) con el mismo `prefix` y `tags`; montar los cuatro `router_admin` en el grupo protegido de `parcial/main.py` y dejar los `router` en el abierto. **Verificación:** los `403` de 7.1 pasan y no cambia ningún path. Trazable: `RN-06`, `design.md` §8.

- [x] 7.3 Triangulación: las lecturas públicas del catálogo siguen respondiendo `200` sin cookie; un `ADMIN` sin cambio pendiente sigue recibiendo `201`/`200` en las mutaciones; un `VENDEDOR` sigue recibiendo `403`; y la lista de paths/métodos del catálogo es idéntica a la de los tests preexistentes (`test_catalogo_rbac.py`). **Verificación:** los cuatro pasan y `test_catalogo_rbac.py` sigue verde sin modificarse. Trazable: `RN-06`, CHECKLIST §6.

- [x] 7.4 Refactor: sin handlers duplicados entre `router` y `router_admin`; los tags y `summary` de OpenAPI se conservan. **Verificación:** test que compara el conjunto de `(method, path)` del `app` antes/después (guardado en el test) coincide, y un `grep` confirma que cada handler aparece una sola vez. Trazable: `grupos-de-rutas` (requisito ADDED de no cambio de contratos).

## 8. Verificación transversal y aceptación de C-15

- [x] 8.1 Suite completa de `parcial/tests` contra PostgreSQL local, incluida la regresión de C-11…C-14. **Verificación:** `N passed, 0 errors` con `N` ≥ baseline de 1.1, y el número nuevo se anota en el resumen. Trazable: `RD-01`, CHECKLIST §10.

- [x] 8.2 Ejecutar literalmente la aceptación de C-15 en `docs/CHECKLIST_ENTREGA.md`: §6 (revocar quita el permiso a la sesión abierta; vencimiento pasado o sin zona → 422; reasignar cierra la fila anterior y la revocada nunca se borra; RN-05 → 409), §7 (eventos en la misma transacción; forzar rollback no deja línea), §5 (mutación de catálogo con cambio pendiente → 403) y §10 C-07/C-08. **Verificación:** cada ítem tiene su test o comando ejecutado; lo que no se pueda correr se reporta como no cumplido, no se marca. Trazable: `RN-03`, `RN-05`, `RN-16`, `RN-06`.

- [x] 8.3 Reglas duras: sin `create_all`; sin `commit()` en repositorios; sin `password_hash` en schemas; `selectinload` solo en `repository.py`; sin `float`; sin `timestamptz` naive en columnas nuevas (no hay columnas nuevas); 4 migraciones intactas y `alembic check` limpio; `despliegue/` sin tocar. **Verificación:** los `grep` de `CV-14`/`CV-02`/`CV-07`/`CV-03` y `alembic check` ejecutados en el resumen. Trazable: `CV-02`, `CV-03`, `CV-07`, `CV-14`.

- [x] 8.4 Actualizar `CHANGES.md`: marcar C-15 con su estado real y su aceptación; **verificar que C-14 esté archivado antes de archivar C-15** (la delta `grupos-de-rutas` es `MODIFIED` y necesita la spec destino en `openspec/specs/`). **Verificación:** `openspec validate c-15-admin-usuarios-roles-eventos` sin hallazgos y `ls openspec/specs/grupos-de-rutas` existe antes del archive de C-15. Trazable: `design.md` §Context y §Risks.

## Evidencia de cierre (auditoría 2026-11-07, PostgreSQL 17.11 real)

Auditoría posterior al archive: se verificó el comportamiento real, no los mensajes de commit. Comandos desde `parcial/` con `PYTHONPATH=parcial` y el `.env` apuntando a la base local `libreria`.

- **3.5** — `parcial/tests/test_admin_repository_sql.py` compila la sentencia de `contar_admins_vigentes`: `FOR UPDATE` presente con `bloquear=True` y ausente con `bloquear=False`. `grep -n "commit(" parcial/app/modules/usuarios/repository.py` sin resultados.
- **5.6** — `parcial/tests/test_admin_roles_concurrencia.py::test_dos_revocaciones_concurrentes_de_los_ultimos_admins_serializan`: dos sesiones revocan los dos últimos `ADMIN`, resultados `200`/`409` y queda exactamente un `ADMIN` vigente; corrido 5 veces seguidas (5/5 verdes).
- **7.1** — `parcial/tests/test_catalogo_protegido.py` cubre `403` para `ADMIN` con `debe_cambiar_password=true` en `POST`/`PATCH`/`DELETE` de libros, `reponer`, `movimientos`, y mutaciones de editoriales, géneros y autores, más la tabla de 20 pares `(method, path)` del catálogo. El RED histórico no es reproducible en el working tree actual; la verificación es el test verde y la estructura de `main.py` (ver 7.2).
- **7.2** — `router`/`router_admin` separados en los cuatro módulos, con el mismo prefijo y tags; `main.py` monta los `router` en el abierto y los cuatro `router_admin` en el protegido (`Depends(control_cambio_password)`).
- **7.3** — lecturas públicas sin cookie `200`, `ADMIN` sin cambio pendiente `201`/`200`, `VENDEDOR` `403`; `test_catalogo_rbac.py` verde sin modificarse; paths/métodos idénticos.
- **7.4** — sin handlers duplicados (`grep` de `def` en routers sin repeticiones); OpenAPI: 20 rutas de catálogo, 41 `operationId` únicos, tags `editoriales`/`generos`/`autores`/`libros` conservados.
- **8.1** — `python -m pytest tests -q` → **417 passed, 0 errors** (baseline 413; +4 tests de verificación agregados, sin cambios de producción).
- **8.2** — §6: `test_clientes_rbac.py::test_rol_revocado_o_vencido_quita_el_acceso_con_la_misma_cookie` y `test_auth_yo_api.py::test_yo_muestra_la_diferencia_tras_revocar_un_rol`; fechas `422` en `test_admin_roles_api.py`; reasignación/cierre en `test_admin_roles_service.py` y `test_admin_repository.py` (PostgreSQL real); `RN-05` en `test_admin_roles_service.py`, `test_admin_roles_api.py` y la concurrencia de 5.6. §7: `test_admin_auditoria_api.py` verifica usuario+rol+evento en una transacción y un fallo forzado tras la auditoría que no deja usuario ni línea. §5: `test_catalogo_protegido.py`. §10 C-07/C-08: los tests citados de sesión abierta, `/auth/yo`, historial y autoprotección.
- **8.3** — sin `create_all`; sin `commit(` en repositorios; sin `password_hash` en schemas; `selectinload` solo en `repository.py`; sin `float`; `alembic check` → «No new upgrade operations detected»; 4 migraciones (`0ba1752f…`, `5f67a857…`, `c8d2dea5…`, `dd4a0e5e…`); `git diff HEAD -- despliegue/` vacío.
- **8.4** — `2026-11-07-c-14-cambio-password-grupos-de-rutas` archivado junto a C-15; `openspec/specs/{alta-de-personal,eventos-seguridad,grupos-de-rutas,roles-de-usuario}` existen; `CHANGES.md` C-15 pasa a `[x]` con este detalle; `openspec validate --archived --strict` → C-15 38/38.
- **Hallazgo** — las tareas 3.5, 5.6 y 6.5 estaban `[x]` sin el test que decían; se agregaron tests de verificación (sin tocar código de producción). No se encontraron defectos funcionales en C-15.

## Workflow follow-up

- Al cerrar el change, archivar con `/opsx-archive` y recién entonces marcar `[x]` en `CHANGES.md`.
- Dejar los cambios en el working tree: no hacer `commit` ni `push` sin pedido explícito (regla dura 17).
