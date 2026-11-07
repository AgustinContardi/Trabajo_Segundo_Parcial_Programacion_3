# Design — C-15 admin-usuarios-roles-eventos

## Context

Ver `proposal.md` (Why) para la motivación. Estado actual relevante, verificado en el repo:

- `parcial/main.py` monta dos grupos: **abierto** (`health`, `usuarios.auth` → `/auth`, y los cuatro routers de catálogo **completos**) y **protegido** (`clientes`, `ventas`) con `Depends(control_cambio_password)` a nivel de router. Las mutaciones `ADMIN` del catálogo quedaron en el grupo abierto, contradiciendo la decisión 1 del `design.md` de C-14.
- `parcial/app/core/dependencies.py` ofrece `get_usuario_actual`, `get_sesion_actual` (devuelve `IdentidadActual` con `usuario`, `roles_db` y `roles_token`) y `requiere_rol(*roles)`. `control_cambio_password` ya existe y se resuelve **antes** que `requiere_rol`, porque es dependencia de router.
- `parcial/app/modules/usuarios/` tiene modelos (`Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad`), `UsuarioRepository` (`get_by_email`, `roles_vigentes`), `AsignacionRolRepository` **sin métodos propios**, `EventoSeguridadRepository` (`listado(page, size)`), tres UoW (`UsuariosUnitOfWork`, `RegistroUnitOfWork`, `CambioPasswordUnitOfWork`) y el router `/auth` con login, registro, logout, `yo` y `cambiar-password`. **No existe ninguna ruta `/usuarios` ni `/eventos`.**
- Esquema ya migrado (C-03/C-04, migración `dd4a0e5e9cf7`): `usuario` con `email UNIQUE`; `asignacion_rol` con `CHECK (rol IN ('ADMIN','VENDEDOR','CLIENTE'))`, índice único parcial `uq_asignacion_rol_abierta (usuario_id, rol) WHERE revocada_en IS NULL`, FK `usuario_id` y `otorgada_por` indexadas; `evento_seguridad (id, cuando, actor text, accion)`. **No hay migración nueva en este change.**
- `parcial/app/core/errors.py` ya mapea `uq_usuario_email` → 409, `uq_asignacion_rol_abierta` → 409, `ck_asignacion_rol_rol` → 422 y las dos FK de `asignacion_rol` → 409.
- **Defecto preexistente**: `parcial/app/modules/usuarios/repository.py` anota `listado(...) -> Pagina[EventoSeguridad]` pero solo importa `paginar`; en Python 3.12 la anotación se evalúa al definir la función, así que **importar el módulo falla con `NameError: name 'Pagina' is not defined`** (verificado con `py -3.12`). Cualquier ruta de C-15 que use `EventoSeguridadRepository` y cualquier test que importe el módulo quedan bloqueados hasta arreglarlo.
- Convenciones: `CV-01` (el router construye el UoW, el servicio lo abre con `async with`), `CV-02` (repositorios solo `flush()`), `CV-03` (`selectinload` solo en `repository.py`), `CV-08` (orden 404 → 403 → 409 → 422 dentro del servicio), `RN-16` (auditoría en la misma transacción).
- `openspec/specs/grupos-de-rutas/` **todavía no existe**: C-14 está cerrado pero no archivado, así que la capability que este change modifica se materializa al archivar C-14. `openspec validate` lo reporta como `INFO`, no como error; el archivo de C-15 requiere que C-14 se haya archivado antes.

## Goals / Non-Goals

**Goals:**

- Alta de personal, asignación/revocación/listado de roles e historial de eventos como rutas `ADMIN` del grupo protegido, con auditoría en la misma transacción.
- `RN-03` garantizada por el índice único parcial existente + el cierre explícito de la fila vencida.
- `RN-05` garantizada en el servicio, con bloqueo de filas para que dos revocaciones concurrentes no dejen el sistema sin administradores.
- Dejar el catálogo completo bajo la puerta del cambio obligatorio sin cambiar ningún contrato existente.
- Reparar el import que hoy impide importar el módulo `usuarios.repository`.

**Non-Goals:**

- Migraciones, columnas nuevas o disparadores (`RN-05` es comprobación de servicio, `RN-03` ya tiene índice).
- `GET /usuarios` (listado), baja lógica de usuarios, bloqueo/desbloqueo, reseteo de contraseña por admin: no están en la consigna ni en `CHANGES.md`.
- `.http` de C-07/C-08 (C-18), seed (C-17), ventas transaccionales (C-16).
- Tocar `despliegue/`: es la copia limpia para C-20/C-21.

## Decisions

### 1. Un `router_admin.py` en el módulo `usuarios`, con dos prefijos

Se agrega `parcial/app/modules/usuarios/router_admin.py` con dos `APIRouter`: `router_usuarios` (`prefix="/usuarios"`, `tags=["usuarios"]`) y `router_eventos` (`prefix="/eventos"`, `tags=["eventos"]`). Ambos se montan en el grupo protegido de `main.py`.

**Razón:** los endpoints comparten modelos, repositorios, schemas y UoW con el módulo `usuarios`; separarlos en un módulo nuevo (`admin/`) duplicaría imports y rompería la cohesión que ya usan C-11…C-14. Mantenerlos en otro archivo (y no en `router.py`, que tiene `prefix="/auth"`) evita mezclar dos superficies con dependencias distintas.

**Alternativa descartada:** un único router con `prefix=""` y paths absolutos. Funciona, pero pierde el prefijo por router y obliga a repetir `/usuarios` y `/eventos` en cada decorador.

### 2. `AdminUnitOfWork` con `usuarios`, `roles` y `eventos`

Nuevo UoW (y dependencia `get_admin_uow`) que compone `UsuarioRepository`, `AsignacionRolRepository` y `EventoSeguridadRepository` sobre **la misma sesión**. El router lo construye; el servicio lo abre con `async with` (`CV-01`).

**Razón:** las tres operaciones de escritura de C-15 tocan exactamente esos tres agregados en una sola transacción (`RN-16`). Reutilizar `RegistroUnitOfWork` (que compone clientes) o `CambioPasswordUnitOfWork` (sin roles) mezclaría responsabilidades.

**Alternativa descartada:** componer los repositorios ad hoc en el router. Rompe el patrón de un UoW por caso de uso que ya siguen los otros tres.

### 3. Consultas nuevas en `AsignacionRolRepository`, con reloj de PostgreSQL

- `get_abierta(usuario_id, rol)` → `AbiertaRol(asignacion, vigente)` o `None`: busca la fila con `revocada_en IS NULL` y calcula `vigente` **en SQL** con `(vence_en IS NULL OR vence_en > now()).label("vigente")`.
- `listar_por_usuario(usuario_id)` → todas las filas, `ORDER BY desde DESC, id DESC`.
- `contar_admins_vigentes(excluir_id=None, bloquear=False)` → cuenta filas `rol='ADMIN'`, `revocada_en IS NULL`, vigentes por `now()`; con `bloquear=True` emite `SELECT ... FOR UPDATE` sobre **todas** las filas vigentes y excluye la objetivo en memoria (ver §5).
- `cerrar(asignacion, cuando=None)` → escribe `revocada_en` (default `now()` del servidor) y hace `flush()`.
- `abrir(usuario_id, rol, *, vence_en=None, otorgada_por=None)` → crea y hace `flush()`.

**Razón:** el docstring del módulo ya fija que «las ventanas de tiempo se calculan con el reloj de PostgreSQL, no con el del proceso». Mezclar `now()` de Python para decidir vigencia y `now()` de la base para guardar produce desfases de segundos que hacen fallar los bordes (`vence_en` recién pasado). El `FOR UPDATE` serializa revocaciones concurrentes de `ADMIN`, que es el único punto de `RN-05` que el índice parcial no cubre.

**Corrección verificada contra PostgreSQL real (tarea 5.6):** si la consulta bloqueada excluyera también del `FOR UPDATE` la fila objetivo, dos transacciones que revocan administradores distintos bloquearían conjuntos **disjuntos** y ambas leerían «queda otro». El bloqueo se aplica a todas las filas vigentes y la exclusión se hace en memoria; el test de dos sesiones lo demuestra (la segunda queda esperando hasta que la primera confirma o revierte).

**Alternativa descartada:** resolver `vigente` en Python comparando con `datetime.now(timezone.utc)`. Más simple, pero contradice la convención del módulo y expone el borde de reloj. **Alternativa descartada:** disparador en la base para «nunca sin administradores». `RN-05` exige la comprobación en el servicio (la KB lo dice explícitamente) y un disparador complicaría el rollback y el mensaje 409.

### 4. Reasignar un rol vencido: cerrar, `flush`, abrir

En `POST /usuarios/{id}/roles` el servicio: lee `get_abierta`; si `None` → `abrir`; si `vigente` → `409`; si existe pero **vencida** → `cerrar(asignacion)` (que hace `flush`) y luego `abrir(...)`.

**Razón:** la fila vencida sigue participando del índice único parcial porque su `revocada_en` es `NULL`. Si se inserta la nueva sin cerrar, PostgreSQL rechaza el `INSERT` por `uq_asignacion_rol_abierta` y el caso legítimo de `RN-03` («reasignar un rol vencido es válido») terminaría en 409. El `flush` explícito garantiza el orden `UPDATE` → `INSERT` independientemente del orden que elija SQLAlchemy al hacer flush automático. **Verificado contra PostgreSQL real (C-15, tarea 3.4):** sin cerrar la fila, el `INSERT` falla por el índice; con `cerrar()` el `UPDATE` se emite antes que el `INSERT`. No se pudo reproducir un fallo atribuible solo a la falta de `flush` (SQLAlchemy ordenó `UPDATE` antes de `INSERT` en la prueba), así que el `flush` se justifica como garantía determinista, no como corrección de un fallo observado.

**Alternativa descartada:** `session.autoflush` confiando en el orden de la unit of work. No hay garantía de orden entre un `UPDATE` de atributo y un `INSERT` pendiente; el test de reasignación lo haría intermitente.

### 5. `RN-05` en el servicio, en este orden

1. `404` si el usuario no existe.
2. `404` si no hay fila de ese rol; `409` si la única fila ya está revocada.
3. `409` si `usuario_id == admin.id` y `rol == "ADMIN"`.
4. `409` si `contar_admins_vigentes(excluir_id=fila.id, bloquear=True) == 0`.
5. Recién entonces `cerrar(fila)` + `evento_seguridad.add(...)`.

**Razón:** el orden respeta `CV-08` y evita bloquear filas para una petición que ya sabemos inválida. El conteo **excluye la fila objetivo**: si quedan 0 administradores vigentes sin contar la que se va a revocar, el sistema quedaría sin administradores. Para que la exclusión no rompa la serialización, la consulta bloqueada trae todas las filas vigentes y descarta la objetivo en memoria (§3). Revocar una fila `ADMIN` ya vencida no reduce administradores vigentes y por eso responde `200`.

**Alternativa descartada:** contar incluyendo la fila y comparar `<= 1`. Es equivalente, pero el «excluir el objetivo» se lee como la invariante real («después de esta revocación debe quedar al menos uno») y cubre igual el caso de la fila vencida.

### 6. Contratos de entrada: `Literal` + `AwareDatetime`

- `PersonalCreate`: `email` (reutiliza `_normalizar_email`), `nombre`, `password` (≤ 72 bytes con `validar_password_bytes`), `rol: Literal["ADMIN","VENDEDOR"]`, `extra="forbid"`, `SinNulMixin`.
- `AsignacionRolCreate`: `rol: Literal["ADMIN","VENDEDOR","CLIENTE"]`, `vence_en: AwareDatetime | None` con validador que exige `> now(UTC)`, `extra="forbid"`.
- Salidas: `UsuarioRead` (existente, sin `rol`), `AsignacionRolRead` y `EventoSeguridadRead`, ambos `from_attributes=True`.

**Razón:** `Literal` hace que un rol inválido sea `422` en el contrato, igual que el `CHECK` de la base; `AwareDatetime` hace que una fecha sin zona sea `422` sin código manual. La comparación con el futuro usa el reloj del proceso: es un borde de segundos y el único lugar donde no se puede usar `now()` de la base antes de abrir la transacción.

**Alternativa descartada:** validar rol y fecha en el servicio. Funciona, pero pierde el `422` automático del contrato y duplica la validación de Pydantic.

**Alternativa descartada:** devolver un `PersonalRead` con `rol` en el alta. Obligaría a un schema nuevo y a una consulta extra; el rol inicial se consulta con `GET /usuarios/{id}/roles`. Se documenta como decisión de contrato.

### 7. Hash fuera de la transacción en el alta

`bcrypt` se calcula antes de abrir el UoW, con `to_thread` + el semáforo de `app.state` (`RN-08`), igual que `registrar` (C-12) y `cambiar_password` (C-14). Dentro de un solo `async with uow`: `usuario` + `asignacion_rol` (`otorgada_por = admin.id`) + `evento_seguridad.add(actor=admin.email, ...)`.

**Razón:** no retener una conexión del pool durante cientos de milisegundos de CPU y no dejar el usuario creado si el rol o la auditoría fallan.

### 8. Catálogo: separar routers, no duplicar rutas

Cada módulo de catálogo expone dos routers con el mismo prefijo y tags: el actual (`router`) conserva **solo las lecturas públicas** y un nuevo `router_admin` agrupa las mutaciones `ADMIN` (`POST`/`PATCH` de editoriales, géneros y autores; `POST`/`PATCH`/`DELETE`, `reponer` y `movimientos` de libros). `main.py` monta los `router_admin` en el grupo protegido y los `router` en el abierto.

**Razón:** es la única forma de que el control de cambio obligatorio se aplique «una sola vez a nivel de router» sin duplicar handlers ni cambiar paths. Los paths, métodos, bodies y responses quedan idénticos; lo único observable es el `403` nuevo para `ADMIN` con cambio pendiente.

**Alternativa descartada:** montar el router completo en el protegido y re-declarar las lecturas públicas en otro router. Duplica handlers y arriesga divergencia de contratos.

**Alternativa descartada:** middleware que decida por path. Acopla autenticación al transporte y repite la lista de rutas (ya descartado en C-14).

### 9. `GET /usuarios/{id}/roles` sin envoltorio de paginación

Devuelve `list[AsignacionRolRead]`. `DD-18` aplica a colecciones paginadas; el historial de roles de una persona no se pagina en la consigna y el caso C-07 lo consume completo.

**Riesgo asumido:** si la corrección espera `{items, total, ...}`, el ajuste es de una línea en C-18. Se deja anotado en `Risks`.

### 10. Arreglo del import de `Pagina`

`from app.core.paginacion import Pagina, paginar` en `usuarios/repository.py`. Es un arreglo de import (la anotación ya era correcta); no cambia comportamiento más que desbloquear el import.

## Risks / Trade-offs

- [`grupos-de-rutas` no existe todavía en `openspec/specs/`] → C-14 debe archivarse antes de C-15; el `MODIFIED` de C-15 se aplica entonces. `openspec validate` lo reporta como `INFO`, no como error. Se verifica en la aceptación.
- [El defecto del import de `Pagina` puede ser el síntoma de un entorno de pruebas distinto al reportado] → Se arregla como primera tarea y se agrega un test de importación (`python -c "import app.modules.usuarios.repository"`) para que no vuelva a pasar inadvertido.
- [Reasignar sin cerrar la fila vencida produce 409 espurio] → Cierre + `flush` explícito y test dedicado contra PostgreSQL real (el índice parcial no se puede simular con fakes).
- [Dos revocaciones concurrentes del último par de administradores] → `SELECT ... FOR UPDATE` sobre las filas `ADMIN` abiertas antes de contar; el costo es contención en una operación administrativa poco frecuente.
- [El reloj del proceso valida `vence_en` futuro y el de la base decide vigencia] → Desfase máximo de segundos en el borde; aceptado y documentado. El test usa márgenes amplios (pasado: −1 día; futuro: +1 día).
- [Mover las mutaciones de catálogo agrega 403 donde antes había 200 para un `ADMIN` con cambio pendiente] → Es el comportamiento exigido por `RN-06` y el checklist §5; el contrato de paths y cuerpos no cambia. Se cubre con test de tabla de rutas.
- [El historial de roles sin envoltorio puede no coincidir con lo esperado por la cátedra] → Cambio de una línea en la capa de router; anotado para C-18.
- [La respuesta del alta no incluye el rol] → Se consulta con `GET /usuarios/{id}/roles`; si la corrección lo pide, se agrega un campo sin romper el contrato existente.

## Migration Plan

Sin migración de base: las tres tablas y el índice parcial ya existen desde C-03/C-04; `alembic upgrade head` no cambia y `alembic check` debe seguir limpio. El despliegue consiste en montar los routers nuevos y mover los de administración del catálogo al grupo protegido. Rollback: retirar los routers de `main.py` y devolver las mutaciones de catálogo al grupo abierto; no hay datos que revertir (las filas escritas por C-15 son datos de negocio válidos). `despliegue/` no se toca.

## Open Questions

Ninguna que cambie specs, enfoque o tareas. Las dos decisiones de contrato que podrían ajustarse con la corrección (`GET /usuarios/{id}/roles` sin envoltorio y alta sin `rol` en la respuesta) están resueltas y anotadas como riesgos.

## UI Mockups

- Decision: no (no UI)
- Fecha: 2026-11-06
- Motivo: el proyecto es API pura (`visual_design.mode = off`); C-15 agrega rutas JSON sin pantallas ni componentes visuales.
