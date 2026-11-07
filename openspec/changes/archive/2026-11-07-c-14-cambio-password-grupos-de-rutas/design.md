# Design — C-14 cambio-password-grupos-de-rutas

## Context

Ver `proposal.md` (Why) para la motivación. Estado actual en `parcial/`: `main.py` monta todos los routers como un solo grupo abierto (sin control de cambio obligatorio); `GET /auth/yo` y `POST /auth/login`/`logout`/`registro` ya existen en `app/modules/usuarios/router.py` (C-11, C-12, C-13); `get_usuario_actual` y `requiere_rol` leen de `request.cookies` y comparten la sesión de `get_session` (C-13); el modelo `usuario` ya tiene `password_hash` y `debe_cambiar_password` (C-03); `evento_seguridad` existe con `id, cuando, actor (text), accion` sin FK (C-03). No hay migración nueva porque no cambian tablas ni columnas. La política de diseño visual del proyecto está en `visual_design.mode = off` (ver `.active-orchestrator-state.json` y `design-system/README.md`).

## Goals / Non-Goals

**Goals:**

- `main.py` con dos grupos de rutas: abierto (`/health`, `/auth`, catálogo público) y protegido (todo lo demás).
- El control de cambio obligatorio (`debe_cambiar_password`) montado **una sola vez** a nivel del router protegido.
- `POST /auth/cambiar-password` y `GET /auth/yo` en el grupo abierto pero con sesión obligatoria (`RN-06`).
- Con `debe_cambiar_password = true`: grupo protegido → `403`; `/auth` y públicas siguen funcionando.
- Cambio de contraseña atómico: hash fuera del UoW; dentro de un solo `async with uow`: `password_hash`, `debe_cambiar_password = false`, `evento_seguridad` (`actor = email`) (`RN-16`).
- No emite token nuevo y no rota la cookie (`IN-03`, `DD-07`).
- `EventoSeguridadRepository` con `add()` y listado paginado para que `C-15` lo reutilice.

**Non-Goals:**

- Rotación de cookie, emisión de token nuevo, invalidación de sesiones abiertas (`IN-03`).
- Migración de esquema ni nuevas tablas.
- Alta de personal, asignación/revocación de roles, `GET /usuarios/*`, `GET /eventos` (`C-15`).
- `POST /ventas` transaccional (`C-16`).
- UI / mockups (no hay interfaz).

## Decisions

### 1. Dos grupos de rutas en main.py, control montado una vez

`main.py` declara dos `APIRouter` (o agrupa las `include_router` en dos bloques):

- **Grupo abierto**: `health_router`, `auth_router` (`/auth/*`), y los routers de catálogo público (`editoriales`, `generos`, `autores`, `libros` lecturas). Sin dependencia de cambio obligatorio.
- **Grupo protegido**: `clientes`, `ventas`, y las mutaciones de catálogo/stock (`POST /libros`, `PATCH /libros/{id}`, `DELETE /libros/{id}`, `POST /libros/{id}/reponer`, `GET /libros/{id}/movimientos`), más los routers futuros de `C-15` (`/usuarios/*`, `/eventos`). Lleva **una sola** dependencia `Depends(control_cambio_password)` a nivel de router.

**Razón:** FastAPI suma dependencias y no las resta (`knowledge-base/03_actores_y_roles.md`, §Dos grupos de rutas, un solo control). Si el control se pusiera ruta por ruta, no habría forma de eximir `POST /auth/cambiar-password`, que es justamente la salida del estado pendiente.

**Alternativa descartada:** middleware global que lea `debe_cambiar_password` y responda `403`. Un middleware no distingue limpiamente qué rutas pertenecen al grupo abierto vs protegido sin duplicar la lista de paths, y acoplaría autenticación a la capa de transporte. La dependencia de router es más explícita y testeable.

### 2. Dónde se lee `debe_cambiar_password` en cada petición

Se lee en una **dependencia compartida** `control_cambio_password` que:
1. Depende de `get_usuario_actual` (misma sesión del UoW, una conexión por petición, `CV-01`/C-13).
2. Lee `usuario.debe_cambiar_password` de la entidad ya resuelta (no consulta adicional a la base).
3. Si es `true`, responde `403` con detalle genérico `"No autorizado"`.
4. Si es `false`, devuelve el `Usuario` para que el router lo use si lo necesita.

Se resuelve **antes** de `requiere_rol` en el router protegido, por lo que el orden es: `401` (autenticación, `get_usuario_actual`) → `403` cambio pendiente (control del grupo) → `403` rol (`requiere_rol`) → negocio. Esto respeta la regla dura: `401` lo decide solo `get_usuario_actual`; `403` lo deciden el rol, el cambio pendiente y la propiedad del recurso.

**Razón:** Leer la columna del objeto `usuario` ya cargado no agrega consultas y reutiliza la sesión del UoW (`RN-04`: roles y estado se leen de la base en cada petición). No se usa middleware porque la decisión requiere la sesión de la petición.

**Alternativa descartada:** leer `debe_cambiar_password` en cada endpoint con una consulta directa. Duplicaría la puerta y dejaría rutas sin protección si un endpoint nuevo la olvida.

### 3. Atomicidad del cambio de contraseña (flujo 4 de `07_flujos_principales.md`)

El servicio `cambiar_password(uow, email, password_actual, password_nueva)`:

1. **Fuera del UoW:** `bcrypt.checkpw(actual, usuario.password_hash)` con `to_thread` + semáforo (`BCRYPT_MAX_CONCURRENCY`). Si no coincide → `401` (no escribe `intento_acceso`, no es login).
2. **Fuera del UoW:** `hash_nuevo = bcrypt(nueva)` con `to_thread` + semáforo. Así no se retiene una conexión del pool durante el costo de CPU de bcrypt (`RN-08`, `CV-01`).
3. **Dentro de un solo `async with uow` (tres escrituras, `flush` solo en repositorios):**
   - `usuario.password_hash = hash_nuevo`
   - `usuario.debe_cambiar_password = False`
   - `evento_seguridad_repo.add(EventoSeguridad(actor=email, accion="Cambio de contraseña"))`
4. El `__aexit__` del UoW confirma las tres o revierte las tres (`RN-16`).

**Razón:** El hash bcrypt es costoso y no debe correr dentro de la transacción (mantener abierta una conexión del pool durante cientos de ms). Las tres escrituras de negocio sí son una sola operación atómica: si cualquiera falla, no queda ni el hash nuevo ni la línea de auditoría (`RN-16`).

### 4. Schemas de entrada/salida

- `CambiarPasswordRequest`: `password_actual: str`, `password_nueva: str`, `extra="forbid"`, cada campo validado con `validar_password_bytes` (≤ 72 bytes → `422`).
- `CambiarPasswordResponse`: `{ mensaje: str }` (sin token, sin hash, sin cookie nueva).
- `UsuarioUpdate` ya tiene `debe_cambiar_password` opcional (C-03/C-15 lo usará); no se expone `password_hash` en ningún schema (`CV-07`).

### 5. EventoSeguridadRepository

Nuevo repositorio en `app/modules/usuarios/repository.py`: hereda `BaseRepository[EventoSeguridad]`, expone `add(evento)` (flush, sin commit) y `listado(page, size)` que devuelve `{items, total, page, size, pages}` usando `paginar()` del core (`C-05`). El listado se filtra sin precarga (`selectinload` solo en `repository.py`, `CV-03`). `C-15` lo reutiliza para alta de personal y cambios de rol.

## Risks / Trade-offs

- [El `403` de cambio pendiente ocurre antes del `403` de rol y antes del `404` de recurso] → Se documenta que `CV-08` (404 → 403 → 409 → 422) rige dentro del servicio; la barrera de cambio pendiente es previa y no consulta el recurso, igual que `requiere_rol` en C-13.
- [No rotar la cookie contradice el checklist heredado] → `IN-03` resuelve a favor del PDF: la cookie se mantiene y el estado vive en la base.
- [Hash fuera de la transacción puede dejar un hash nuevo sin `debe_cambiar_password = false` si el UoW falla] → El hash se tira si el UoW revierte; el usuario sigue con `debe_cambiar_password = true` y puede reintentar. No hay inconsistencia visible.
- [Leer `debe_cambiar_password` del objeto `usuario` resuelto por `get_usuario_actual` acopla el control al modelo de usuario] → Aceptado: es la columna que ya se carga y no agrega consultas.

## Migration Plan

No hay migración de base ni cambio de esquema (`usuario.debe_cambiar_password` y `evento_seguridad` ya existen desde C-03). Al implementar no se toca Alembic; `alembic check` debe seguir limpio. El rollback consiste en retirar la dependencia del router protegido, el endpoint `/auth/cambiar-password` y `EventoSeguridadRepository`, restaurando el estado de C-13; no hay datos que revertir. No se modifican variables de entorno ni secretos.

## Open Questions

Ninguna. El alcance queda fijado por el proposal y los specs; `C-15` consumirá `EventoSeguridadRepository` sin cambios de contrato en este change.

## UI Mockups

- Decision: no (no UI)
- Fecha: 2026-11-06
- Motivo: el proyecto es API pura (sin UI/screens); la política del proyecto es `visual_design.mode = off`, por lo que no aplica el gate de mockups (`design-system` skill). La API no tiene pantallas ni componentes visuales que maquetar.
