# Auditoría — C-12 auto-registro-atomico

- **Fecha:** 2026-11-08
- **Auditor:** subagente auditor (solo lectura; único archivo escrito: este informe)
- **Objeto:** `POST /auth/registro` contra `docs/CHECKLIST_ENTREGA.md` §5, §7 y §10 (caso `C-02`)
- **Fuentes:** CHANGES.md `[C-12]`, `openspec/changes/archive/2026-11-07-c-12-auto-registro-atomico/` (proposal, design, tasks), código en `parcial/app/`, evidencia `parcial/test/registro_http_evidence.md`
- **Veredicto:** **PASS** — 12/12 ítems verificados, 0 FAIL, 0 WARN.

## Método

Ejecución viva con `httpx.ASGITransport` sobre `main.app` (sin uvicorn, sin pytest, sin seed) usando el lifespan real (`app.router.lifespan_context`), contra PostgreSQL 17.11 en `127.0.0.1:5432` (db `libreria`). Solo se dispararon casos **sin escritura** (422 y 409); el 201 y la atomicidad se verificaron por evidencia registrada. Consultas de control vía `psql` (solo SELECT). `alembic check` (solo lectura).

## Tabla de ítems

| # | Ítem (checklist) | Cómo se verificó | Resultado |
|---|---|---|---|
| 1 | §5 — hash bcrypt **antes** de abrir la transacción | `service.registrar`: `hash_password` (línea 200) precede a `async with uow` (línea 208); comentario del servicio lo declara | PASS |
| 2 | §5 — campos que terminan en bcrypt aceptan ≤ 72 bytes; > 72 → **422** | `validar_password_bytes` (>72 bytes → `ValueError` → 422). Vivo: password de 73 bytes → `422` `value_error`, 0 filas escritas. Evidencia: 40 «ñ» (80 bytes) → 422; 72 bytes exactos → 201 (`registro_http_evidence.md` C-02.5/6/7) | PASS |
| 3 | §5 — registro con `rol` extra → 422, sin escribir | Vivo: `{"rol":"ADMIN"}` → `422` `extra_forbidden` ("El campo no está permitido"); `UsuarioCreate` tiene `extra="forbid"`; counts 5/5/3 sin cambios | PASS |
| 4 | §7 — usuario + rol `CLIENTE` + ficha de cliente en **un** `async with uow` | Un único `async with` en `registrar` (línea 208) con `usuarios.add` → `roles.add` (`rol="CLIENTE"`) → `clientes.add`; `RegistroUnitOfWork` compone los tres repositorios sobre la misma sesión | PASS |
| 5 | §7 — forzar fallo en la ficha → `count(usuario)` no crece (rollback de las dos primeras escrituras) | Vivo: 409 cliente-duplicado con ficha existente = fallo forzado en la tercera escritura; `count(usuario)` quedó en 5 (idéntico al baseline) y `count(asignacion_rol)` en 5. Evidencia: `test_registro_atomicidad_no_deja_usuario_ni_rol_tras_el_409` (test_registro_api_db.py:380) y tasks.md 5.5 con PostgreSQL real | PASS |
| 6 | §7 / §0 — ningún repositorio hace `commit()`, sólo `flush()`; el UoW confirma en `__aexit__` y revierte con excepción | `Select-String 'commit\('` sobre `app/modules/*/repository.py` y `app/core/repository.py` → 0 coincidencias. `core/unit_of_work.py`: `commit()` sin excepción / `rollback()` con excepción, `return False` (no suprime) | PASS |
| 7 | §7 — el `except IntegrityError` va **fuera** del bloque `async with` | `service.registrar` líneas 230-231: el `except` cierra el bloque y traduce a `traducir_integrity_error`; el docstring explica que atrapar adentro confirmaría filas parciales | PASS |
| 8 | §10 C-02 — 409 usuario duplicado con mensaje propio, sin filas sueltas | Vivo: `admin@example.com` → `409` `{"detail":"Ya existe un usuario con ese email"}`; counts sin cambios (5/5/3); sin `Set-Cookie`. Mapeo `uq_usuario_email` en `errors.py` | PASS |
| 9 | §10 C-02 — 409 cliente duplicado con mensaje propio **sin apropiarse de la ficha** | Vivo: `lucia@example.com` → `409` `{"detail":"Ya existe un cliente con ese email"}`; `psql`: `cliente.usuario_id` sigue `NULL`, `nombre`/`email` intactos, cero filas `aud-c12%` en usuario/cliente. Mapeo `uq_cliente_email` en `errors.py` | PASS |
| 10 | §5/§10 — 201 sin `Set-Cookie`, sin token, sin `password_hash` | No re-ejecutado (escribiría): verificado por evidencia. `registro_http_evidence.md` C-02.1: 201, `Set-Cookie: []`, cuerpo exacto `{id, email, nombre, activo, debe_cambiar_password}`. `UsuarioRead` no declara `password_hash`; el handler no emite cookie (sin `set_cookie` en `router.registro`) | PASS |
| 11 | §9 — ningún error expone texto interno de la base ni trazas | Mensajes propios de `CONSTRAINTS` (409) y `value_error`/`extra_forbidden` de Pydantic (422); cuerpos vivos confirmados sin nombres de tablas/constraints | PASS |
| 12 | §3 / §1 — sin migraciones nuevas; `alembic check` limpio; ruta en el grupo abierto | `alembic check` → "No new upgrade operations detected." Vivo: los 4 POST sin cookie llegaron al handler (422/409, nunca 401) → ruta pública en el grupo abierto | PASS |

## Observaciones (no bloqueantes)

- El hash bcrypt se calcula también en las rutas de 409 (antes del UoW), coherente con el diseño «hash fuera de la transacción»; no retiene conexión durante bcrypt.
- El router delega todo a `service.registrar` (sin hash, sin lógica de unicidad, sin `async with`, sin cookie) — cumple CV-01.
- La ficha va **última** a propósito (documentado en el docstring) para que el duplicado de cliente ejercite el rollback completo — diseño correcto para el invariante de §7.

## Veredicto

C-12: PASS 12/12 — FAIL 0 — WARN 0. Sin acciones correctivas requeridas.
