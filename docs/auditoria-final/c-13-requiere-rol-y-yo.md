# Auditoría final — C-13 `requiere-rol-y-yo` vs `docs/CHECKLIST_ENTREGA.md` §6 Autorización

- **Change auditado:** `openspec/changes/archive/2026-11-06-c-13-requiere-rol-y-yo/` (proposal, design, tasks, specs leídos).
- **Sección del checklist:** §6 completa (7 ítems) + lo que aplica de §5 (`/auth/yo`, claim del JWT, 401 uniforme) y §7 (misma sesión por petición).
- **Fecha:** 2026-11-08.
- **Método:** auditoría SOLO LECTURA. API probada en vivo con `httpx.ASGITransport` in-process (sin uvicorn), tokens reales de login y tokens forjados con `JWT_SECRET` local; `psql` solo SELECT; `alembic check` ejecutado. Sin pytest (regla de auditoría compartida), sin seed, sin escrituras a la base. Los logins de prueba escribieron filas en `intento_acceso` (permitido).
- **Nota de contexto:** el working tree incluye cambios posteriores a C-13 (C-14 grupos de rutas + `control_cambio_password`, C-15 admin de roles, C-16 `POST /ventas`). No alteran el juicio: se audita lo que C-13 comprometió.

## Veredicto global: **PASS** (13 PASS · 2 WARN · 0 FAIL)

---

## Tabla de verificación

| Ítem (checklist §) | Veredicto | Evidencia |
|---|---|---|
| §6.1 `requiere_rol` consulta `asignacion_rol` en cada petición y no confía en el claim `roles` | **PASS** ⚠ver nota M-1 | Código: `parcial/app/core/dependencies.py:105-112` (`requiere_rol` compara sólo `roles_db`) y `parcial/app/modules/usuarios/repository.py:57-76` (`roles_vigentes`: `revocada_en IS NULL AND (vence_en IS NULL OR vence_en > func.now())`). Vivo: token forjado para ana con claim `roles=["ADMIN"]` → `GET /libros/1/movimientos` **403** y `GET /clientes/3/ventas` **403**; token para admin con claim `roles=[]` → `GET /clientes/3/ventas` **200** (la base otorga). |
| §6.2 Revocación quita el permiso a una sesión ya abierta; `vence_en <= now()` no otorga | **PASS** (no re-ejecutado en vivo: requiere escritura) | Tests como evidencia: `parcial/tests/test_role_authorization.py` `test_requiere_rol_deniega_un_rol_revocado_con_la_misma_cookie` y `test_requiere_rol_deniega_un_rol_vencido`; `parcial/tests/test_clientes_rbac.py` `test_rol_revocado_o_vencido_quita_el_acceso_con_la_misma_cookie` (403, misma cookie). Evidencia registrada: `parcial/test/EVIDENCIA.md` C-07.2→07.5 (misma cookie: pública 200, ruta ADMIN 403, `/auth/yo` `roles: []` vs `roles_token: ["VENDEDOR"]`) y C-07.11 con vencimiento real `now+3 s` (200 antes, 403 después, captura `test/evidencia/manual-c07-vencimiento.txt`). |
| §6.3 Vencimiento en el pasado o sin zona horaria → **422**, no 409 | **PASS** (no re-ejecutado en vivo) | Código: `parcial/app/modules/usuarios/schemas.py` — `AwareDatetime` (AfterValidator rechaza naive) y `AsignacionRolCreate._vence_en_futuro` (pasado → `ValueError` → 422). Evidencia: `EVIDENCIA.md` C-07.7/C-07.8 → 422 `loc: ["body","vence_en"]`, `value_error`; `parcial/test/roles.http` C-07.7/C-07.8. |
| §6.4 Reasignar un rol vencido cierra la fila anterior y abre una nueva; la revocada **nunca se borra** | **PASS** | Código: `parcial/app/modules/usuarios/service.py` `asignar_rol` (abierta no vigente → `cerrar` + `abrir` en la misma transacción) y `parcial/app/modules/usuarios/repository.py` `cerrar()` (escribe `revocada_en`, nunca `delete`). Evidencia: `EVIDENCIA.md` C-07.6 (fila revocada visible con `revocada_en`) y nota final «Ninguna se borró (RN-05)». |
| §6.5 Un ADMIN no se revoca su propio ADMIN y nunca quedan 0 administradores → **409** | **PASS** | Código: `service.revocar_rol` — propio ADMIN → 409 «No puede revocar su propio rol de administrador»; `contar_admins_vigentes(excluir_id, bloquear=True) == 0` → 409 «No se puede revocar el último administrador vigente». Evidencia: `EVIDENCIA.md` C-08.1 → 409 y C-08.2 fila ADMIN intacta; `roles.http` C-08.1/C-08.2. |
| §6.6 `GET /ventas/{id}` **no** lleva `requiere_rol`: decide el servicio (personal o dueño 200; ajeno 403) | **PASS** | Código: `parcial/app/modules/ventas/router.py` `obtener_venta` usa `get_sesion_actual` (sin `_solo_personal`); `parcial/app/modules/ventas/service.py` `obtener()` decide `_es_personal` / dueño y responde 403. Vivo: `admin GET /ventas/1` **200**, `vendedor GET /ventas/1` **200**, `ana GET /ventas/1` (ajena) **403** «No autorizado». Tests: `test_ventas_authorization.py` (dueño 200, ajeno 403, inexistente 404 para cualquier sesión). |
| §6.7 `/mis-ventas` sólo pide sesión y devuelve únicamente las ventas del cliente ligado; ajeno 403 | **PASS** | Vivo: `GET /ventas/mis-ventas` sin cookie **401**; `ana` **200** con `items` solo de `cliente_id` propio (0 en seed); `vendedor` sin ficha **200** página vacía `{items:[],total:0,page:1,size:20,pages:1}`. Tests: `test_mis_ventas_devuelve_solo_las_ventas_propias` y `test_mis_ventas_sin_ficha_de_cliente_devuelve_pagina_vacia`. El 403 «ajeno» de C-06 lo verifica `GET /ventas/1` con ana (véase fila anterior). |
| §5 `GET /auth/yo`: usuario sin `password_hash`, roles vigentes de la base y roles del token | **PASS** | Vivo: `ana GET /auth/yo` **200** `{usuario:{id,email,nombre,activo,debe_cambiar_password}, roles:["CLIENTE"], roles_token:["CLIENTE"]}` (sin `password_hash` ni token); con token forjado `roles=["ADMIN"]` → `roles:["CLIENTE"]`, `roles_token:["ADMIN"]` (diferencia visible). Sin cookie **401**. Código: `usuarios/router.py` `/yo` + `schemas.py` `YoResponse`/`UsuarioRead`. |
| §5 El JWT lleva `sub`, `exp` y los roles vigentes al emitirlo | **PASS** | Vivo: token de login de ana decodificado (sin verificar firma): `{sub:"4", exp:<future>, roles:["CLIENTE"]}`. Emisión en `usuarios/service.py` `autenticar` (roles de `roles_vigentes` antes de `create_access_token`). |
| §5 401 uniforme: sin cookie, token inválido/vencido, usuario inexistente/inactivo; `Authorization` no sustituye la cookie | **PASS** | Vivo: `GET /clientes/3/ventas` sin cookie **401**; token vencido **401**; token con `sub` inexistente **401**; `Authorization: Bearer <token admin válido>` sin cookie **401**. Todos con cuerpo `{"detail":"No autenticado"}`. (Usuario inactivo: cubierto por `test_sesion_actual_rechaza_usuario_inexistente_e_inactivo`.) |
| §7 Dependencias de identidad y de rol usan la **misma sesión** que el UoW (una conexión por petición) | **PASS** | `parcial/tests/test_session_sharing.py`: contador sobre `get_session` → `llamadas == 1`, misma instancia de `AsyncSession` para `UsuarioRepository` (identidad+roles) y `ClienteRepository` (UoW), `cerradas == 1`. Código: `get_sesion_actual`, `requiere_rol` y cada `get_*_uow` dependen del mismo callable `get_session` (`dependencies.py`, `database.py`). |
| Matriz catálogo: mutaciones y stock sólo **ADMIN**; lecturas públicas sin cookie | **PASS** | Código: `libros/router.py`, `editoriales/router.py`, `generos/router.py`, `autores/router.py` — `router_admin` con `_solo_admin = requiere_rol("ADMIN")` en POST/PATCH/DELETE/reponer/movimientos; lecturas en el router público. Vivo: `GET /libros/1` sin cookie **200**; `ana POST /libros/` **403**; `vendedor POST /libros/` **403**; `vendedor/ana GET /libros/1/movimientos` **403**; `admin GET /libros/1/movimientos` **200**. Tests: `test_catalogo_rbac.py`. |
| Matriz clientes: rutas de clientes VENDEDOR/ADMIN + cierre de C-07 (`GET /clientes/{id}/ventas` 401/403/200) | **PASS** | Código: `clientes/router.py` `_solo_personal = requiere_rol("VENDEDOR","ADMIN")` en las 5 rutas; `service.ventas_de(..., actual=sesion)` con `actual` obligatorio. Vivo: sin cookie **401**; `ana` **403**; `vendedor` **200** con envoltorio `{total,page,size,pages}`; `vendedor GET /clientes/999999` **404**; `ana GET /clientes/999999/ventas` **403** (la barrera de rol precede al 404 → el 403 no ejecuta la consulta). Tests: `test_clientes_rbac.py` (incluye `test_el_403_de_cliente_no_ejecuta_la_consulta_de_ventas`, `llamadas == 0`). |
| Defecto conocido `dd4a0e5e9cf7` (defaults `timestamptz` congelados `server_default='now()'` literal) | **WARN** (conocido, no FAIL nuevo) | `migrations/versions/dd4a0e5e9cf7_acceso_y_stock.py:40,47,68,87` y `0ba1752f7c23_0001_initial_tp_baseline.py:71`. Afecta `intento_acceso.cuando`, `evento_seguridad.cuando`, `asignacion_rol.desde`, `venta.fecha`. Los flujos de C-13 escriben `desde`/`vence_en`/`revocada_en` explícitamente (seed, `abrir`, `cerrar`) → sin impacto en lo auditado. |

Conteo: **PASS 13 · WARN 2 · FAIL 0**. (El WARN «checklist §6.1» se cuenta en hallazgo M-1, no como ítem propio de la tabla.)

---

## Hallazgos por severidad

**Blocker:** ninguno.

**Major:** ninguno.

**Minor:**

- **M-1 — Comando de verificación de §6.1 desactualizado.** El checklist pide `grep -n "AsignacionRol" app/core/dependencies.py` y el archivo **no contiene** el literal: la consulta vive en `UsuarioRepository.roles_vigentes` (`app/modules/usuarios/repository.py:57`), y `dependencies.py` la invoca por nombre (`get_sesion_actual`, línea 96). El grep corre pero produce salida vacía, y el checklist dice que un ítem cuyo comando no da el resultado esperado «no está cumplido». La conducta exigida está **verificada funcionalmente** (token que miente → 403; base que otorga → 200). **Fix propuesto:** actualizar el comando del checklist a `grep -n "roles_vigentes" app/core/dependencies.py` + `grep -n "AsignacionRol" app/modules/usuarios/repository.py` (o agregar un comentario en `dependencies.py` que nombre `AsignacionRol` sin cambiar la conducta).
- **M-2 — `/ventas/{id}` y `/mis-ventas` quedan dentro del grupo protegido (C-14).** Con `debe_cambiar_password = true`, `control_cambio_password` responde 403 antes de la decisión de propiedad (`main.py` monta `ventas_router` en `router_protegido`; verificado en vivo con `nuevo@`: `GET /clientes/3/ventas` → 403 y `/auth/yo` → 200). Es el diseño de C-14/RN-06, **no** un defecto de C-13; anotado para que un corrector no confunda el 403 de cambio obligatorio con un 403 de rol en `GET /ventas/{id}`.
- **M-3 — Dueño-200 de `GET /ventas/{id}` no reproducible en vivo sin escribir.** En el seed, Ana (única cliente con `usuario_id`) no posee ventas; crearle una venta sería escritura. Cubierto por `test_dueno_consulta_su_venta_sin_rol_de_personal` y `EVIDENCIA.md` C-06.4. **Fix propuesto:** ninguno de código; opcionalmente verificar en la pasada con REST Client tras `python seed.py` (roles.http C-06.3/06.4).
- **M-4 — Escenarios de escritura no ejecutados contra la DB compartida (regla de auditoría).** Revocación en vivo, vencimiento real 200→403, reasignación de rol vencido, 422 de `vence_en`, 409 de autoprotección, y 201/204 de mutaciones se verificaron por código + evidencia registrada (`tasks.md` todo `[x]`, `parcial/test/roles.http`, `parcial/test/EVIDENCIA.md` §5 con corrida equivalente 2026-11-08, y los tests de `parcial/tests/`). No se marcó ningún ítem PASS apoyado únicamente en código sin evidencia registrada o prueba.

---

## Qué NO se pudo verificar de forma independiente

1. Revocación de rol con la misma cookie abierta, en vivo (requiere `DELETE /usuarios/{id}/roles/{rol}` → escritura). Verificado por código + tests + `EVIDENCIA.md`.
2. Vencimiento real `200 → 403` en vivo (requiere asignar `vence_en`). Verificado por tests + `EVIDENCIA.md` C-07.11 (`manual-c07-vencimiento.txt`).
3. Dueño-200 de `GET /ventas/{id}` en vivo (ver M-3).
4. Casos 201/204/409 de las mutaciones de catálogo y de clientes (escritura).
5. `pytest` completo no ejecutado (regla: otros auditores usan la misma DB); los tests se leyeron como evidencia.
6. `alembic check` sí ejecutado: **«No new upgrade operations detected»** — sin migraciones ni cambios de esquema pendientes, consistente con «sin migraciones nuevas» de C-13.

## Cierre del flujo

`CHANGES.md` refleja C-13 `[x]` archivado y C-07 `[x]` cerrado por C-13 (líneas 396 y 598); `tasks.md` del change con las 5 secciones en `[x]`. Sin hallazgos que bloqueen el archive.
