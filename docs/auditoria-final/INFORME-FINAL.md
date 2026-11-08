# Informe final de auditoría — C-01…C-19

> Consolidación de los 19 informes de `docs/auditoria-final/c-NN-*.md`.
> Fecha: 2026-11-08 · Repo: `prog_segundo_parcial` · Base: PostgreSQL 17.11 (`127.0.0.1:5432/libreria`).
> Este documento **no** re-audita: agrega lo ya verificado y prioriza lo que falta.

---

## 1. Veredicto global

| Estado | Cantidad | Changes |
|---|---|---|
| PASS (sin WARN) | **4** | C-02, C-03, C-11, C-12 |
| PASS con WARN | **13** | C-01, C-05, C-06, C-07, C-08, C-09, C-13, C-14, C-15, C-16, C-17, C-18, C-19 |
| FAIL | **2** | **C-04** (defaults `now()` congelados en migración 0003), **C-10** (`GET /mis-ventas` montado en `/ventas/mis-ventas`) |

**Veredicto global: NO APTO para cerrar la entrega** hasta corregir los 2 FAIL. El resto del código
cumple: 17 de 19 changes pasan, con 32 WARN acumulados, casi todos documentales o de trazabilidad.
Ningún WARN oculta un defecto funcional nuevo; los dos FAIL sí son observables desde fuera
(`curl /mis-ventas` → 404; `movimiento_stock.cuando` / `evento_seguridad.cuando` con la hora de la
migración en todas las filas).

Los 2 FAIL también arrastran dos ítems del checklist: **§6.7** (`/mis-ventas` como ruta propia) y
**§3.11 + §4** (defaults `timestamptz` que no son hora de la operación).

---

## 2. Tabla por change

> La columna `PASS/WARN/FAIL` es el estado normalizado (FAIL si el informe declara al menos un FAIL).
> «veredicto» reproduce el change y el conteo del informe original.

| C-NN | veredicto | PASS/WARN/FAIL | hallazgos clave | archivo |
|---|---|---|---|---|
| C-01 | baseline-tp-y-fundacion — PASS (0 FAIL / 7 WARN) | **WARN** | 7 WARN son ítems no re-verificables sin mutar/levantar servidor (seed, base temporal, uvicorn, pytest), todos con evidencia creíble del 2026-11-07. Notas: README con placeholders de integrantes y paso 4 desactualizado («todavía no hay migraciones»), migraciones 0003/0004 sin prefijo numérico (no matchea el glob de §3), `health/__pycache__` en disco, `app/core/errors.py` extra (C-05). | `c-01-baseline-tp-y-fundacion.md` |
| C-02 | core-repositorios-uow-paginacion — PASS (0 FAIL / 0 WARN) | **PASS** | Repos sólo `flush()`, UoW confirma en `__aexit__` sin cerrar sesión, envoltorio de página exacto, 422 con mensaje propio, `size` default 20, `total` con los mismos filtros, inyección ligada. `alembic check` limpio. | `c-02-core-repositorios-uow-paginacion.md` |
| C-03 | modelos-acceso-stock — PASS (24/24) | **PASS** | Entidades en su módulo, CHECKs e índices parciales correctos, FKs indexadas, `timestamptz`/`NUMERIC`, invariante de stock en 0 filas. Nota: el «8 columnas» de `asignacion_rol` es error de conteo del checklist (son 7). | `c-03-modelos-acceso-stock.md` |
| C-04 | migraciones-0003-0004 — FAIL documentado | **FAIL** | §3 se cumple 6/6, pero `server_default="now()"` como *string* quedó compilado como literal congelado en `asignacion_rol.desde`, `intento_acceso.cuando`, `evento_seguridad.cuando`, `movimiento_stock.cuando` (+ `venta.fecha` de 0001). Evidencia en datos: 7 movimientos y 1 evento con exactamente `2026-11-08 12:18:56.115576-03`. `alembic check` no lo detecta porque el modelo replica el mismo literal. | `c-04-migraciones-0003-0004.md` |
| C-05 | errores-paginacion-contratos — PASS (3 WARN) | **WARN** | §9 completo en runtime. WARN: `bool_type`/`float_type` mapean a «Debe ser un número entero válido» (`core/errors.py:166-167`); falta el comentario de contrato CV-08 (`404→403→409→422`) en `autores`, `generos` y `libros`; el 409 de unicidad no se disparó end-to-end (sólo unit). | `c-05-errores-paginacion-contratos.md` |
| C-06 | capas-editoriales-generos-autores — PASS (19/19, 4 WARN) | **WARN** | `PATCH /autores/{id}` no puede dar 409 por unicidad: `Autor` no tiene ningún `UNIQUE` → rama muerta. `GET /generos/{id}` no existe (sólo listado y `/libros`), `GeneroService.obtener()` queda sin ruta. Numeración CV-02/CV-03 inconsistente entre documentos; evidencia de task 5.2 cita `import app.main` (el módulo real es `main`). | `c-06-capas-editoriales-generos-autores.md` |
| C-07 | capas-clientes-y-perfil — PASS (1 WARN) | **WARN** | 401/403/200 de `GET /clientes/{id}/ventas` correctos y roles releídos de base. `ClienteRepository.ventas_de` pagina sin `ORDER BY` → orden no determinista (el design D-6 lo preveía). | `c-07-capas-clientes-y-perfil.md` |
| C-08 | capas-libros-alta-stock-inicial — PASS (12/12, 2 WARN) | **WARN** | El movimiento «Stock inicial» se atribuye a `SELECT id FROM usuario LIMIT 1`, no al admin autenticado: `crear_libro` recibe `_sesion` y no lo pasa al servicio. `stock_inicial = 0` no deja movimiento (correcto por el `CHECK cantidad <> 0`, documentado). Invariante en 0 filas. | `c-08-capas-libros-alta-stock-inicial.md` |
| C-09 | libros-baja-reposicion-movimientos — PASS (15/15, 1 WARN) | **WARN** | Mismo defecto que C-08 en `reponer`: `usuario_actual` no se propaga y el fallback SQL asigna el primer usuario de la tabla. Todo lo demás (204, 404, 409 de baja, re-alta 201, venta vieja con título) verificado con evidencia. | `c-09-libros-baja-reposicion-movimientos.md` |
| C-10 | capas-ventas-lecturas — FAIL (1 FAIL / 1 WARN) | **FAIL** | `GET /mis-ventas` → **404**: el handler vive bajo `APIRouter(prefix="/ventas")` y sólo existe `/ventas/mis-ventas` (confirmado en `openapi.json`). La consigna, la KB y §6.7 piden el path standalone; los tests usan también el path equivocado, por eso la suite no lo detecta. WARN: `design.md` sin `Decision: no (no UI)`. | `c-10-capas-ventas-lecturas.md` |
| C-11 | seguridad-login-cookie — PASS | **PASS** | Token sólo en cookie HttpOnly/SameSite/Max-Age; 401 uniforme con hash ficticio; límite antes de verificar con 429 + `Retry-After` en ms; `intento_acceso` en transacción propia; bcrypt con `to_thread` + semáforo; 73 bytes → 422. | `c-11-seguridad-login-cookie.md` |
| C-12 | auto-registro-atomico — PASS (12/12) | **PASS** | Hash antes de la transacción, usuario + rol CLIENTE + ficha en un solo `async with`, `except IntegrityError` fuera del bloque, 409 de usuario y de cliente sin filas sueltas ni apropiarse de la ficha, 201 sin cookie ni `password_hash`. | `c-12-auto-registro-atomico.md` |
| C-13 | requiere-rol-y-yo — PASS (13 PASS / 2 WARN) | **WARN** | Token que miente (`roles:["ADMIN"]` forjado) → 403; base que otorga → 200; `/auth/yo` muestra `roles` vs `roles_token`; misma sesión por petición (`test_session_sharing`). WARN: el comando del checklist §6.1 (`grep AsignacionRol app/core/dependencies.py`) da vacío porque la consulta vive en `usuarios/repository.py`; dueño-200 no reproducible en vivo sin escribir. | `c-13-requiere-rol-y-yo.md` |
| C-14 | cambio-password-grupos-de-rutas — PASS (20 PASS / 2 WARN) | **WARN** | `control_cambio_password` montado una sola vez en `main.py:119`; con bandera en `true` el grupo protegido da 403 y `/auth` sigue pasando; cambio de clave no rota la cookie ni emite token. WARN: `tasks.md` dice «PostgreSQL real» pero el test usa `Mock`/`dependency_overrides`; `tests/test_control_cambio_password.py:35-38` es un test con sólo `pass`. | `c-14-cambio-password-grupos-de-rutas.md` |
| C-15 | admin-usuarios-roles-eventos — PASS (2 WARN) | **WARN** | RN-03/RN-05/RN-16: autoprotección y último ADMIN con `FOR UPDATE`, cierre sin borrado, evento con actor en la misma transacción, `FOR UPDATE` verificado en SQL compilado. WARN H-1: defaults congelados (C-04) contaminan `evento_seguridad.cuando`; H-2: `cerrar()` usa reloj Python aunque el docstring dice `now()` del servidor. | `c-15-admin-usuarios-roles-eventos.md` |
| C-16 | venta-transaccional (+ fix) — PASS (33 PASS / 2 WARN) | **WARN** | Venta atómica en un UoW, `Decimal`/`NUMERIC`, stock sólo vía `aplicar_movimiento`, 409 sin escrituras en los cuatro casos, `POST /ventas` sin barra → 201 sin 307, `BackgroundTasks` después del commit, invariante 0 filas. WARN: defaults congelados (referencia) y casos 201/204 no re-ejecutados. | `c-16-venta-transaccional.md` |
| C-17 | seed-libreria — PASS | **WARN** | Estado sembrado coincide con lo declarado (5 usuarios/5 roles, 3-3-6 catálogo, 5 libros 10/5/8/3/1, venta 1 = 69000.00, 7 movimientos, 1 evento SISTEMA); `TRUNCATE … RESTART IDENTITY` + verificación interna. WARN: defaults congelados; INFO: `intento_acceso` con 15 filas de actividad posterior (no del seed). | `c-17-seed-libreria.md` |
| C-18 | casos-c-http-y-solo-agregado — PASS (16/16, 3 WARN) | **WARN** | Los 16 casos `C-01…C-16` existen con `# Esperado:` y evidencia; C-14 (trigger) y C-15 (6 SELECT = 6 SELECT) con capturas. WARN: C-07.11 usa fecha fija y no es auto-concluyente; la pasada httpyac corrió sobre copias `_compat/`; defaults congelados. Sin cambios de producción (`git diff` vacío). | `c-18-casos-c-http-y-solo-agregado.md` |
| C-19 | suite-pytest-y-evidencia — PASS (12 PASS / 3 WARN) | **WARN** | `tests/` sólo pytest (53 `.py`, 0 `.http`/`.sql`), sin sqlite, comparación status+body, `--collect-only` 460 ítems consistente con 459 passed / 1 skipped registrado, `evidencia/` con C-14 y C-15. WARN: captura de `BackgroundTasks` fuera de `evidencia/`; defaults congelados; `__pycache__`/`.pytest_cache` en disco (riesgo al armar el zip). | `c-19-suite-pytest-y-evidencia.md` |

---

## 3. Rollup por sección del checklist (§0…§13)

| Sección | Estado | Observaciones |
|---|---|---|
| **§0** Reglas no negociables | **PASS** | Paths exactos y 8 módulos con seis capas (C-01); router construye UoW / servicio lo abre / sólo `__aexit__` confirma (C-01, C-02, C-06…C-10, C-16); `selectinload` sólo en `repository.py`; sin `password_hash` en schemas; sin `create_all`; sin credenciales en repo ni historial. Deuda documental: numeración `CV-02`/`CV-03` inconsistente (C-06) y comentario CV-08 ausente en 3 servicios (C-05). |
| **§1** Estructura | **PASS** | `main.py` con `lifespan` y dos grupos; `seed.py` en raíz de `parcial/`; 7 archivos en `app/core/` (+`errors.py` de C-05); `health` sólo `router.py`; entidades en su módulo; `test/` con `.http` + `solo_agregado.sql` y `tests/` sólo pytest (C-19: 53 `.py`, 0 `.http`/`.sql`); `env.example` sin punto; `.env` ignorado y no trackeado. Ruido: `__pycache__` en disco. |
| **§2** Configuración | **PASS** | 13 variables en `Settings`, `database_url` con `@computed_field` y `postgresql+asyncpg`, `POSTGRES_PASSWORD`/`JWT_SECRET` sin default (fail-fast verificado por `Settings(_env_file=None)`), motor y sessionmaker sólo en `lifespan` en `app.state`, `hash_ficticio` una vez, `dispose()` al apagar, `alembic.ini` sin URL, `env.py` desde Settings con `NullPool`. |
| **§3** Migraciones | **FAIL** | 4 versiones encadenadas, `alembic current` = head `c8d2dea5529f`, `alembic check` sin drift, 0003 con las 8 piezas y 0004 con función + trigger append-only, round-trip acreditado por evidencia. **Falla el ítem de defaults**: `server_default="now()"` congelado (C-04, confirmado además en C-13/C-15/C-16/C-17/C-18/C-19). Nota: nombres sin prefijo `0003_`/`0004_` no matchean el glob literal del checklist. |
| **§4** Modelo de datos | **PASS (con salvedad)** | Estructura, CHECKs, índices únicos parciales, FKs indexadas, `timestamptz` y `NUMERIC` correctos; invariante de stock en 0 filas en cada medición. Salvedad: los defaults de §3 hacen que `cuando`/`desde` de las filas escritas por la app no reflejen la operación (§4 exige columnas, no defaults; el defecto se imputa a §3). `asignacion_rol` tiene 7 columnas: el «8» del checklist es error de conteo; `cliente.usuario_id` tiene unicidad duplicada (inofensiva). |
| **§5** Autenticación | **PASS** | Cookie HttpOnly/SameSite/Lax con `Secure` configurable, cuerpo sin token, JWT con `sub`/`exp`/roles validado por PyJWT, 401 uniforme con hash ficticio, límite antes de verificar + 429 con `Retry-After` en ms, intento registrado incluso cuando se limita, bcrypt `to_thread` + semáforo y ≤72 bytes → 422, `cambiar-password` sin token nuevo ni rotación de cookie, `debe_cambiar_password` bloqueando el grupo protegido salvo `/auth`. |
| **§6** Autorización | **FAIL** | Roles releídos de `asignacion_rol` en cada petición (token forjado → 403, base que otorga → 200), revocación/vencimiento con la misma cookie, 422 de `vence_en`, RN-03/RN-05 con `FOR UPDATE`, `GET /ventas/{id}` sin `requiere_rol`, matriz de rutas correcta. **Falla §6.7**: la ruta canónica es `/ventas/mis-ventas`; `GET /mis-ventas` → 404 (C-10). Además, el comando de §6.1 (`grep AsignacionRol app/core/dependencies.py`) da vacío: la consulta está en `usuarios/repository.py` (M-1 de C-13). |
| **§7** Capas y transacciones | **PASS** | `BaseRepository`/`SoftDeleteRepository` con la firma exigida, cero `commit()` en repositorios, UoW confirma/revierte sin cerrar, UoW por módulo con la misma sesión, ningún servicio recibe `AsyncSession` ni construye UoW (única excepción declarada: `intento_acceso` con sesión propia, DD-05), una conexión por petición autenticada (`test_session_sharing`), stock en un único punto, eventos RN-16 en la misma transacción. Deuda: atribución del actor del movimiento (C-08/C-09). |
| **§8** Ventas, stock y catálogo | **PASS (con WARN)** | Venta atómica con precios copiados y total del servidor, 409 sin escrituras (stock, cliente, libro, baja), sin `PATCH /ventas`, baja lógica 204, re-alta con ISBN de baja 201 y segundo vigente 409, `PATCH /libros` sólo título/precio, `stock_inicial` + movimiento, detalle muestra libros de baja, invariante 0 filas, seed coherente con la spec. WARN: `usuario_id` del movimiento no es el autenticado (C-08/C-09); `PATCH /autores` promete un 409 inalcanzable (C-06). |
| **§9** Errores y paginación | **PASS (con WARN)** | Envoltorio exacto en todos los listados, `page` desde 1, `size` 1..100 default 20, página fuera de rango 422 con mensaje propio, `total` con los mismos filtros y `pages: 1` en vacío, sin texto interno ni trazas, ninguna entrada inválida termina en 500, búsqueda ligada e insensible a mayúsculas, `extra="forbid"`, `exclude_unset`, códigos de la tabla. WARN: mensajes de `bool`/`float` engañosos (C-05); `ventas_de` sin `ORDER BY` → paginación no determinista (C-07); 409 de unicidad no ejercitado end-to-end en la auditoría (C-05). |
| **§10** Pruebas | **PASS (por evidencia)** | Un `.http` por caso con `# Esperado:` (C-18, 16/16), capturas críticas (trigger C-14, 6=6 SELECT C-15, `BackgroundTasks` C-10), suite 459 passed / 1 skipped / 0 errors registrada y `--collect-only` 460 consistente, handlers todos `async def`, sin sqlite ni mocks globales de DB. **No re-ejecutado** por la regla de auditoría. WARN: C-07.11 no auto-concluyente; pasada GUI REST Client pendiente; C-01-422 y `' OR '1'='1` sin test pytest dedicado. |
| **§11** Despliegue | **NO AUDITADO** | `despliegue/` es la copia intacta del TP cap. 1-4 (verificada: sin `movimiento_stock`/`AsignacionRol`/`UnitOfWork`). No hay `Dockerfile`, `.dockerignore`, `DEPLOY.md` ni `despliegue/evidencia/` todavía: corresponde a **C-20** (imagen) y **C-21** (VPS), ambos `[ ]`. |
| **§12** Formato de entrega | **PARCIAL** | `tests/`, `test/` y `evidencia/` trackeados y no ignorados; C-14 y C-15 presentes en `parcial/evidencia/`; sin temporales `_compat`/`*.bak`. Pendiente: zip `Parcial_Cap1a6_<Grupo>.zip` (C-22), nombres y apellidos en `parcial/README.md` (placeholders de C-01), y decidir si se copia `c-10-backgroundtasks.txt` a `evidencia/`. |
| **§13** Autoevaluación contra la rúbrica | **PENDIENTE** | La tabla de la rúbrica está sin tildar; es entrega de C-22. Con los 2 FAIL abiertos no puede cerrarse en verde: «Autorización» (12 %) y «Modelos, relaciones y migraciones» (10 %) quedan observados. |

---

## 4. Fixes priorizados

> Restricciones respetadas: no se edita ninguna migración ya aplicada (regla 9), no se propone
> `commit`/`push`, y toda verificación indicada es ejecutable sin tocar la base compartida (base
> temporal propia o test con rollback).

### 4.1 Bloqueantes

#### B-1 · C-10 — `GET /mis-ventas` en el path incorrecto

- **Archivos**: `parcial/app/modules/ventas/router.py`, `parcial/main.py`,
  `parcial/tests/test_ventas_authorization.py`, `parcial/tests/test_cambio_password_api.py`,
  `parcial/test/roles.http`, `parcial/test/EVIDENCIA.md`.
- **Cambio**:
  1. En `ventas/router.py` (hoy `APIRouter(prefix="/ventas")`, línea 19), declarar un segundo router
     `router_mis_ventas = APIRouter(tags=["ventas"])` y mover allí el handler
     `@router.get("/mis-ventas")` con su cuerpo intacto (sigue usando `get_sesion_actual` y
     `get_ventas_uow`; la lógica de `service.mis_ventas` no cambia).
  2. En `main.py`, importar y montar `router_mis_ventas` dentro de `router_protegido`
     (`main.py:129-136`), para conservar `control_cambio_password` y el 403 de C-09.
  3. Actualizar a `/mis-ventas` los tests que hoy pegan a `/ventas/mis-ventas` y el caso C-06 de
     `roles.http` + su fila en `EVIDENCIA.md`.
- **Verificación esperada**:
  - `GET /mis-ventas` sin cookie → **401** `{"detail":"No autenticado"}` (hoy 404).
  - `GET /mis-ventas` con cookie `ana@example.com` → **200** con
    `{items,total,page,size,pages}` y sólo ventas de su `cliente_id`.
  - `openapi.json` contiene `/mis-ventas` y **no** `/ventas/mis-ventas`.
  - `pytest -q` verde con los tests renombrados; `POST /ventas/` y `GET /ventas/` siguen igual
    (el nuevo router no compite con `/ventas/{venta_id}`).

#### B-2 · C-04 — defaults `now()` congelados

- **Archivos**: `parcial/migrations/versions/` (**revisión nueva**, p. ej. `0005_now_defaults.py`),
  `parcial/app/modules/usuarios/models.py` (×3), `parcial/app/modules/libros/models.py` (×1),
  `parcial/app/modules/ventas/models.py` (×1), y opcionalmente
  `parcial/app/modules/libros/repository.py`, `parcial/app/modules/usuarios/service.py`,
  `parcial/seed.py` para pasar `cuando` explícito.
- **Cambio**:
  1. Migración nueva (no editar `dd4a0e5e9cf7` ni `0ba1752f7c23`), leída a mano antes de aplicar:
     `ALTER TABLE … ALTER COLUMN … SET DEFAULT now()` para `asignacion_rol.desde`,
     `intento_acceso.cuando`, `evento_seguridad.cuando`, `movimiento_stock.cuando` y
     `venta.fecha`; `downgrade` que reponga el literal documentado en la cabecera.
  2. En los 5 modelos, `server_default="now()"` → `server_default=sa.text("now()")` (o
     `text("now()")`), en el mismo commit que la migración, para que `alembic check` siga limpio.
  3. No reescribir filas históricas: los `cuando`/`desde` ya congelados no se actualizan (falsearía
     la auditoría); dejar constancia en el estado del change de que los datos previos conservan el
     sello de la migración.
- **Verificación esperada** (base temporal, nunca la compartida):
  - `alembic upgrade head` sobre base vacía → exit 0; `alembic check` → «No new upgrade operations
    detected».
  - `psql -c "SELECT pg_get_expr(adbin, adrelid) FROM pg_attrdef …"` sobre las 5 columnas →
    `now()` (no un literal con fecha).
  - Insertar dos filas separadas ≥1 s en una base temporal (o en el test con rollback) →
    `count(DISTINCT cuando) = 2`; hoy es 1.
  - `pytest -q` (suite completa) verde y `python seed.py` seguido de la query del invariante → 0
    filas.

### 4.2 Mayores

#### M-1 · C-08/C-09 — el usuario autenticado no llega al movimiento de stock

- **Archivos**: `parcial/app/modules/libros/router.py` (`crear_libro`, `reponer_libro`),
  `parcial/app/modules/libros/service.py` (`crear`, `reponer`, `_usuario_id`),
  `parcial/tests/test_stock_invariante.py` (o un test nuevo de atribución).
- **Cambio**: pasar `_sesion.usuario` a `service.crear(uow, data, usuario_actual=…)` y
  `service.reponer(uow, libro_id, cantidad, usuario_actual=…)`; eliminar el fallback
  `SELECT id FROM usuario LIMIT 1` para que un movimiento sin actor falle en tests en vez de atribuirse
  al primer usuario de la tabla. (La firma ya prevé el parámetro, así que no cambia el contrato.)
- **Verificación esperada**: test que crea un libro y repone con `admin2` (id 2) y consulta
  `SELECT usuario_id FROM movimiento_stock WHERE motivo IN ('Stock inicial','Reposición')` → `2`, no
  `1`; `GET /libros/{id}/movimientos` con cookie de `admin2` devuelve `usuario_id: 2`.

#### M-2 · C-07 — `ventas_de` sin `ORDER BY`

- **Archivo**: `parcial/app/modules/clientes/repository.py` (`ventas_de`).
- **Cambio**: añadir `.order_by(Venta.id)` (o `Venta.fecha.desc(), Venta.id.desc()`, coherente con
  `VentaRepository.listar`). No toca contratos ni esquema.
- **Verificación esperada**: test con 3 ventas del mismo cliente y `size=2` → página 1 `[1,2]`,
  página 2 `[3]`, sin repetidos ni faltantes entre páginas; `GET /clientes/{id}/ventas?size=2&page=2`
  estable entre dos llamadas.

#### M-3 · C-06 — rama 409 muerta en `PATCH /autores` y `GET /generos/{id}` faltante

- **Archivos**: `parcial/app/modules/autores/models.py` (+ revisión nueva de Alembic si se opta por
  unicidad), `parcial/app/modules/generos/router.py`, `parcial/app/modules/generos/service.py`.
- **Cambio**:
  1. `PATCH /autores/{id}`: elegir explícitamente una de dos vías y dejarla escrita en el change.
     (a) `UniqueConstraint("nombre", "nacionalidad")` en el modelo + migración nueva leída a mano;
     o (b) quitar del scope/spec de C-06 la promesa «409 unicidad en PATCH autores» y borrar el
     mapeo muerto. **No** agregar la constraint por `create_all` ni editando `dd4a0e5e9cf7`.
  2. `GET /generos/{id}`: exponer la ruta con `GeneroRead` y 404 `"Género no encontrado"` (o
     eliminar `GeneroService.obtener`), para que la colección de detalle sea simétrica con
     editoriales/autores.
- **Verificación esperada**: `openapi.json` contiene `/generos/{genero_id}`;
  `GET /generos/1` → 200 y `GET /generos/999999` → 404; si se elige (a), `PATCH /autores` con
  `(nombre, nacionalidad)` de otro autor → 409 con mensaje propio y `alembic check` limpio.

#### M-4 · C-05 — mensajes de `bool`/`float` y comentario CV-08

- **Archivos**: `parcial/app/core/errors.py` (líneas 166-167),
  `parcial/app/modules/{autores,generos,libros}/service.py`.
- **Cambio**: mapear `bool_type` → «Debe ser un valor booleano válido» y `float_type` → «Debe ser un
  número válido»; añadir el comentario de contrato CV-08 (orden `404 → 403 → 409 → 422`) en los tres
  servicios que hoy sólo tienen los `raise` 404.
- **Verificación esperada**: `GET /libros?size=true` (o un query booleano) → 422 con el mensaje nuevo;
  `grep -rn "CV-08" parcial/app/modules/*/service.py` devuelve los 7 módulos; `pytest -q` verde (los
  tests de mensajes se ajustan si comparan literal).

### 4.3 Menores / documentales

| # | Change | Archivos | Cambio | Verificación |
|---|---|---|---|---|
| m-1 | C-01 | `parcial/README.md` | Reemplazar los placeholders de integrantes cuando C-22 los defina y corregir el paso 4 que dice «todavía no hay migraciones propias» (hoy hay 4). No cambia la secuencia ejecutable. | Leer el README de punta a punta y correr los pasos en una copia limpia (evidencia C-01 1.4). |
| m-2 | C-14 | `parcial/tests/test_control_cambio_password.py:35-38`; `openspec/changes/archive/2026-11-07-c-14-…/tasks.md` | Convertir el test de sólo `pass` en uno real (mock de `get_usuario_actual` que devuelva 401 y comprobar que el control no se ejecuta); corregir la redacción de `tasks.md` 7.1/8.2: el archivo mockea, la corrida real contra PostgreSQL es la de `EVIDENCIA.md` §C-09. | `pytest -q parcial/tests/test_control_cambio_password.py` y que el test falle si se invierte el orden 401/403. |
| m-3 | C-15 | `parcial/app/modules/usuarios/repository.py` (`cerrar()`, ~145-152) | Alinear docstring y código: o el docstring deja de decir «default `now()` del servidor», o `cerrar()`/`abrir()` escriben con `func.now()` de PostgreSQL. Un solo criterio para el módulo. | `grep -n "now()" repository.py` vs docstring; test de `revocar_rol` sigue verde; `alembic check` limpio. |
| m-4 | C-18 | `parcial/test/roles.http` (C-07.11), `parcial/test/EVIDENCIA.md` | Dejar en el encabezado de C-07.11 los pasos exactos para regenerar el 403 (fecha relativa +1 min, o mismo procedimiento de `manual-c07-vencimiento.txt`), para que el bloque no devuelva 200 con la fecha fija de 2030. | Ejecutar C-07.11 con el procedimiento nuevo → 200 antes y 403 después. |
| m-5 | C-19 | `parcial/evidencia/`, `parcial/test/evidencia/` | Copiar `c-10-backgroundtasks.txt` a `parcial/evidencia/` para que §12 tenga juntas las tres capturas críticas (aunque el zip ya trae `test/`). | `ls parcial/evidencia` → C-10, C-14, C-15. |
| m-6 | C-19/C-22 | `.gitignore` (ya correcto), procedimiento del zip | Al empaquetar, usar `git archive` o checkout limpio: `parcial/tests/__pycache__/` y `parcial/.pytest_cache/` existen en disco y no deben viajar. | Extraer el zip y `Get-ChildItem -Recurse -Force` sin `.venv`/`__pycache__`/`.env` (§12). |
| m-7 | C-06/C-13 | `app/core/repository.py`, `app/modules/*/repository.py`, `app/core/dependencies.py`, `docs/CHECKLIST_ENTREGA.md` | Unificar la numeración `CV-02`/`CV-03` (precarga vs. paths) entre código, KB y checklist; actualizar el comando de verificación de §6.1 a `grep -n "roles_vigentes" app/core/dependencies.py` + `grep -n "AsignacionRol" app/modules/usuarios/repository.py`. | Los greps del checklist devuelven lo que el checklist espera. |
| m-8 | C-01/C-04 | `parcial/migrations/versions/0003`, `0004`; `docs/CHECKLIST_ENTREGA.md` §3 | Decidir el naming (`0003_acceso_y_stock`, `0004_append_only`) y ajustar el glob del checklist, o mantener los nombres y documentar que el glob literal no matchea. **No renombrar una migración ya aplicada** si eso invalida `alembic_version`. | El comando de §3 encuentra las 4 revisiones. |

---

## 5. Nota de método

- **Read-only**: los 19 auditores no ejecutaron `pytest` completo, `python seed.py`, `uvicorn` ni
  `INSERT/UPDATE/DELETE` contra la base compartida; sólo `SELECT`/catálogo, `alembic check` y
  peticiones de lectura mediante `httpx.ASGITransport` con el lifespan real. Las únicas escrituras
  admitidas fueron logins de auditoría (`intento_acceso`, append-only) y este informe.
- **Motivo**: varios auditores comparten la misma instancia y la suite/seed reescriben el estado; un
  `pytest` paralelo habría invalidado las mediciones de los demás.
- **Base**: PostgreSQL **17.11** en `127.0.0.1:5432/libreria`, en head `c8d2dea5529f`, con el estado
  del seed (5 usuarios, 5 libros 10/5/8/3/1, venta 1 = 69000.00, 7 movimientos, 1 evento SISTEMA,
  invariante de stock en 0 filas).
- **Evidencia usada**: código bajo `parcial/app/`, `parcial/migrations/`, `parcial/main.py`;
  `docs/CHECKLIST_ENTREGA.md`; `CHANGES.md`; los changes archivados en `openspec/changes/archive/`
  (`proposal`, `design`, `tasks`, specs); `parcial/test/` (5 `.http`, `solo_agregado.sql`,
  `EVIDENCIA.md`, `evidencia/*.txt`) y `parcial/tests/`.
- **Límite transversal**: los casos de escritura (201/204/409/200 de mutaciones, re-ejecución de la
  suite, idempotencia del seed) se acreditan por evidencia registrada + lectura de código, no por
  re-ejecución. Cuando un informe decía «PASS (por evidencia)» se conservó esa calificación.

---

## 6. Estado de los informes y qué falta antes de C-20

**Los 19 informes existen, son legibles y cubren C-01…C-19**: `c-01` … `c-19`, uno por change, con
veredicto explícito, tabla por ítem, evidencia y hallazgos priorizados. No hay changes sin auditar ni
informes incompletos. Consistencia cruzada: el defecto de defaults congelados aparece identificado de
forma coincidente en C-04, C-13, C-15, C-16, C-17, C-18 y C-19; el path de `/mis-ventas` sólo lo
detecta C-10 (C-13, C-14, C-15 y C-16 lo dan por bueno porque verificaron la conducta en el path
existente, no el path de la consigna).

**Bloquea el cierre (debe resolverse antes de tocar C-20)**:

1. **B-1** — mover `/mis-ventas` a su path canónico y corregir tests/evidencia (C-10). Sin esto, §6.7
   falla y C-19/C-18 quedan con evidencia de un path que la consigna no admite.
2. **B-2** — migración nueva que reemplace los defaults congelados + `sa.text("now()")` en los
   modelos (C-04). Sin esto, §3 falla y los eventos y movimientos que generen C-20/C-21 (y el seed en
   la demo) seguirán sellados con la hora de la migración.

**Recomendado antes de C-20 (no bloquea el build de la imagen, sí la calidad de la entrega)**: M-1
(actor del movimiento, porque el VPS mostrará `usuario_id` incorrecto en las evidencias), M-2
(paginación estable) y M-4 (mensajes). M-3 y los menores pueden ir en el mismo barrido o en un change
correctivo propio, pero conviene resolverlos antes de C-22 para no reabrir la suite.

**Fuera del alcance de esta auditoría**: §11 (Docker, VPS, `D-01…D-08`) y §13 (autoevaluación) siguen
pendientes y dependen de **C-20**, **C-21** y **C-22**, los tres en `[ ]`. Cuando B-1 y B-2 estén
cerrados, el repo queda apto para arrancar C-20 con `C-01` como única dependencia ya cumplida.
