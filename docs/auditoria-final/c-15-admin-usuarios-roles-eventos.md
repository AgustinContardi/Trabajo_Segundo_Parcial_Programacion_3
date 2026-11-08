# Auditoría final — C-15 `admin-usuarios-roles-eventos`

- **Auditor:** subagente auditor final (solo lectura)
- **Fecha:** 2026-11-08
- **Alcance:** `docs/CHECKLIST_ENTREGA.md` §6 (Autorización) + §4 (modelo) aplicable; foco en rutas de administración de `C-15`.
- **Método:** lectura de código (`parcial/app/…`), `psql` con SELECT únicamente, `alembic check`, API en vivo con `httpx` + `ASGITransport` in-process (solo lecturas y logins; los logins escriben `intento_acceso`, permitido), y evidencia registrada (`tasks.md`, `parcial/test/EVIDENCIA.md`, `parcial/test/roles.http`, tests de `parcial/tests/`). NO se ejecutó `pytest` ni `seed.py`; NO hubo INSERT/UPDATE/DELETE vía auditoría.
- **DB:** PostgreSQL 17.11 en `127.0.0.1:5432/libreria` — estado sembrado canónico (5 usuarios, 5 asignaciones, 1 evento `SISTEMA`).

## Veredicto global: **PASS** (2 WARN, 0 FAIL)

Todos los ítems de §6 aplicables a C-15 se cumplen, verificados por código, por evidencia registrada y por peticiones en vivo (401/403/200/422/404 observadas). Los dos WARN son el defecto de migración ya conocido (`dd4a0e5e9cf7`, defaults `timestamptz` congelados) y una desviación menor docstring/reloj en `cerrar()`.

---

## Tabla de ítems — `docs/CHECKLIST_ENTREGA.md` §6

| # | Ítem del checklist | Veredicto | Evidencia |
|---|---|---|---|
| 1 | `requiere_rol` consulta `asignacion_rol` en **cada** petición y no confía en el claim `roles` (RN-04) | **PASS** | `parcial/app/core/dependencies.py` `get_sesion_actual` lee `UsuarioRepository.roles_vigentes()` (SQL sobre `asignacion_rol` con `revocada_en IS NULL` y `vence_en > now()`, `repository.py:66-82`) en cada petición; `requiere_rol` compara **solo** `roles_db` (el claim solo informa `/auth/yo`). Evidencia registrada: `EVIDENCIA.md` C-07.4 (403 con la misma cookie tras revocar) y C-07.5 (`roles:[]` vs `roles_token:["VENDEDOR"]`); `test_admin_usuarios_api.py::test_usuarios_alta_vendedor_da_403`. |
| 2 | Revocar un rol quita el permiso a una sesión ya abierta; `vence_en <= now()` no otorga permiso (RN-04, AB-10) | **PASS** | `EVIDENCIA.md` §5 C-07.2→C-07.4 (revocación → 403 inmediato con la cookie ya emitida) y C-07.9→C-07.11 corrida enfocada `manual-c07-vencimiento.txt` (200 antes del vencimiento / 403 después; `/auth/yo` sin el rol). Test `test_clientes_rbac.py::test_rol_revocado_o_vencido_quita_el_acceso_con_la_misma_cookie` (citado en `tasks.md` 8.2). |
| 3 | `vence_en` en el pasado o sin zona horaria → **422**, no 409 | **PASS** | `schemas.py:18-26` (`AwareDatetime` con `AfterValidator(_fecha_con_zona)`) + `schemas.py:151` (`_vence_en_futuro` exige `> now(UTC)`). `EVIDENCIA.md` C-07.7 y C-07.8 (422 con `loc: ["body","vence_en"]`, `value_error`, ambos observados); `test_admin_roles_api.py::test_asignar_rol_vence_en_sin_zona_da_422` y `…_pasado_da_422_no_409`. |
| 4 | Reasignar un rol vencido cierra la fila anterior y abre una nueva; la fila revocada **nunca se borra** (RN-03) | **PASS** | `service.py:342-374` (`asignar_rol`): si `get_abierta` devuelve fila **vencida**, `cerrar()` + `flush` y luego `abrir()` en la misma transacción; `cerrar()` (`repository.py:145`) escribe `revocada_en`, nunca `DELETE`. Índice parcial `uq_asignacion_rol_abierta` (`models.py`) respalda RN-03. `EVIDENCIA.md` C-07.6 (la fila revocada sigue en el historial); tests 3.4 y 5.1 de `tasks.md`. |
| 5 | Un ADMIN no puede revocarse su propio ADMIN y el sistema nunca queda sin administradores vigentes → **409** (RN-05) | **PASS** | `service.py:377-416` (`revocar_rol`): 409 autoprotección (`usuario_id == admin.id and rol == "ADMIN"`) → 409 último ADMIN (`contar_admins_vigentes(excluir_id, bloquear=True) == 0`). `EVIDENCIA.md` C-08.1 (409 «No puede revocar su propio rol de administrador») y C-08.2 (fila sigue vigente). Concurrencia: `test_admin_roles_concurrencia.py` (dos revocaciones simultáneas → `[200, 409]`, queda exactamente 1 ADMIN vigente; corrido 5/5 según `tasks.md` 5.6). |
| 6 | `GET /ventas/{id}` **no** lleva `requiere_rol`: decide el servicio (personal o dueño 200; ajeno 403) | **PASS** *(ítem de C-06/C-13, verificado por código; no es producción de C-15)* | `parcial/app/modules/ventas/router.py:105-112`: solo `Depends(get_sesion_actual)`; la decisión está en `service.obtener(…, actual=sesion)`. `EVIDENCIA.md` C-06.4 (Ana lee **su** venta 200) y C-06.5 (ajena 403). |
| 7 | `/mis-ventas` solo pide estar autenticado y devuelve únicamente las ventas del cliente ligado al usuario; lo ajeno da **403** (RN-14) | **PASS** *(ídem, fuera de la superficie de C-15)* | `ventas/router.py:69-84`: `Depends(get_sesion_actual)`, delega en `service.mis_ventas`. `EVIDENCIA.md` C-06.4/C-06.5. |

## Verificaciones adicionales del brief (alcance C-15)

| Verificación | Veredicto | Evidencia |
|---|---|---|
| Solo ADMIN puede crear usuarios y asignar/revocar roles | **PASS** | `router_admin.py:26` `_solo_admin = requiere_rol("ADMIN")` como `Depends` en **las 5 rutas** (POST `/usuarios/`, GET/POST `/usuarios/{id}/roles`, DELETE `/usuarios/{id}/roles/{rol}`, GET `/eventos/`). En vivo: sin cookie → 401 (`GET /eventos/`, `POST /usuarios/`); vendedor → 403 en `POST /usuarios/`, `GET /usuarios/1/roles`, `GET /eventos/`. |
| Alta de usuario con rol ADMIN inicial | **PASS** | `schemas.py:122` `PersonalCreate.rol: Literal["ADMIN","VENDEDOR"]`; `test_admin_usuarios_api.py::test_usuarios_alta_admin_da_201`; el seed carga `admin2` como ADMIN (`EVIDENCIA.md` §2). Caso de escritura: no ejecutado en vivo (regla de auditoría). |
| Vigencia de asignaciones (`desde`/`vence_en`/`revocada_en`, RN-03/RN-05) | **PASS** | `abrir()` escribe `desde=datetime.now(timezone.utc)` explícito y `vence_en` del DTO (`repository.py:154`); `cerrar()` escribe `revocada_en` (`repository.py:145`); lecturas deciden vigencia con `now()` de PostgreSQL (`get_abierta`, `roles_vigentes`). Columnas `DateTime(timezone=True)` en `models.py`. |
| No se puede revocar el rol del ÚLTIMO admin (409, C-08) | **PASS** | Ítem 5 de la tabla + `test_admin_roles_service.py` (último ADMIN vigente con otro admin autenticado → 409; dos admins → 200; admin vigente + admin vencido → 409) y `test_admin_roles_concurrencia.py`. |
| Auditoría: cada alta/asignación/revocación genera `evento_seguridad` con actor (RN-16) | **PASS** | `service.py:326` (`actor=admin.email, accion="Alta de personal"`), `:370` (`Asignación de rol: {rol}`), `:412` (`Revocación de rol: {rol}`) — dentro del mismo `async with uow` que la escritura. `test_admin_auditoria_api.py::test_alta_asignacion_y_revocacion_auditan_tres_eventos_del_admin` (3 líneas con el email del admin). |
| Rollback atómico de la auditoría (RN-16, §7) | **PASS** | `test_admin_auditoria_api.py::test_fallo_tras_auditoria_revierte_usuario_rol_y_evento`: fallo forzado tras escribir el evento → 0 usuarios, 0 eventos. `UnitOfWork.__aexit__` (`app/core/unit_of_work.py:53-58`): commit sin excepción, rollback con excepción. |
| `GET /eventos/` solo ADMIN | **PASS** | `router_admin.py` (dependencia `_solo_admin`). En vivo: sin cookie → 401; vendedor → 403; admin → 200 con envoltorio `{items,total:1,page:1,size:20,pages:1}`. |
| Claves de eventos con datos clave | **PASS** | `accion` incluye operación + rol («Asignación de rol: CLIENTE», «Revocación de rol: CLIENTE», «Alta de personal»); `actor` = email del admin que ejecuta; item expone `{id, cuando, actor, accion}` (`EventoSeguridadRead`). Observado en vivo: item `SISTEMA / Carga de los datos iniciales`. |
| SQL `FOR UPDATE` al bloquear filas | **PASS** | `repository.py:115-139` `contar_admins_vigentes(bloquear=True)` → `stmt.with_for_update()` sobre **todas** las filas ADMIN vigentes (exclusión del objetivo en memoria); `test_admin_repository_sql.py` compila el SQL y verifica `FOR UPDATE` presente con `True` y ausente con `False`. |
| Sin lógica de negocio en el router | **PASS** | `router_admin.py`: cada handler solo recibe el DTO, obtiene `admin` de la dependencia, construye el UoW (`Depends(get_admin_uow)`) y delega a `service.*`; sin consultas ni ramas de negocio. UoW construido una sola vez por petición (`get_admin_uow`). |
| Grupo protegido con `control_cambio_password` una sola vez | **PASS** | `parcial/main.py:119` `router_protegido = APIRouter(dependencies=[Depends(control_cambio_password)])`; `router_usuarios` y `router_eventos` incluidos ahí; `grep` en `main.py` → 1 sola referencia de montaje. |
| Contratos de entrada (`extra="forbid"`, `Literal`, 73 bytes, NUL) | **PASS** | `schemas.py:122-156` (`PersonalCreate`, `AsignacionRolCreate` con `extra="forbid"`, `SinNulMixin`, `validar_password_bytes`). En vivo (admin): `rol:"CLIENTE"` en alta → 422 `literal_error`; campo extra → 422 `extra_forbidden`; `size=500` en `/eventos/` → 422; usuario inexistente en POST roles → 404. |
| Reglas duras (CV-02, CV-03, sin float, alembic) | **PASS** | `commit(` solo en `core/unit_of_work.py:53` (`__aexit__`) y en `service.py` `registrar_intento_acceso` (autorizado por DD-05); `selectinload` solo en `repository.py` de cada módulo; sin `float` en `app/modules/usuarios/`; `alembic check` → «No new upgrade operations detected». |
| §4 modelo: CHECK rol, índice único parcial, FKs indexadas, timestamptz | **PASS (1 WARN)** | `models.py`: `ck_asignacion_rol_rol` (CHECK `rol IN (...)`), índice parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL`, `usuario_id`/`otorgada_por` con `index=True`, columnas `DateTime(timezone=True)`. WARN: ver H-2 (defaults congelados). |

---

## Hallazgos (por severidad)

### H-1 — WARN · Defecto conocido `dd4a0e5e9cf7`: defaults `timestamptz` congelados (no es FAIL nuevo)

- **Observación:** `psql`: `information_schema.columns` muestra `asignacion_rol.desde`, `evento_seguridad.cuando` e `intento_acceso.cuando` con `column_default = '2026-11-08 12:18:56.115576-03'::timestamp with time zone` — un literal fijo (la migración `dd4a0e5e9cf7` declaró `server_default='now()'` como string y Alembic lo congeló). El evento `SISTEMA` del seed y los eventos que escribe C-15 (`EventoSeguridad(actor=…, accion=…)` sin `cuando` explícito, `service.py:326/370/412`) heredan ese timestamp fijo.
- **Impacto:** `cuando` de `evento_seguridad` no refleja la hora real de la operación (todos los eventos de la app comparten el instante de la migración). El listado `ORDER BY cuando DESC, id DESC` (`repository.py` `listado`) sigue siendo estable gracias al desempate por `id`. `desde`/`revocada_en` de las asignaciones **no** se ven afectadas en la práctica (la app las escribe explícitas), e `intento_acceso` escribe `cuando` explícito (RN-07).
- **Fix propuesto:** nueva migración con `ALTER COLUMN … SET DEFAULT now()` (o `server_default=sa.text("now()")`), o escribir `cuando` explícito al crear eventos (igual que `registrar_intento_acceso`). `alembic check` hoy está limpio porque el literal coincide con el default declarado; tras el fix, re-verificar.

### H-2 — INFO · `cerrar()` usa el reloj del proceso, no `now()` de PostgreSQL

- **Observación:** `repository.py:145-152` `cerrar()` escribe `revocada_en = cuando or datetime.now(timezone.utc)` pese a que su docstring dice «default `now()` del servidor» y el design §3 fija reloj de PostgreSQL para el módulo. `abrir()` también escribe `desde` con reloj Python.
- **Impacto:** nulo funcional (borde de segundos; las decisiones de vigencia usan `now()` de la base). Es inconsistencia documental.
- **Fix propuesto:** corregir el docstring o escribir `revocada_en` con `func.now()` en SQL; unificar el criterio del módulo.

### H-3 — INFO · Casos de escritura no ejecutados en la auditoría

- Por regla del brief, `POST /usuarios/` (201), asignar/revocar rol (201/200/409) y `DELETE` no se ejecutaron contra la DB compartida. Se verificaron por código + tests (`test_admin_*`) + evidencia registrada (`EVIDENCIA.md` §5: C-07/C-08 con 27/27 bloques OK en la pasada httpyac; `tasks.md` 8.1: 417 passed / 0 errors). No es un defecto; se declara como límite de la verificación.

---

## Qué NO se pudo verificar independientemente

1. **`pytest` completo** (prohibido por el brief): se apoya en `tasks.md` 8.1 (417 passed / 0 errors, baseline 413) y en `CHANGES.md` C-19 (459 passed / 1 skipped).
2. **Casos de escritura 201/200/409 en vivo** (alta de personal, asignar/revocar rol, auto-revocación, último ADMIN): verificados solo por código, tests y `EVIDENCIA.md`/`roles.http`.
3. **Pasada REST Client (GUI)**: no disponible en este entorno; existe la pasada manual con httpyac documentada en `EVIDENCIA.md` §9.
4. **Revocación con vencimiento real en vivo** (C-07.11): requiere espera de reloj; se apoya en `manual-c07-vencimiento.txt` y en los tests citados.
5. **Migración `dd4a0e5e` corregida**: no existe aún; el WARN H-1 queda como hallazgo con fix propuesto.

## Conclusión

C-15 cumple §6 del checklist y todas las verificaciones del brief: autorización ADMIN por roles de base en cada petición, RN-03/RN-05 (autoprotección + último administrador + concurrencia con `FOR UPDATE`), RN-16 (auditoría con actor en la misma transacción y rollback atómico) y contratos 422. Veredicto **PASS** con 2 WARN (H-1 defecto conocido `dd4a0e5e`, H-2 desvío documental menor) y sin FAIL.
