# Proposal — C-15 admin-usuarios-roles-eventos

## Why

La autorización ya funciona por rol vigente en la base (C-13) y el cambio obligatorio de contraseña con su auditoría está cerrado (C-14), pero el sistema todavía no tiene la superficie de administración: no se puede dar de alta personal con contraseña provisoria, no se pueden otorgar ni revocar roles con historial, y no hay forma de consultar el `evento_seguridad` que C-14 empezó a escribir. Sin esto, `C-17` (seed) no tiene las reglas de negocio validadas y los casos `C-07`/`C-08` del parcial —revocar un rol con la sesión abierta y la autoprotección del administrador— quedan sin implementación.

Además, al verificar el estado real contra el `design.md` de C-14 aparecieron dos deudas concretas que bloquean o degradan este change: los routers de catálogo quedaron **enteros** en el grupo abierto, así que sus mutaciones `ADMIN` no pasan por `control_cambio_password`; y `EventoSeguridadRepository.listado` está anotado con `Pagina`, pero el módulo no importa ese nombre, por lo que importar `usuarios/repository.py` falla con `NameError` (verificado con `py -3.12`).

## What Changes

- `POST /usuarios` (`ADMIN`, grupo protegido) → **201**: alta de personal con contraseña provisoria. El hash bcrypt se calcula **fuera** del UoW (`to_thread` + semáforo); dentro de **un solo** UoW: `usuario` (`debe_cambiar_password = true`), `asignacion_rol` inicial y la línea de `evento_seguridad` con `actor = email` del admin (`RN-16`). Correo repetido → **409**; `rol` fuera de `{ADMIN, VENDEDOR}` o campos de más → **422** (`SU-02`).
- `POST /usuarios/{id}/roles` (`ADMIN`) → **201**: `vence_en` opcional, **con zona horaria** y en el **futuro** (sin zona o en el pasado → **422**, no 409; `rol` fuera del `CHECK` → 422; usuario inexistente → **404**). Segunda asignación **abierta** del mismo rol → **409** (índice único parcial `uq_asignacion_rol_abierta`, `RN-03`). Reasignar un rol **vencido** cierra la fila anterior (`revocada_en = now()`) y abre la nueva **en la misma transacción**. `otorgada_por` = admin que otorga.
- `DELETE /usuarios/{id}/roles/{rol}` (`ADMIN`) → **200** con la asignación ya revocada (`SU-12`): escribe `revocada_en`, **la fila no se borra nunca**. Rol nunca asignado → **404**; fila ya revocada → **409**. `RN-05` en el servicio: revocar el **propio** `ADMIN` → **409**; revocar el **último** `ADMIN` vigente → **409**, aunque lo haga otro administrador.
- `GET /usuarios/{id}/roles` (`ADMIN`) → **200** con el historial completo (vigentes, vencidas y revocadas), ordenado por `desde` descendente; usuario inexistente → **404**.
- `GET /eventos?page=&size=` (`ADMIN`) → **200** con el envoltorio canónico `{items, total, page, size, pages}` (`DD-18`), ítems `{id, cuando, actor, accion}`; `size` fuera de 1..100 → **422**, página fuera de rango → **422**.
- Cada operación de escritura deja su línea de auditoría en `evento_seguridad` **dentro del mismo UoW** del cambio, con `actor` = email del admin (`RN-16`).
- **Corrección de C-14 (deuda de montaje)**: las mutaciones `ADMIN` del catálogo (`POST`/`PATCH` de editoriales, géneros y autores; `POST`/`PATCH`/`DELETE`, `reponer` y `movimientos` de libros) pasan al **grupo protegido**, de modo que `control_cambio_password` también las alcanza. Las lecturas públicas del catálogo siguen en el grupo abierto, sin sesión.
- **Prerequisito técnico**: reparar el import faltante de `Pagina` en `parcial/app/modules/usuarios/repository.py` (bloquea cualquier `GET /eventos` y el propio import del módulo).

## Capabilities

### New Capabilities

- `alta-de-personal`: contrato de `POST /usuarios` (201, email normalizado y único con 409, `rol` inicial `ADMIN`/`VENDEDOR` con 422 si no, `debe_cambiar_password = true`, hash bcrypt fuera del UoW, `usuario` + `asignacion_rol` + `evento_seguridad` en la misma transacción, 401 sin sesión y 403 sin rol `ADMIN`).
- `roles-de-usuario`: contrato de `GET`/`POST /usuarios/{id}/roles` y `DELETE /usuarios/{id}/roles/{rol}` (201, 200, 404, 409; `vence_en` con zona y futuro → 422; reasignación de una fila vencida que cierra y abre; la fila revocada nunca se borra; `RN-05` con 409 por autoprotección y por último administrador; auditoría en la misma transacción).
- `eventos-seguridad`: contrato de `GET /eventos` (200 con envoltorio paginado, `actor` puede ser `'SISTEMA'`, `size` 1..100 → 422, página fuera de rango → 422, orden más reciente primero, 403 sin rol `ADMIN`).

### Modified Capabilities

- `grupos-de-rutas`: el grupo abierto deja de contener «todo el catálogo» y pasa a contener solo las **lecturas** públicas; las mutaciones `ADMIN` de catálogo se montan en el grupo protegido y quedan sujetas a `control_cambio_password`. El requisito de montaje único del control y el de 403 por cambio pendiente no cambian.

## Impact

- Código:
  - `parcial/main.py`: montar `/usuarios/*` y `/eventos` en el grupo protegido; mover los routers de mutación de catálogo al grupo protegido (split de routers por módulo).
  - `parcial/app/modules/usuarios/`: `schemas.py` (schemas de alta de personal, asignación y evento), `repository.py` (import de `Pagina`; `get_abierta`, `listar_por_usuario`, `contar_admins_vigentes`), `service.py` (alta, asignar, revocar, listar), `router_admin.py` (nuevo: `/usuarios` y `/eventos`), `unit_of_work.py` (`AdminUnitOfWork` + dependencia).
  - `parcial/app/modules/{editoriales,generos,autores,libros}/router.py`: separar routers público y de administración sin cambiar paths ni tags.
- API: cinco rutas nuevas (`POST /usuarios`, `GET|POST /usuarios/{id}/roles`, `DELETE /usuarios/{id}/roles/{rol}`, `GET /eventos`), todas en el grupo protegido con `requiere_rol("ADMIN")`. Ninguna ruta existente cambia de path ni de contrato; el catálogo público tampoco.
- Datos: **sin migración**. `usuario`, `asignacion_rol` (con `uq_asignacion_rol_abierta` y `ck_asignacion_rol_rol`) y `evento_seguridad` ya existen desde C-03/C-04; `alembic check` debe seguir limpio. `errors.py` ya mapea `uq_asignacion_rol_abierta` a 409 y `ck_asignacion_rol_rol` a 422.
- Pruebas: unitarias de schemas, repositorio y servicio con UoW fake (TDD), integración contra PostgreSQL real en `parcial/tests/` (201/409/422/404/401/403, mismo UoW, fila revocada persistida, RN-05), y una regresión del catálogo protegido (mutación con `debe_cambiar_password = true` → 403; lecturas públicas → 200). Los archivos `.http` de C-07/C-08 quedan para C-18.
- Riesgo de secuencia: `grupos-de-rutas` todavía no está sincronizada a `openspec/specs/` porque **C-14 no está archivado**; archivar C-14 antes de archivar C-15 es parte de la aceptación.
- Fuera de alcance: `POST /ventas` transaccional (C-16), seed (C-17), `.http` (C-18), Docker/VPS (C-20/C-21), migraciones de esquema, listado `GET /usuarios` y borrado lógico de usuarios (no están en la consigna).
