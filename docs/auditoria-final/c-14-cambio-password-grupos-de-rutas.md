# Auditoría final — C-14 `cambio-password-grupos-de-rutas`

- **Change auditado:** `openspec/changes/archive/2026-11-07-c-14-cambio-password-grupos-de-rutas/` (archivado)
- **Secciones del checklist:** `docs/CHECKLIST_ENTREGA.md` §5 Autenticación y §6 Autorización (ítems relevantes a C-14 + consistencia transversal de grupos)
- **Fecha:** 2026-11-08
- **Método:** solo lectura. Código + spec + tests leídos sin ejecutar; API en vivo con `httpx.ASGITransport` in-process (sin uvicorn); `psql` solo SELECT; `alembic check`. Casos de escritura (cambio exitoso) verificados por código + evidencia registrada, no ejecutados contra la DB compartida.
- **Alcance:** C-14 + los ítems de §5/§6 cuya lógica intersecta el change. Ítems de §5/§6 propios de otros changes (C-03…C-08, C-11) se auditan solo por código/evidencia registrada y se marcan como tales.

## Veredicto global: **PASS**

Ningún FAIL. 20 PASS, 2 WARN (documentales, sin impacto funcional).

## Tabla de ítems

### §5 Autenticación

| Ítem | Veredicto | Evidencia |
|---|---|---|
| 5.1 bcrypt con costo desde `Settings`, bajo `to_thread` + semáforo | **PASS** | `app/core/security.py:33-59` (`hash_password`/`verify_password`: `asyncio.to_thread` + `async with semaphore`); costo: `usuarios/router.py:129-130` pasa `settings.BCRYPT_ROUNDS`; semáforo creado en `main.py:63` (`BCRYPT_MAX_CONCURRENCY`). No hay `gensalt` con costo fijo. |
| 5.2 Hash calculado **antes** de abrir la transacción | **PASS** | `usuarios/service.py:255-270` (cambio): lectura en UoW → `verify_password` y `hash_password` **fuera** del `async with uow` → escritura en `273-279`. Registro idem `service.py:200-208`. Test `test_cambio_password_service.py:63-102` (2 aperturas de UoW, hash fuera). |
| 5.3 Todo campo bcrypt acepta ≤ 72 bytes → 422 (no 500) | **PASS** | `usuarios/schemas.py:103-113` valida `password_actual` y `password_nueva`; `app/core/errors.py:247-251` mide `len(value.encode("utf-8")) > 72` (multibyte correcto). En vivo (cookie `nuevo@` con cambio pendiente): `POST /auth/cambiar-password` con nueva de 73 bytes → **422** `loc:["body","password_nueva"]`; campo extra → **422** `extra_forbidden`; sin `password_nueva` → **422**. Tests `test_cambio_password_schemas.py:30-52` (73 y 72 bytes exactos). |
| 5.4 Login no devuelve token en cuerpo; solo `Set-Cookie` HttpOnly + SameSite | **PASS** | `LoginResponse` solo `{mensaje, debe_cambiar_password, expira_en_segundos}` (`schemas.py:87-92`); cookie en `app/core/security.py:92-108` (`httponly=True, samesite="lax", secure=settings`). En vivo login `nuevo@` → 200 sin token en cuerpo, cookie presente. |
| 5.5 JWT con `sub`/`exp`/roles; `exp` lo valida PyJWT; sin comparación con `iat` | **PASS** | `security.py:62-78` (emite `sub`, `exp`, `roles`; sin `iat`); `security.py:81-89` `jwt.decode` con `options={"require":["sub","exp"]}`; `dependencies.py:74-77` no compara `iat`. |
| 5.6 Límite de intentos **antes** de verificar credenciales; 6.º fallo → 429 + `Retry-After` ms | **PASS** | `usuarios/service.py:125-148`: `resumen_fallos` corre antes de `get_by_email`/bcrypt; `Retry-After` en ms (`_retry_after_ms`, `service.py:55-69`). No re-ejecutado en vivo (evita bloquear `nuevo@`; pertenece a C-05). Evidencia registrada: `parcial/test/` de C-05. |
| 5.7 Login correcto reinicia la cuenta de fallos | **PASS** | `usuarios/repository.py:191-211`: solo cuentan fallos `cuando > coalesce(max(exito), época)`. |
| 5.8 Respuesta y tiempo iguales exista o no el correo (hash ficticio) | **PASS** | `main.py:67-72` (hash ficticio en `lifespan`, `to_thread`); `service.py:46-52,150` lo usa cuando no hay usuario. En vivo login inexistente `audit-c14@example.com` → **401** `{"detail":"Credenciales inválidas"}`, mismo cuerpo que credenciales malas. |
| 5.9 `GET /auth/yo` devuelve usuario, roles vigentes y claim | **PASS** | `usuarios/router.py:99-108`; roles de base en `dependencies.py:96-107`. En vivo (cambio pendiente): **200** `roles:["VENDEDOR"]`, `roles_token:["VENDEDOR"]`, sin hash. |
| 5.10 `POST /auth/logout` borra cookie (`Max-Age=0`) → siguiente petición 401 | **PASS** | `security.py:111-122`; en vivo: `logout` → `Set-Cookie: access_token=…; Max-Age=0; HttpOnly; Path=/; SameSite=lax`, `GET /auth/yo` siguiente → **401** «No autenticado». |
| 5.11 `POST /auth/cambiar-password` no emite token nuevo, no rota la cookie, `debe_cambiar_password=false` | **PASS** | Código: `router.py:111-132` devuelve solo `CambiarPasswordResponse` (`schemas.py:116-119`, solo `mensaje`); `service.py:273-279` escribe hash + `False` + evento en un UoW; ningún `set_cookie`. Test `test_cambio_password_api.py:104-138` (no `Set-Cookie` con `access_token=`; flag en `False`; evento `actor=email`). Evidencia real registrada: `parcial/test/EVIDENCIA.md` C-09.4 (200 «Contraseña actualizada») y C-09.5 (**misma cookie** → 200 en grupo protegido); `parcial/test/roles.http:303-350`. *No re-ejecutado en vivo: es la escritura prohibida contra la DB compartida.* |
| 5.12 Con `debe_cambiar_password=true`: grupo protegido 403, solo pasan `/auth` y abiertas | **PASS** | En vivo con cookie de `nuevo@` (`debe_cambiar_password=true`): `GET /ventas/mis-ventas`, `/clientes/1`, `/ventas/1` → **403** «No autorizado»; `GET /auth/yo` → **200**; `GET /libros/1`, `/editoriales/1`, `/health/live` → **200**; `POST /auth/cambiar-password` (73 bytes) alcanza validación → **422** (la ruta está exenta del control). Control: `dependencies.py:133-145`; montado una única vez en `main.py:119`. |

### §6 Autorización

| Ítem | Veredicto | Evidencia |
|---|---|---|
| 6.1 `requiere_rol` consulta `asignacion_rol` en **cada** petición, no confía en claim | **PASS** | `dependencies.py:96-107`: `get_sesion_actual` llama `roles_vigentes(usuario.id)` por petición (`repository.py:56-71`, SQL con `revocada_en IS NULL` y `vence_en > now()`); `requiere_rol` decide solo con `roles_db` (`dependencies.py:122-128`). En vivo `/auth/yo` leyó roles frescos de base. |
| 6.2 Revocar quita permiso a sesión abierta; `vence_en <= now()` no otorga | **PASS** | Mismo mecanismo que 6.1 (roles releídos por petición). Evidencia registrada: `EVIDENCIA.md` C-07.2→7.4 (misma cookie pierde permiso), C-07.10/7.11 (rol vencido: 200 antes, 403 después). |
| 6.3 `vence_en` pasado o sin zona → 422 | **PASS** | `schemas.py:142-154` (`AwareDatetime`, futuro requerido). Evidencia: `EVIDENCIA.md` C-07.7/7.8 (422 en ambos). |
| 6.4 Reasignar rol vencido cierra fila y abre nueva; revocada nunca se borra | **PASS** | `service.py:342-372` (`cerrar` + `abrir` en misma transacción); `repository.py:145-152` (`cerrar` escribe `revocada_en`, no borra). Evidencia: `EVIDENCIA.md` C-07.6 (fila revocada visible en historial). |
| 6.5 ADMIN no puede revocarse su propio ADMIN; nunca sin administradores → 409 | **PASS** | `service.py:399-408`; evidencia `EVIDENCIA.md` C-08.1/8.2 (409, fila vigente). |
| 6.6 `GET /ventas/{id}` **sin** `requiere_rol`: decide el servicio (personal/dueño 200, ajeno 403) | **PASS** | Enumeración in-process de `main.app` (42 rutas): `/ventas/{venta_id}` solo con `get_sesion_actual`, sin dependencia de rol; decisión en `ventas/service.py:47-63` (personal o `cliente.id == venta.cliente_id`, si no → 403). Evidencia: `EVIDENCIA.md` C-06.4/6.5. |
| 6.7 `/mis-ventas` solo autenticado y solo ventas del cliente ligado; ajeno 403 | **PASS** | Enumeración: `/ventas/mis-ventas` solo `get_sesion_actual`; `ventas/service.py:66-82` filtra por `clientes.get_by_usuario_id`. Evidencia: `EVIDENCIA.md` C-06.4 y C-09.5 (200 envoltorio de Ana). |

### Consistencia de grupos de rutas (objetivo propio de C-14)

| Verificación | Veredicto | Evidencia |
|---|---|---|
| `control_cambio_password` montado **una sola vez**, a nivel de router | **PASS** | `main.py:119` única referencia de montaje (`router_protegido = APIRouter(dependencies=[Depends(control_cambio_password)])`); `grep -rn "control_cambio_password" parcial/` solo en `main.py`, `dependencies.py` y tests. |
| No hay rutas protegidas fuera del grupo | **PASS** | `grep -rn "include_router" parcial/` → solo en `main.py` (dos grupos). Enumeración in-process de 42 rutas: abiertas (health, auth, GET catálogo) sin dependencia de control; protegidas (clientes, ventas, usuarios, eventos, mutaciones de catálogo) bajo el router con control. |
| `/auth/*` exento del control | **PASS** | `main.py:98-114` (auth en `router_abierto`); en vivo `GET /auth/yo` y validación de `cambiar-password` funcionan con bandera en `true` (5.12). |
| Consistencia con specs principales | **PASS** | `openspec/specs/grupos-de-rutas/spec.md` (montaje único, 403, exención de `/auth`) y `openspec/specs/cambio-password/spec.md` (hash fuera de transacción, 3 escrituras, cookie no rota) coinciden 1:1 con la implementación verificada. |
| Migraciones coherentes | **PASS** | `python -m alembic check` → «No new upgrade operations detected.», exit 0. |

## Hallazgos

1. **[WARN — documental]** `tasks.md` 7.1/8.2 describen `test_cambio_password_api.py` como corrido «contra PostgreSQL 17 real», pero el archivo declara «sin PostgreSQL» y usa `Mock`/`dependency_overrides` (`tests/test_cambio_password_api.py:1,47-101`). La verificación real contra PostgreSQL existe en `parcial/test/EVIDENCIA.md` §C-09 (corrida `.http`-equivalente); solo la redacción de tasks es imprecisa. Fix: corregir la trazabilidad en el change archivado o aceptar la nota.
2. **[WARN — menor]** `tests/test_control_cambio_password.py:35-38` es un test con solo `pass`: documenta el orden 401→403 sin assertear nada. Fix: convertirlo en un test real (p. ej. mock de `get_usuario_actual` que lance 401 y verificar que el control no se ejecuta).
3. **[INFO]** Defecto conocido `dd4a0e5e9cf7` (defaults `timestamptz` congelados): **no aplica a C-14** — los modelos de `usuarios` usan `server_default="now()"` (`models.py:90,130,147`), sin default Python congelado.
4. **[INFO]** Petición sin cookie con cuerpo inválido responde 422 antes que 401 (validación de cuerpo precede a la dependencia de sesión en FastAPI). Comportamiento estándar y fuera del contrato §5 (que exige 401 para peticiones válidas sin cookie — verificado en vivo: `/ventas/mis-ventas` y `/auth/yo` sin cookie → 401).

## No verificado independientemente (y por qué)

- **Escritura exitosa de `cambiar-password`** (hash nuevo + `debe_cambiar_password=false` + fila de `evento_seguridad`, y misma cookie entrando al grupo protegido tras el cambio): es la única operación de escritura del change; por regla de auditoría no se ejecuta contra la DB compartida. Verificado por código (`service.py:236-279`), tests (`test_cambio_password_api.py`, `test_cambio_password_service.py`) y evidencia registrada (`EVIDENCIA.md` C-09.4/C-09.5, `roles.http` C-09). La DB actual fue re-sembrada (única fila de `evento_seguridad` es «Carga de los datos iniciales»), por lo que no hay fila de evento C-09 que corroborar hoy por SELECT.
- **429/`Retry-After` del login** (ítem 5.6): no re-ejecutado para no contaminar el límite de intentos de `nuevo@`; es alcance de C-05, verificado por código y evidencia de C-05.
- **Ejecución de la suite pytest** (172 passed según `tasks.md` 8.1): prohibida por regla (otros auditores sobre la misma DB); no se re-corrió. Los tests se leyeron y su lógica es consistente con lo observado.
