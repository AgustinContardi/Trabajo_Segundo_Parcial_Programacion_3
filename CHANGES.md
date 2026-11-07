# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Parcial Cap. 1-6 — «la librería»**: el TP de los
> capítulos 1 a 4 (catálogo, clientes, ventas), más el acceso con usuarios y roles (cap. 5), la capa de
> repositorios + Unit of Work (cap. 6) y el despliegue del TP original en un contenedor sobre el VPS.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

**Fuentes, en orden de autoridad**

| Fuente | Para qué sirve |
|---|---|
| `docs/Parcial_Cap1a6_Consigna.pdf` (24 p.) | Qué se pide. Nada de este plan existe si no está ahí o no es consecuencia directa. |
| `docs/CHECKLIST_ENTREGA.md` (14 secciones, 136 ítems) | **Criterio de aceptación**: cada change cita las secciones/ítems que satisface. |
| `knowledge-base/` (12 archivos) | Cómo está pensado el sistema: modelo, reglas (`RN-01…RN-16`), flujos, arquitectura, despliegue. |

Los códigos `CV-NN` (convención de ingeniería, del checklist heredado) y `RD-NN` (regla propia del
equipo) **no son de la consigna** y se marcan como tales en el scope. Los `RN-NN` sí lo son y no se
redefinen.

---

## Cómo usar este documento

1. **Identificar el change** — mirar el árbol de dependencias y los `GATE`: el próximo change es el que
   tiene **todas** sus dependencias en `[x]`. No adelantar por comodidad.
2. **Leer la KB** — los 3-5 archivos de la sección **Leer antes** del change, con la sección indicada.
   Leer también la **Aceptación**: son los ítems del checklist que hay que poder correr.
3. **Proponer** — `/opsx:propose C-NN-{nombre}` usando el **Scope** del bloque como insumo.
4. **Aplicar** — `/opsx:apply C-NN-{nombre}`. Al terminar, correr **literalmente** los comandos de la
   Aceptación; si el comando no se puede correr, el ítem no está cumplido.
5. **Archivar** — `/opsx:archive C-NN-{nombre}` y marcar el change como `[x]` en este archivo.

> **Frase de cierre del checklist:** «Si un caso `C-NN` no se corrió literalmente, no está verificado.
> Si el JSON real no se miró, no está verificado. Si no se corrió en una carpeta limpia, no está
> verificado.»

---

## Árbol de dependencias

```
C-01 baseline-tp-y-fundacion
 ├─> C-02 core-repositorios-uow-paginacion
 │    └─> C-05 errores-paginacion-contratos
 │         ├─> C-06 capas-editoriales-generos-autores
 │         │    └─> C-08 capas-libros-alta-stock-inicial              (+ C-03)
 │         │         ├─> C-09 libros-baja-reposicion-movimientos
 │         │         └─> C-10 capas-ventas-lecturas                    (+ C-07)
 │         ├─> C-07 capas-clientes-y-perfil                            (+ C-03)
 │         │    └─> C-12 auto-registro-atomico                         (+ C-11)
 │         └─> C-11 seguridad-login-cookie                             (+ C-03)
 │              └─> C-13 requiere-rol-y-yo                             (+ C-03)
 │                   ├─> C-14 cambio-password-grupos-de-rutas
 │                   │    └─> C-15 admin-usuarios-roles-eventos
 │                   └─> C-16 venta-transaccional                      (+ C-08, C-10)
 ├─> C-03 modelos-acceso-stock
 │    └─> C-04 migraciones-0003-0004
 └─> C-20 imagen-docker-tp-cap1a4                                      (vía despliegue)
      └─> C-21 despliegue-vps-deploy-md

CIERRE
 C-09 + C-15 + C-16 ──> C-17 seed-libreria
 C-12 + C-14 + C-17 ──> C-18 casos-c-http-y-solo-agregado
 C-18 ────────────────> C-19 suite-pytest-y-evidencia
 C-18 + C-19 + C-21 ──> C-22 entrega-zip-y-autoevaluacion
```

Las marcas `(+ C-NN)` son dependencias adicionales que no se dibujan para no cruzar el árbol.

### Paralelismo por fase (GATES)

```
GATE 0: C-01 ✓                                    ← PRIMER FORK (tres vías)
  → C-02 core-repositorios-uow-paginacion         [Agente A]
  → C-03 modelos-acceso-stock                     [Agente B]
  → C-20 imagen-docker-tp-cap1a4                  [Agente C — vía despliegue, sólo depende de C-01]

GATE 1: C-02 ✓ · C-03 ✓ · C-20 ✓
  → C-05 errores-paginacion-contratos             [Agente A]
  → C-04 migraciones-0003-0004                    [Agente B — si C-03 ✓]
  → C-21 despliegue-vps-deploy-md                 [Agente C — si C-20 ✓]

GATE 2: C-05 ✓ · C-04 ✓                           ← FORK
  → C-06 capas-editoriales-generos-autores        [Agente A]
  → C-07 capas-clientes-y-perfil                  [Agente B — si C-03 ✓]
  → C-11 seguridad-login-cookie                   [Agente C — si C-03 ✓]

GATE 3: C-06 ✓ · C-07 ✓ · C-11 ✓
  → C-08 capas-libros-alta-stock-inicial          [Agente A — si C-03 ✓]
  → C-12 auto-registro-atomico                    [Agente B]
  → C-13 requiere-rol-y-yo                        [Agente C — si C-03 ✓]

GATE 4: C-08 ✓ · C-12 ✓ · C-13 ✓                  ← FORK
  → C-09 libros-baja-reposicion-movimientos       [Agente A]
  → C-10 capas-ventas-lecturas                    [Agente B — si C-08 ✓]
  → C-14 cambio-password-grupos-de-rutas          [Agente C]

GATE 5: C-09 ✓ · C-10 ✓ · C-14 ✓                  ← FORK
  → C-16 venta-transaccional                      [Agente A — si C-13 ✓]
  → C-15 admin-usuarios-roles-eventos             [Agente B]
  → apoyo a C-22 (README de `parcial/` + `env.example`) [Agente C]

GATE 6: C-15 ✓ · C-16 ✓
  → C-17 seed-libreria                            [Agente A]
  → reverificación de D-04 y D-08 en el VPS       [Agente C]

GATE 7: C-17 ✓
  → C-18 casos-c-http-y-solo-agregado             [Agentes A + B + C, repartidos por módulo]

GATE 8: C-18 ✓
  → C-19 suite-pytest-y-evidencia                 [Agente B]

GATE 9: C-18 ✓ · C-19 ✓ · C-21 ✓
  → C-22 entrega-zip-y-autoevaluacion             [Agentes A + C]
```

**Regla de los gates:** la vía de despliegue (`C-20`, `C-21`) **no** espera al resto del parcial. Vale
18 % de la nota (11 % imagen + 7 % VPS) y es la única que depende de un recurso externo —las
credenciales y la base que provee la cátedra—, así que arranca en `GATE 0` y se sostiene hasta el final.

### Camino crítico (11 changes — mínimo irreducible)

```
C-01 → C-02 → C-05 → C-11 → C-13 → C-14 → C-15 → C-17 → C-18 → C-19 → C-22
```

Base → núcleo de capas → contratos/errores → login → autorización por rol → cambio obligatorio →
administración de roles → datos iniciales → casos C → evidencia → entrega.

Cadena alternativa (más corta, por la venta transaccional): `C-01 → C-02 → C-05 → C-08 → C-16 → C-17 →
C-18 → C-19 → C-22`. La cadena de autenticación/autorización es la que manda: **14 % + 12 %** de la nota
y la que más traps tiene (IN-03, RN-06, RN-04).

### Plan óptimo con 3 agentes

| Paso | Agente A (Backend Core: catálogo/libros/ventas) | Agente B (Backend Aux: clientes/datos/tests) | Agente C (Auth, seguridad y despliegue) |
|---|---|---|---|
| 1 | C-01 baseline-tp-y-fundacion | — pide al grupo el TP cap. 1-4 entregado | — |
| 2 | C-02 core-repositorios-uow-paginacion | C-03 modelos-acceso-stock | C-20 imagen-docker-tp-cap1a4 |
| 3 | C-05 errores-paginacion-contratos | C-04 migraciones-0003-0004 | C-21 despliegue-vps-deploy-md |
| 4 | C-06 capas-editoriales-generos-autores | C-07 capas-clientes-y-perfil | C-11 seguridad-login-cookie |
| 5 | C-08 capas-libros-alta-stock-inicial | C-12 auto-registro-atomico | C-13 requiere-rol-y-yo |
| 6 | C-09 libros-baja-reposicion-movimientos | C-10 capas-ventas-lecturas | C-14 cambio-password-grupos-de-rutas |
| 7 | C-16 venta-transaccional | C-15 admin-usuarios-roles-eventos | apoyo a C-22 (README + `env.example`) |
| 8 | C-17 seed-libreria | — | reverifica D-04/D-08 en el VPS |
| 9 | C-18 casos-c-http-y-solo-agregado | C-18 (casos de clientes/ventas) | C-18 (casos de auth/roles) |
| 10 | C-22 entrega-zip-y-autoevaluacion | C-19 suite-pytest-y-evidencia | C-22 (revisión de §12 en carpeta limpia) |

Los tres agentes terminan casi juntos: A y B cargan con los módulos y los datos; C carga con los 30
puntos de auth/autorización y con los 18 del despliegue, que son los dos bloques donde un error se paga
caro pero donde el trabajo es más acotado.

---

## FASE 1 — Base y fundación

> El TP cap. 1-4 entra al repo y se lo deja cumpliendo la estructura, la configuración y el ciclo de vida
> del parcial. Sin esta fase no hay dónde escribir nada: de acá salen `parcial/`, `despliegue/` y las dos
> ramas paralelas del plan.

### [C-01] baseline-tp-y-fundacion

- **Estado**: `[x]` cerrado — mitad (A) implementada y verificada; mitad (B) cerrada: TP cap. 1-4
  implementado desde la consigna (`docs/TP_Cap1a4_Consigna (1).pdf`), adoptado en `parcial/`,
  copiado intacto a `despliegue/`, migraciones `0001`/`0002` aplicadas, baseline documentado en
  `docs/BASELINE_TP_CAP1a4.md`. Change OpenSpec:
  `openspec/changes/c-01-baseline-tp-y-fundacion/` · handoff: `docs/HANDOFF_BASELINE_TP_CAP1a4.md`.
- **Scope**:
  - Traer el **TP cap. 1-4 ya entregado** a `parcial/` (código, `requirements.txt`, `alembic.ini`,
    `migrations/0001` y `0002`) y una copia **intacta** a `despliegue/`. No reescribir su lógica
    (consigna p. 2 y Ej. 9).
  - Cerrar las columnas heredadas contra el repo del TP y dejarlas escritas en
    `docs/BASELINE_TP_CAP1a4.md`: `SU-01` (tipo de `id`), `SU-07` (`venta.usuario_id`), `SU-08` (nombre
    del precio copiado), `SU-09` (revisiones de las migraciones 1 y 2).
  - `app/core/config.py`: `Settings` con las 13 variables (`CV-09`), URL con `@computed_field` y driver
    `postgresql+asyncpg`, `POSTGRES_PASSWORD` y `JWT_SECRET` **sin default**.
  - `app/core/database.py` + `main.py`: motor y `async_sessionmaker` creados **en el `lifespan`** y
    guardados en `app.state` (`pool_size=POOL_SIZE`, `expire_on_commit=False`), `get_session` con una
    sesión por petición que cierra al terminar, `hash_ficticio` calculado **una vez**, `dispose()` al
    apagar.
  - `app/modules/health/router.py` (y **sólo** `router.py`) con `GET /health/live` y
    `GET /health/ready` (`SELECT 1`, 503 si la base no contesta).
  - `alembic.ini` **sin** `sqlalchemy.url`; `migrations/env.py` lee de `Settings`; `env.example` (sin
    punto inicial) con todas las variables y ningún secreto; `.gitignore` con `.env`.
  - `requirements.txt` con las versiones mínimas de la consigna; `app/__init__.py` y los `__init__.py`
    de cada paquete.
- **Dependencias**: ninguna
- **Governance**: **CRÍTICO** — es la base de todo y una de las condiciones que anulan la corrección («un
  proyecto que no levanta»); además decide si el TP heredado se puede o no adoptar sin reescribirlo.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §0: los paths exactos (`CV-03`), sin credenciales en `alembic.ini` ni en el repo.
  - §1: `main.py` con `lifespan`, `health` con sólo `router.py`, `env.example` sin punto,
    `.gitignore` con `.env`, y `grep -rn "create_all"` vacío (`CV-14`).
  - §2: los seis primeros ítems (Settings completo, `@computed_field`, secretos sin default, motor en
    `lifespan`, `alembic.ini` limpio).
  - §10: todos los handlers existentes son `async def`.
  - §13, fila «Proyecto, configuración y ciclo de vida» (6 %).
  - Reglas: base de `RN-08` (hash ficticio), `RN-15` (sin `debug=True`).
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — §Estructura de directorios, §Configuración, §Ciclo de vida
  - `knowledge-base/02_descripcion_general.md` — stack con versiones mínimas
  - `knowledge-base/10_preguntas_abiertas.md` — §2 (columnas heredadas a confirmar)
  - `knowledge-base/11_despliegue_y_devops.md` — §Regla de oro: son dos proyectos distintos
  - `knowledge-base/09_decisiones_y_supuestos.md` — DD-01, DD-10, SU-01, SU-07, SU-08, SU-09

### [C-02] core-repositorios-uow-paginacion

- **Estado**: `[x]` cerrado — archivado como `2026-11-05-c-02-core-repositorios-uow-paginacion`. Entrega `BaseRepository[T]` + `SoftDeleteRepository[T]` (`parcial/app/core/repository.py`), `UnitOfWork` (`parcial/app/core/unit_of_work.py`) y `Pagina[T]` + `paginar()` (`parcial/app/core/paginacion.py`). Verificado: imports OK, py_compile OK, sin `commit()` en repositorios, sin `close()` en UoW, sin `create_all`.
- **Scope**:
  - `app/core/repository.py`: `BaseRepository[T]` con constructor `(session, model_class)` —los genéricos
    se borran en runtime— y `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `add`/`update`
    hacen **`flush()`**, nunca `commit()`.
  - `SoftDeleteRepository[T]`: hereda, filtra `borrado_en IS NULL` por defecto y agrega
    `get_by_id_including_deleted` y `soft_delete`, que **no** existen en la clase base.
  - `app/core/unit_of_work.py`: `UnitOfWork` como gestor de contexto asíncrono — commit en `__aexit__`
    sin excepción, rollback con excepción, **no cierra** la sesión.
  - `app/core/paginacion.py`: tipo `Pagina[T]` y función `paginar(...)` que devuelve
    `{items, total, page, size, pages}` y valida `page ≥ 1`, `size` 1..100 (default 20), página fuera de
    rango → 422 con mensaje propio, cero resultados → una página vacía (`pages: 1`).
  - Plantilla de `<módulo>/unit_of_work.py` que compone los repositorios del módulo con **la misma**
    sesión (se replica en `C-06`…`C-10` y `C-15`).
  - Comentario de contrato en cada archivo: quién construye, quién abre, quién confirma, quién cierra
    (`CV-01`).
- **Dependencias**: `C-01`
- **Governance**: **CRÍTICO** — «Repositorios y Unit of Work» es el criterio más pesado de la rúbrica
  (16 %) y esta clase es la que lo garantiza en todos los módulos.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §7: «`BaseRepository[T]` recibe `(session, model_class)`…», «Ningún repositorio hace `commit()`…»,
    «El UoW base confirma…, revierte… y **no cierra** la sesión», «Cada módulo tiene su UoW…».
  - §9: «Todo listado devuelve `{items, total, page, size, pages}`» y «`size` va de 1 a 100 con default
    **20**».
  - §13, fila «Repositorios y Unit of Work» (16 %).
  - Reglas: soporte de `RN-02`, `RN-10`, `RN-16` (una operación = un `async with`).
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — §Qué puede y qué no puede cada capa, §El Unit of Work, §Los dos repositorios
  - `knowledge-base/05_reglas_de_negocio.md` — §Convenciones de ingeniería (`CV-01`), §Reglas de diseño propias
  - `knowledge-base/07_flujos_principales.md` — leyenda de fronteras de transacción (`[TX]`)
  - `knowledge-base/04_modelo_de_datos.md` — §libro (`borrado_en`) para el filtro del repositorio

---

## FASE 2 — Esquema versionado

> Los modelos primero y las migraciones después, en ese orden y sin `create_all` (`CV-14`): la tercera
> migración se **lee antes de aplicarla** y la cuarta se escribe a mano porque `autogenerate` no ve
> funciones ni disparadores.

### [C-03] modelos-acceso-stock

- **Estado**: `[x]` cerrado — archivado como `2026-11-05-c-03-modelos-acceso-stock`. Entrega los modelos de acceso (`Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad`), `MovimientoStock`, `Libro.borrado_en` con índice parcial del ISBN, y `Cliente.usuario_id` nullable+UNIQUE con navegación en ambos extremos. Verificado: configure_mappers OK, columnas exactas (6/7/5/4/7), sin float, sin create_all.
- **Scope**:
  - `app/modules/usuarios/models.py`: `Usuario` (6 columnas, `email` **UNIQUE**, **sin** columna `rol`),
    `AsignacionRol` (7 columnas, `CHECK (rol IN ('ADMIN','VENDEDOR','CLIENTE'))`, **índice único parcial**
    `(usuario_id, rol) WHERE revocada_en IS NULL` con `postgresql_where`, índices en `usuario_id` y
    `otorgada_por`), `IntentoAcceso` (5 columnas + índice `(email, ip, cuando)`), `EventoSeguridad`
    (4 columnas, `actor` **Text**, sin FK ni CHECK).
  - `app/modules/libros/models.py`: `MovimientoStock` (7 columnas, `venta_id` nulo, `CHECK (cantidad <> 0)`,
    índice en cada FK), `Libro.borrado_en` (`timestamptz`, nulo) y **reemplazo** del `UNIQUE(isbn)` por el
    índice único parcial `(isbn) WHERE borrado_en IS NULL`; se conservan `CHECK (precio > 0)` y
    `CHECK (stock >= 0)`; `LibroAutor` sin cambios.
  - `app/modules/clientes/models.py`: `Cliente.usuario_id` **nulo permitido** + `UNIQUE` + FK; navegación
    declarada en **los dos extremos** (`Cliente.usuario` devuelve un objeto, no una lista; `Usuario.cliente`);
    `PerfilCliente` 1—1 intacto.
  - Convenciones de tipo: fechas nuevas `timestamptz`, dinero `Numeric`/`Decimal` (nunca `float`), cada FK
    nueva con su índice.
  - Asignación obligatoria de entidades a módulos: `AsignacionRol`/`IntentoAcceso`/`EventoSeguridad` en
    `usuarios`; `MovimientoStock` y `LibroAutor` en `libros`; `PerfilCliente` en `clientes`;
    `RenglonVenta` en `ventas`.
- **Dependencias**: `C-01`
- **Governance**: **ALTO** — el modelo de datos pesa 10 % y es lo que todo lo demás referencia; un nombre
  de columna cambiado invalida los casos de prueba y la corrección.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §4: `usuario` (6 columnas, `email` UNIQUE, sin `rol`), `asignacion_rol` (7 columnas + CHECK), índice
    único parcial con `postgresql_where`, `libro.borrado_en` + índice parcial del ISBN, `cliente.usuario_id`
    nulo y UNIQUE, `Cliente.usuario` como objeto con navegación en los dos extremos, `movimiento_stock`
    (7 columnas, `venta_id` nulo, `cantidad <> 0`), `intento_acceso` (5 columnas + índice), `evento_seguridad`
    (4 columnas, `actor` texto sin FK), `perfil_cliente` 1—1.
  - §1: entidades en su módulo obligatorio.
  - Reglas: `RN-01`, `RN-03`, `RN-12`, `RN-13`, `RN-16`.
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — §ERD, §Entidades (todas), §Índices y restricciones
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-01, §RN-03, §RN-12, §RN-13, §RN-16
  - `knowledge-base/03_actores_y_roles.md` — §Los roles viven en su propia tabla
  - `knowledge-base/10_preguntas_abiertas.md` — §2 (columnas heredadas), AB-07, AB-02

### [C-04] migraciones-0003-0004

- **Estado**: `[x]` cerrado — archivado como `2026-11-05-c-04-migraciones-0003-0004`. Entrega `0003` (autogenerada, leída y corregida a mano: 8 piezas, índices parciales, timestamptz, FKs con índice) y `0004` (trigger append-only sobre `movimiento_stock`, escrita a mano). Round-trip `upgrade head → downgrade base → upgrade head` OK, `alembic check` limpio, sin `create_all`.
- **Scope**:
  - `0003_...`: `alembic revision --autogenerate` contra una base con el esquema del TP aplicado;
    **leerla entera antes de aplicarla** y corregir a mano lo que la comparación no infiere bien (tipos,
    `postgresql_where` de los dos índices parciales, `borrado_en` como `timestamptz`, los índices de las
    FKs nuevas).
  - Verificar que la tercera trae las **8 piezas**: 4 tablas de acceso, `movimiento_stock`,
    `cliente.usuario_id`, `libro.borrado_en` y los **dos** índices únicos parciales.
  - Comentario de cabecera en `0003` que diga que se leyó antes de aplicar y **qué** se corrigió a mano.
  - `0004_...` **escrita a mano**: `CREATE FUNCTION` + `CREATE TRIGGER` que rechazan **cualquier**
    `UPDATE` o `DELETE` sobre `movimiento_stock`; `downgrade` con `DROP TRIGGER` **y** `DROP FUNCTION`.
  - Round-trip sobre base vacía: `upgrade head` → `downgrade base` → `upgrade head`, y `alembic check`
    sin diferencias (`CV-10`).
  - Sin `create_all` en ningún lado (`CV-14`).
- **Dependencias**: `C-03`
- **Governance**: **CRÍTICO** — «que no crea su esquema con `alembic upgrade head` sobre una base vacía»
  anula la corrección; además `RN-12` se juega entero acá (10 % de integridad).
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §3 **completo**: exactamente cuatro versiones, las 8 piezas de la tercera, comentario de lectura,
    función + disparador + `downgrade` en la cuarta, round-trip, `alembic check`, FKs con índice y tipos.
  - §13, fila «Modelos, relaciones y migraciones» (10 %) y fila «Integridad» (10 %, cuarta migración).
  - Reglas: `RN-12`; `DD-04`, `DD-09`.
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — §Migraciones
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-12 (garante: disparador en migración)
  - `knowledge-base/04_modelo_de_datos.md` — §movimiento_stock, §Índices y restricciones
  - `knowledge-base/09_decisiones_y_supuestos.md` — DD-04, DD-09, SU-09

---

## FASE 3 — Convenciones de contrato, errores y paginación

> Una sola fase para las reglas transversales que todos los módulos van a repetir. Se hace **antes** de
> los módulos para no reescribirlos después.

### [C-05] errores-paginacion-contratos

- **Estado**: `[x]` cerrado — archivado como `2026-11-05-c-05-errores-paginacion-contratos`. Entrega `app/core/errors.py` (traducción de `IntegrityError` por constraint, handler de `RequestValidationError`, `SinNulMixin`, validador de 72 bytes), handler registrado en `main.py`, `paginar()` conectado en todos los listados, base de schemas `Create/Update/Read` con `extra="forbid"` en 29 ocurrencias y sin `password_hash`. Verificado: 422 para id no entero/JSON malformado/NUL/extra/73 bytes; paginación con mensaje propio y cero resultados; unicidades/FKs/CHECKs traducidos a 409/422; `alembic check` limpio; sin `create_all`.
- **Scope**:
  - Traducción del `IntegrityError` por **nombre de constraint** a 409/422 con mensaje propio en español,
    en segunda persona y sin jerga de base (`RD-03`); el texto de PostgreSQL **nunca** sale al cliente
    (`RN-15`).
  - Manejador propio de `RequestValidationError`: `{id}` no entero, `size` fuera de rango, JSON malformado,
    NUL en un string y contraseña de 73 bytes dan **422** y **nunca** 500.
  - `paginar()` conectado en todos los listados existentes: `page` desde 1, `size` 1..100 (default 20),
    página fuera de rango → 422 («La página 4 no existe: hay 3»), cero resultados → `items: []`,
    `total: 0`, `pages: 1`, y `total` contado **con los mismos filtros** que la página.
  - Base de schemas por módulo: un `Create`, un `Update` y un `Read` por entidad, todos con
    `extra="forbid"`, los PATCH aplicando `exclude_unset`, y **ningún** `password_hash` en un schema
    (`CV-07`).
  - Orden de resolución de errores 404 → 403 → 409 → 422 (`CV-08`) documentado en el servicio de cada
    módulo.
- **Dependencias**: `C-02`
- **Governance**: **ALTO** — 8 % de contratos + `RN-15` atraviesa todos los módulos; si esta fase queda
  floja, cada módulo posterior arrastra el defecto.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §9 **completo** (envoltorio, `page`/`size`, página inexistente, `total` con los mismos filtros,
    ningún texto interno, ninguna entrada inválida en 500, búsqueda con parámetros ligados,
    `extra="forbid"`/`exclude_unset` y códigos).
  - §0: «Ninguna respuesta incluye `password_hash`».
  - §10, C-01 (422 sin ejecutar el handler) y C-16 (búsqueda y paginación) como casos que habilitan.
  - Reglas: `RN-15`, `RN-09` (precio/total fuera del cuerpo); `CV-07`, `CV-08`, `RD-03`.
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-15, §Convenciones de ingeniería (`CV-07`, `CV-08`), §Reglas de diseño propias (`RD-03`)
  - `knowledge-base/08_arquitectura_propuesta.md` — §Errores y códigos
  - `knowledge-base/06_funcionalidades.md` — US-020, US-021, US-024
  - `knowledge-base/07_flujos_principales.md` — §Resumen de fronteras transaccionales

---

## FASE 4 — Capas en los módulos heredados

> El TP cap. 1-4 pasa a seis capas con repositorios + Unit of Work; **los servicios dejan de recibir la
> sesión**. Acá se construye casi todo el 16 % de la rúbrica y el 10 % de integridad del stock.

### [C-06] capas-editoriales-generos-autores

- **Estado**: `[x]` cerrado - archivado como `2026-11-05-c-06-capas-editoriales-generos-autores`. Refactor de editoriales/generos/autores a seis capas (repository + unit_of_work + service sin AsyncSession + router que construye el UoW), listados paginados, PATCH editorial/autor, listado de libros por entidad excluyendo borrados. Verificado: py_compile OK, import main OK, grep invariants vacios, runtime end-to-end contra PostgreSQL.
- **Scope**:
  - Los tres módulos con sus seis capas (`models`, `schemas`, `repository`, `unit_of_work`, `service`,
    `router`); repositorios por entidad y UoW que los compone con la misma sesión.
  - `POST /editoriales`, `/generos`, `/autores` → **201**; duplicado → **409** con mensaje propio
    (`RN-01`).
  - `PATCH /editoriales/{id}` y `PATCH /autores/{id}` → 200 aplicando sólo lo enviado; 404 recurso de la
    ruta; 409 unicidad; 422 contrato.
  - Listados paginados con el envoltorio y `GET /editoriales/{id}/libros`, `/generos/{id}/libros`,
    `/autores/{id}/libros` (404 si el id no existe), sin libros dados de baja.
  - El router **construye** el UoW con una dependencia y lo pasa; el servicio lo **abre** con
    `async with` y nunca lo construye (`CV-01`); la precarga vive sólo en `repository.py` (`CV-02`).
  - Tests de la capa: `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py` vacío.
- **Dependencias**: `C-05`
- **Governance**: **MEDIO** — CRUDs simples, pero son el patrón que copian los otros módulos; un error de
  molde se replica cuatro veces.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §1: los módulos `editoriales`, `generos` y `autores` con las seis capas.
  - §7: «Ningún servicio recibe una `AsyncSession` ni construye su UoW» y «Toda precarga vive en
    `repository.py`» (`CV-02`).
  - §9: envoltorio y códigos de los listados y de los PATCH.
  - Reglas: `RN-01`, `RN-15`; `CV-01`, `CV-02`.
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — §Qué puede y qué no puede cada capa, §Asignación de entidades a módulos
  - `knowledge-base/04_modelo_de_datos.md` — §editorial, §genero, §autor, §libro_autor
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-01
  - `knowledge-base/06_funcionalidades.md` — US-022

### [C-07] capas-clientes-y-perfil

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-07-capas-clientes-y-perfil`. C-13 completó la autorización que faltaba: `GET /clientes/{id}/ventas` responde 401 sin cookie, 403 a CLIENTE y 200 a VENDEDOR/ADMIN con el envoltorio paginado, y el servicio recibe la identidad actual (`IdentidadActual`). Verificado: 105 pruebas pasan contra PostgreSQL 17 local.
- **Scope**:
  - Módulo `clientes` con sus seis capas; `ClienteRepository` con precarga de `perfil` y de `usuario`
    declarada en el método que la necesita.
  - `Cliente.usuario_id` **nulo permitido** y `UNIQUE`: el cliente de mostrador no tiene acceso web y un
    usuario no puede colgar de dos fichas.
  - `POST /clientes` → 201 con `usuario_id` nulo; 409 si el correo ya existe; 422 por campos de más.
  - `GET /clientes/{id}` → 200 con su perfil si lo tiene; `PATCH /clientes/{id}` → 200 sólo con lo
    enviado; 404 inexistente; 409 correo que choca.
  - `POST /clientes/{id}/perfil` → 201, 404 cliente inexistente, 409 si ya tiene perfil.
  - `GET /clientes/{id}/ventas` → 200 paginado, 404 si el cliente no existe y **403** si quien pide es
    CLIENTE (`RN-14`).
- **Dependencias**: `C-03`, `C-05`
- **Governance**: **ALTO** — el `usuario_id` nullable/UNIQUE es lo que hace posible `RN-02` y `RN-14`; un
  `UNIQUE` mal puesto rompe el auto-registro o el cliente de mostrador.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §4: `cliente.usuario_id` nulo y UNIQUE; `Cliente.usuario` devuelve un objeto con navegación en los
    dos extremos; `perfil_cliente.cliente_id` FK UNIQUE 1—1.
  - §6: «`GET /clientes/{id}/ventas` es de personal (VENDEDOR/ADMIN); un CLIENTE recibe **403**».
  - §1: módulo `clientes` con las seis capas y `PerfilCliente` en su módulo.
  - Reglas: `RN-01`, `RN-14`.
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — §cliente, §perfil_cliente
  - `knowledge-base/03_actores_y_roles.md` — §RBAC (filas de `/clientes`)
  - `knowledge-base/06_funcionalidades.md` — US-030…US-033
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-01, §RN-14

### [C-08] capas-libros-alta-stock-inicial

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-08-capas-libros-alta-stock-inicial`. Modulo `libros` a seis capas con LibroRepository(SoftDeleteRepository), punto unico de escritura de stock (`aplicar_movimiento`), alta con `stock_inicial` + autores + movimiento 'Stock inicial', PATCH solo titulo/precio, listados paginados con filtro titulo/genero y busqueda con parametro ligado. Verificado: py_compile OK, import main OK, grep invariants vacios, smoke test 201 + invariante stock.
- **Scope**:
  - Módulo `libros` con sus seis capas; `LibroRepository(SoftDeleteRepository[Libro])` que filtra los
    dados de baja y precarga editorial, género y autores.
  - **Punto único de escritura de stock**: un solo método que escribe `libro.stock` **y** agrega el
    `movimiento_stock` en el mismo lugar; lo usan el alta, la reposición y la venta (`RN-11`). Etiquetas
    de `motivo`: `'Stock inicial'`, `'Reposición'`, `'Venta'` (`RD-02`).
  - `POST /libros` con `stock_inicial` (**no** `stock`) y `autores: [{autor_id, rol, orden}]`: libro +
    `libro_autor` + movimiento «Stock inicial» en **un** `async with`; 201; 409 si el ISBN choca con un
    libro **vigente** o si una FK no existe; 422 si `precio <= 0` o `stock_inicial < 0`.
  - `PATCH /libros/{id}` acepta **sólo** título y precio; mandar `stock` → **422**.
  - Lecturas: `GET /libros` (`page`, `size`, `titulo`, `genero_id`) con envoltorio y exclusión de borrados,
    `GET /libros/{id}` y los listados por editorial/género/autor; búsqueda con `ilike` y **parámetro
    ligado** (sin concatenar).
- **Dependencias**: `C-03`, `C-05`, `C-06`
- **Governance**: **CRÍTICO** — acá se define el punto único de stock: si alguien escribe `libro.stock`
  por fuera, la igualdad `stock = SUM(movimiento_stock.cantidad)` se rompe y fallan **todos** los casos de
  venta (`RN-10`, `RN-11`).
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §8: «`POST /libros` recibe `stock_inicial`… y deja el movimiento «Stock inicial»»; «`PATCH /libros/{id}`
    sólo acepta título y precio; mandar `stock` da 422»; búsqueda con `' OR '1'='1` sin romper.
  - §4: índice parcial del ISBN, `CHECK (precio > 0)` y `CHECK (stock >= 0)`.
  - §7: «El stock se escribe en **un único punto**, usado por el alta, la reposición y la venta».
  - §10, C-13 y C-16 (parte de alta, re-alta y PATCH).
  - Reglas: `RN-01`, `RN-11`, `RN-15`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 6 (alta de libro con stock inicial)
  - `knowledge-base/04_modelo_de_datos.md` — §libro, §libro_autor, §movimiento_stock
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-01, §RN-11, §RN-13
  - `knowledge-base/08_arquitectura_propuesta.md` — §Los dos repositorios

### [C-09] libros-baja-reposicion-movimientos

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-09-libros-baja-reposicion-movimientos`. Baja logica (DELETE 204 + borrado_en), reposicion (POST 200 + movimiento 'Reposicion'), GET /libros/{id}/movimientos, re-alta por ISBN dado de baja (201) y segundo vigente (409) via indice parcial. Verificado: py_compile OK, import main OK, grep invariants vacios, smoke test 204/200/409/201.
- **Scope**:
  - `DELETE /libros/{id}` → **204** y escribe `borrado_en = now()` (baja lógica); el libro desaparece de
    **todos** los listados y del detalle público; repetir la baja o un id inexistente → **404**.
  - `POST /libros/{id}/reponer` → **200** con el libro actualizado; `cantidad > 0` (si no, 422); libro
    dado de baja → **409**; usa el punto único de stock y deja el movimiento de entrada.
  - `GET /libros/{id}/movimientos` → **200** con `cantidad` firmada, `motivo`, `cuando`, `usuario_id` y
    `venta_id` (nulo si no vino de una venta).
  - Re-alta con el ISBN de un libro dado de baja → **201**; un segundo libro **vigente** con ese ISBN →
    **409**. Lo garantiza el índice único parcial, **no** una consulta previa.
  - La precarga de los renglones del detalle de venta **no** filtra borrados: una venta vieja sigue
    mostrando el título.
- **Dependencias**: `C-08`
- **Governance**: **ALTO** — `RN-13` cruza catálogo, ventas y stock; el error típico es un `UNIQUE` común
  en el ISBN que hace fallar C-13 sin que nada parezca roto.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §8: reponer 200 + movimiento; baja 204 y desaparición del catálogo; libro dado de baja no se vende ni
    se repone (409); baja repetida 404; re-alta 201 y segundo vigente 409; la venta vieja sigue mostrando
    el título.
  - §10, C-12 y C-13 completos.
  - Reglas: `RN-13`, `RN-01`, `RN-12`; `RD-02`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 7 (reponer) y Flujo 8 (baja lógica)
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-13, §RN-01
  - `knowledge-base/04_modelo_de_datos.md` — §libro (la trampa del ISBN), §Índices consolidados
  - `knowledge-base/06_funcionalidades.md` — US-025…US-027

### [C-10] capas-ventas-lecturas

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-10-capas-ventas-lecturas`. Modulo `ventas` a seis capas con VentaRepository con precarga fija (incluye borrados), GET /ventas/{id} sin requiere_rol, GET /mis-ventas solo sesion, sin PATCH, precarga solo en repository.py. Verificado: py_compile OK, import main OK, grep invariants vacios, runtime end-to-end.
- **Scope**:
  - Módulo `ventas` con sus seis capas; `VentaRepository` con la precarga de cliente, renglones y el
    libro de cada renglón —**incluidos los dados de baja**— declarada adentro del método que la necesita
    (`CV-02`): el número de consultas es **fijo** y no crece con los renglones.
  - `GET /ventas` (`page`, `size`) → 200 para VENDEDOR/ADMIN, con envoltorio y orden estable.
  - `GET /ventas/{id}` **sin `requiere_rol`**: personal → 200, dueño → 200, otro → **403**, inexistente →
    404. La decisión la toma el servicio (`RN-14`).
  - `GET /mis-ventas` (`page`, `size`) → 200 sólo con sesión: las ventas del cliente ligado por
    `usuario_id`; sin cookie → 401; un usuario sin ficha de cliente → página vacía (`SU-05`).
  - **No** existe `PATCH /ventas/{id}` (`RN-09`).
- **Dependencias**: `C-07`, `C-08`
- **Governance**: **ALTO** — «Lecturas sin N+1» (6 %) se corrige con `SQL_ECHO=true` contando `SELECT`, y
  `RN-14` es la regla que decide el 403 de lo ajeno.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §6: «`GET /ventas/{id}` **no** lleva `requiere_rol`…» y «`/mis-ventas` sólo pide estar autenticado…».
  - §8: «No existe `PATCH /ventas/{id}`» y el detalle muestra el título de un libro dado de baja.
  - §7: precarga sólo en `repository.py`.
  - §10, C-15 (misma cantidad de consultas con 2 y con 4 renglones) y C-06 (lo propio).
  - Reglas: `RN-09`, `RN-13`, `RN-14`; `CV-02`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 3 (autorización de una petición) y §Resumen de fronteras
  - `knowledge-base/03_actores_y_roles.md` — §Por qué `/ventas/{id}` no lleva `requiere_rol`
  - `knowledge-base/06_funcionalidades.md` — US-041…US-043
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-09, §RN-14

---

## FASE 5 — Autenticación

> 14 % de la nota y la zona con más trampas del parcial: el orden del login, el hash ficticio, el límite
> antes de verificar, el intento en su propia transacción y una cookie que **no** se rota al cambiar la
> contraseña.

### [C-11] seguridad-login-cookie

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-11-seguridad-login-cookie`. Implementa la base de autenticacion: `COOKIE_SECURE`, helpers bcrypt (`to_thread` + semaforo), JWT y cookie `HttpOnly`/`SameSite`/`Max-Age`/`Secure`, repositorio/UoW/servicio/router de `usuarios`, `POST /auth/login`, `POST /auth/logout`, `get_usuario_actual` leyendo solo `request.cookies` y registro de cada intento en transaccion propia (`IntentoAcceso.cuando` explicito para evitar el default de timestamp congelado de la migracion `dd4a0e5e9cf7`), con `Retry-After` como entero decimal en milisegundos. Verificado: 54 pruebas pasan contra PostgreSQL 17 local. No cierra la autorizacion por roles de C-13 ni el 403 pendiente de `GET /clientes/{id}/ventas` en C-07.
- **Scope**:
  - `app/core/security.py`: bcrypt con costo desde `BCRYPT_ROUNDS`; **toda** llamada envuelta en
    `to_thread` y bajo un semáforo de `BCRYPT_MAX_CONCURRENCY`; helpers de hash/verificación; JWT firmado
    con `sub`, `exp` y los roles vigentes al emitirlo (informativos); armado y borrado de la cookie.
  - `POST /auth/login`: **primero** el límite (una consulta de conteo sobre `intento_acceso` con la
    ventana de 60 s contada desde el último login exitoso de ese `email`+`ip`); si se superó → **429 +
    `Retry-After`** sin calcular ningún hash. **Después** la verificación contra el hash del usuario o
    contra el `HASH_FICTICIO` calculado en el `lifespan` (mismo cuerpo y mismo tiempo, `RN-08`).
  - La fila de `intento_acceso` se escribe **siempre**, en **sesión y transacción propias**, con el
    comentario de tres puntos que exige el Ej. 7 (qué hace distinto, por qué no comparte la transacción,
    cuál es su costo).
  - Éxito: roles vigentes leídos de la base → JWT → `Set-Cookie: access_token` con `HttpOnly`,
    `SameSite=Lax`, `Max-Age` = TTL y `Secure` configurable; el cuerpo **no** trae el token.
  - `POST /auth/logout` → 200 y `Max-Age=0`.
  - `get_usuario_actual` en `app/core/dependencies.py`: lee de `request.cookies` (nunca de
    `Authorization`), valida `exp` con PyJWT y responde **401** sin cookie, token inválido o vencido,
    usuario inexistente o `activo = false`.
- **Dependencias**: `C-02`, `C-03`, `C-05`
- **Governance**: **CRÍTICO** — autenticación es 14 % y el 429/401/anti-enumeración son los tres casos
  (C-03, C-04, C-05) donde un detalle de orden cambia el resultado.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §5: bcrypt desde `Settings` con `to_thread` + semáforo; `≤ 72 bytes` → 422 en los cuatro campos;
    cookie `HttpOnly`/`SameSite=Lax`/`Max-Age`/`Secure` y dependencia leyendo de `request.cookies`;
    JWT con `sub`, `exp` y roles, sin comparación con `iat`; límite **antes** de verificar con 429 +
    `Retry-After` en milisegundos; reinicio de la cuenta tras un login correcto; mismo cuerpo y tiempo
    con o sin correo; `logout` que borra la cookie y deja 401.
  - §7: el `intento_acceso` en sesión y transacción propias, con el comentario de tres puntos.
  - §2: el hash ficticio calculado **una vez** en el `lifespan`.
  - §10, C-03, C-04 y C-05.
  - Reglas: `RN-07`, `RN-08`, `RN-15`; `CV-09`; `DD-05`, `DD-07`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 2 (login con límite de intentos), completo
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-07, §RN-08
  - `knowledge-base/08_arquitectura_propuesta.md` — §Seguridad, §Ciclo de vida
  - `knowledge-base/03_actores_y_roles.md` — §401 vs 403
  - `knowledge-base/09_decisiones_y_supuestos.md` — DD-05, DD-07, SU-06, SU-11, SU-13

### [C-12] auto-registro-atomico

- **Estado**: `[x]` cerrado — archivado como `2026-11-07-c-12-auto-registro-atomico`. Implementa `POST /auth/registro` atómico: hash bcrypt antes de abrir el UoW y, en un solo `async with`, `usuario` + `asignacion_rol` con `rol = 'CLIENTE'` + ficha de `cliente` ligada por `usuario_id`; responde `201`, `409` propio para correo duplicado (sin apropiarse de la ficha existente) y `422` ante campos de más o contraseña de más de 72 bytes. Verificado contra PostgreSQL real: 22/22 tareas y suite completa 413 passed; sin migraciones (2026-11-07).
- **Scope**:
  - `POST /auth/registro` → **201** con `email`, `nombre` y `password`; `rol` **no** es un campo: mandarlo
    da **422** (`extra="forbid"`).
  - El hash bcrypt se calcula **antes** de abrir el UoW.
  - **Un solo** `async with uow` con las tres escrituras: `usuario`, `asignacion_rol` con
    `rol = 'CLIENTE'` (`desde = now()`, `vence_en` y `revocada_en` nulos) y `cliente` con `usuario_id`
    apuntando al usuario nuevo (`RN-02`).
  - Correo ya usado como **usuario** → 409; correo ya usado como **cliente** → 409 **sin apropiarse** de
    la ficha existente (no se le escribe `usuario_id`); ninguna de las dos deja filas sueltas.
  - Contraseña de más de **72 bytes** → 422; la respuesta no incluye `password_hash`.
- **Dependencias**: `C-07`, `C-11`
- **Governance**: **CRÍTICO** — `RN-02` es la operación que justifica el capítulo 6: tres escrituras que
  no tienen sentido por separado y un `409` que no debe tocar la ficha ajena.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §7: «El auto-registro (RN-02) escribe usuario + rol CLIENTE + ficha de cliente en **un** `async with
    uow` — forzar un fallo en la ficha → `SELECT count(*) FROM usuario` no crece».
  - §5: contraseña ≤ 72 bytes → 422; el hash antes de la transacción.
  - §10, C-02 completo (201; 409 de usuario y de cliente con mensaje propio; sin filas sueltas).
  - Reglas: `RN-01`, `RN-02`, `RN-15`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 1 (auto-registro), completo
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-02
  - `knowledge-base/06_funcionalidades.md` — US-001
  - `knowledge-base/04_modelo_de_datos.md` — §usuario, §asignacion_rol, §cliente

---

## FASE 6 — Autorización

> 12 % de la nota. La regla que ordena todo: los permisos se leen de la base **en cada petición**, y
> revocar un rol tiene efecto sobre una sesión ya abierta.

### [C-13] requiere-rol-y-yo

- **Estado**: `[x]` cerrado - archivado como `2026-11-06-c-13-requiere-rol-y-yo`. Implementa `IdentidadActual`, `get_sesion_actual` y `requiere_rol(*roles)` en `parcial/app/core/dependencies.py`, con los roles vigentes leídos de `asignacion_rol` en cada petición y la misma sesión del UoW (el claim `roles` del token es sólo informativo). Agrega `GET /auth/yo` con usuario sin `password_hash`, roles de la base y roles del token, y aplica la matriz RBAC: clientes y `GET /ventas` para VENDEDOR/ADMIN; mutaciones de catálogo y `/libros/{id}/movimientos` sólo ADMIN; `GET /ventas/{id}` y `/mis-ventas` sólo exigen autenticación y la propiedad la decide el servicio. Cierra el pendiente de C-07: `GET /clientes/{id}/ventas` responde 401 sin cookie, 403 a CLIENTE y 200 a VENDEDOR/ADMIN con el envoltorio paginado. Verificado: 105 pruebas pasan contra PostgreSQL 17 local; sin migraciones nuevas.
- **Scope**:
  - `requiere_rol(*roles)` en `app/core/dependencies.py`: consulta `asignacion_rol` **en cada petición**
    con la **misma sesión** del UoW (`revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`) y
    responde **403** si no hay ningún rol vigente de los exigidos. El claim `roles` del token **no** se usa
    para decidir (`RN-04`).
  - `GET /auth/yo` → 200 con el usuario (sin `password_hash`), sus **roles vigentes leídos de la base** y
    los **roles que dice el token**, para que la diferencia se vea.
  - `get_usuario_actual` y `requiere_rol` comparten la sesión del UoW: una sola conexión por petición
    autenticada.
  - Regla dura 401/403: 401 lo decide sólo `get_usuario_actual`; 403 lo deciden el rol, el cambio
    pendiente y la propiedad del recurso.
- **Dependencias**: `C-03`, `C-11`
- **Governance**: **CRÍTICO** — autorización es 12 % y `RN-04` es la regla que la consigna usa para
  distinguir «leer del token» de «leer de la base»; un atajo acá invalida C-07 entero.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §6: «`requiere_rol` consulta `asignacion_rol` en **cada** petición y no confía en el claim `roles`»;
    revocar quita el permiso a una sesión abierta y `vence_en <= now()` no otorga permiso.
  - §5: `GET /auth/yo` devuelve usuario + roles vigentes + roles del token.
  - §7: «Las dependencias de usuario actual y de rol usan **la misma sesión** que el UoW».
  - §10, C-06 y C-07 (en lo que no depende de la administración de roles).
  - Reglas: `RN-04`; `DD-02`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 3 (autorización de una petición autenticada)
  - `knowledge-base/03_actores_y_roles.md` — §RBAC, §401 vs 403, §Los roles viven en su propia tabla
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-04, §RN-14
  - `knowledge-base/06_funcionalidades.md` — US-004

### [C-14] cambio-password-grupos-de-rutas

- **Estado**: `[x]` cerrado — implementado y verificado contra PostgreSQL 17 real (172 passed / 0 errors vs baseline 151/0); dos grupos de rutas en main.py, control de cambio obligatorio, cambio de password sin rotar cookie, EventoSeguridadRepository (2026-11-06)
- **Scope**:
  - `main.py` con **dos grupos de rutas**: abierto (`/health`, `/auth`, catálogo público) y protegido
    (todo lo demás), con el control del cambio obligatorio montado **una sola vez** a nivel del router
    protegido. `GET /auth/yo` y `POST /auth/cambiar-password` viven en el grupo abierto **pero exigen
    sesión** (`RN-06`).
  - Con `debe_cambiar_password = true`: toda ruta del grupo protegido → **403**; las de `/auth` y las
    públicas siguen funcionando.
  - `POST /auth/cambiar-password`: contraseña actual + nueva (≤ 72 bytes cada una → 422); **401** si la
    actual no coincide (no escribe `intento_acceso`, no es un login); hash nuevo **fuera** de la
    transacción; en un solo UoW: `password_hash`, `debe_cambiar_password = false` y la línea de
    `evento_seguridad` con `actor = email` (`RN-16`).
  - **No** emite token nuevo y **no** rota la cookie: la misma cookie sigue entrando al grupo protegido
    con 200 (`IN-03`, `DD-07`). El bloqueo se libera porque el estado vive en la base.
  - El módulo `usuarios` suma su `EventoSeguridadRepository` (con `add`/listado paginado) para que `C-15`
    lo reutilice.
- **Dependencias**: `C-13`
- **Governance**: **CRÍTICO** — acá se juega C-09 y una de las trampas más grandes del parcial: rotar la
  cookie **hace fallar** el caso y contradice el PDF.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §1: «`main.py` con `lifespan` y **dos** grupos de rutas (abierto / protegido)».
  - §5: «`POST /auth/cambiar-password` **no** emite token nuevo ni invalida la cookie anterior, y deja
    `debe_cambiar_password = false`»; «Con `debe_cambiar_password = true` todo el grupo protegido da 403».
  - §7: «Los eventos de seguridad (RN-16) se escriben en la misma transacción del cambio».
  - §10, C-09 completo.
  - Reglas: `RN-06`, `RN-16`; `IN-03`, `DD-06`, `DD-07`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 4 (cambio de contraseña) y su recuadro «lo que NO pasa»
  - `knowledge-base/03_actores_y_roles.md` — §Dos grupos de rutas, un solo control
  - `knowledge-base/10_preguntas_abiertas.md` — §1, IN-03 e IN-06
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-06, §RN-16

### [C-15] admin-usuarios-roles-eventos

- **Estado**: `[ ]` pendiente
- **Scope**:
  - `POST /usuarios` (ADMIN) → **201**: alta de personal con contraseña provisoria (hash antes de la
    transacción), `debe_cambiar_password = true`, rol inicial ADMIN o VENDEDOR (`SU-02`) y línea de
    `evento_seguridad` en el **mismo** UoW; 409 correo repetido; 422 campos de más.
  - `POST /usuarios/{id}/roles` → **201**: `vence_en` opcional, **con zona** y en el **futuro**; en el
    pasado o sin zona → **422** (no 409); segunda asignación **abierta** del mismo rol → **409** (índice
    parcial de `RN-03`); usuario inexistente → 404; `otorgada_por` = admin que otorga.
  - `DELETE /usuarios/{id}/roles/{rol}` → **200**: escribe `revocada_en`, **la fila no se borra nunca**.
    Reasignar un rol vencido **cierra la fila anterior y abre una nueva** en la misma transacción.
  - `RN-05` en el servicio: revocar el propio ADMIN → **409**; revocar el **último** ADMIN vigente →
    **409**, aunque lo haga otro administrador.
  - `GET /usuarios/{id}/roles` → 200 con todo el historial (vigentes, vencidas y revocadas);
    `GET /eventos` (page, size) → 200 con el envoltorio.
  - Cada operación deja su línea de auditoría en la misma transacción (`RN-16`).
- **Dependencias**: `C-13`, `C-14`
- **Governance**: **ALTO** — `RN-05` y `RN-16` son reglas de negocio con caso propio (C-07 y C-08) y el
  índice parcial es el garante de `RN-03`; el riesgo es alto, pero está acotado a administración.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §6: revocar quita el permiso a una sesión abierta; vencimiento pasado o sin zona → **422**; reasignar
    cierra la fila anterior y la revocada **nunca se borra**; un ADMIN no se revoca su propio ADMIN y el
    sistema nunca queda sin administradores → **409**.
  - §7: eventos en la misma transacción del cambio (forzar rollback → no queda línea).
  - §10, C-07 y C-08 completos.
  - Reglas: `RN-03`, `RN-05`, `RN-16`; `SU-02`, `SU-12`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 9 (revocar con la sesión abierta) y Flujo 10 (asignar con vigencia)
  - `knowledge-base/03_actores_y_roles.md` — §Estados de una fila de `asignacion_rol`, §RBAC
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-03, §RN-05, §RN-16
  - `knowledge-base/06_funcionalidades.md` — US-010…US-016

---

## FASE 7 — Venta transaccional

> El corazón del capítulo 6: cuatro clases de escritura, una sola transacción, y el aviso que sale
> después de la respuesta. Acá se juntan `RN-09`, `RN-10` y `RN-11`.

### [C-16] venta-transaccional

- **Estado**: `[x]` cerrado — implementado y verificado contra PostgreSQL 17 real (325 passed / 0 errors vs 264 del padre, **+61**, no 21); `POST /ventas` atómico con stock, renglones, movimientos y `BackgroundTasks` (2026-11-07). Evidencia y hardening completados por el change correctivo `c-16-fix-venta-transaccional` (2026-11-07): cliente o libro inexistente → **409** (no 422/404), `parcial/test/ventas.http` presente y tareas archivadas reconciliadas. El commit `f2b6b89` no se reescribe.
- **Nota de seguimiento (2026-11-07)**: el change correctivo `c-16-fix-venta-transaccional` (23/23 tareas, **no** es un número nuevo del roadmap) quedó archivado como `2026-11-07-c-16-fix-venta-transaccional`. Corrigió el contrato estricto de `POST /ventas` (`precio`/`total`/`fecha` y enteros fuera de rango → `422`), la traducción de `DataError`/`DBAPIError` a `422` genérico, el orden de verificación 401 → 403 → 409 → 422, y reforzó el invariante de stock y la evidencia de pruebas. Caveat honesto: en el archivo original de C-16 la tarea 5.6 permanece `[ ]` de forma deliberada (24/25), porque los movimientos son append-only y no permiten borrar las filas creadas por las pruebas; no se marca como hecha.
- **Scope**:
  - `VentaCreate` con **sólo** `cliente_id` y `renglones: [{libro_id, cantidad}]`, `extra="forbid"`:
    mandar `precio`, `total` o `fecha` → **422**; cero renglones o `libro_id` repetido → **422**.
  - `VentasUnitOfWork` que compone ventas, renglones, libros y clientes con **la misma** sesión; el router
    lo construye, el servicio lo abre (`CV-01`).
  - Un solo `async with`: cliente existente (si no, 409) → libros existentes y **no dados de baja** (409)
    → stock suficiente por renglón (409) → venta con `total` = Σ(cantidad × precio) → copia de
    `precio_unitario` → descuento de stock con el **punto único** de `C-08`, un movimiento negativo por
    renglón con `usuario_id` del vendedor.
  - Si un libro no alcanza, **no queda ninguna** de esas escrituras (ni venta, ni renglones, ni
    descuentos, ni movimientos): la garantía es el rollback, no el chequeo.
  - `requiere_rol('VENDEDOR','ADMIN')`: un CLIENTE → 403; sin sesión → 401.
  - `BackgroundTasks`: después del commit, `add_task(avisar_comprobante, venta.id)` con
    `await asyncio.sleep(0.5)` y un log que **se vea con el arranque normal de uvicorn**.
- **Dependencias**: `C-08`, `C-10`, `C-13`
- **Governance**: **CRÍTICO** — `RN-10` es la regla más riesgosa del parcial: un descuento parcial deja el
  invariante roto y hace fallar C-10, C-11 y C-12 a la vez; además es el 16 % de repositorios/UoW.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §7: «Registrar una venta escribe venta + renglones + descuento de stock + un movimiento por renglón
    en **un** `async with uow`».
  - §8: cuerpo con sólo `cliente_id` y `renglones`; ≥ 1 renglón y sin repetidos; precio copiado y total
    calculado; 409 sin ninguna escritura si un libro no alcanza; cliente/libro inexistente o libro dado
    de baja → 409.
  - §10: C-10 (201, precios, total, stock, movimientos y aviso después de la respuesta), C-11 (409 y el
    invariante en 0 filas) y C-12 (los tres 409), más el ítem de `BackgroundTasks`.
  - §4: la query del invariante da 0 filas después de cada venta.
  - Reglas: `RN-09`, `RN-10`, `RN-11`, `RN-13`, `RN-15`; `DD-11`, `DD-13`.
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` — Flujo 5 (registrar una venta), completo
  - `knowledge-base/05_reglas_de_negocio.md` — §RN-09, §RN-10, §RN-11
  - `knowledge-base/08_arquitectura_propuesta.md` — §El Unit of Work, §`BackgroundTasks`
  - `knowledge-base/06_funcionalidades.md` — US-040, US-042

---

## FASE 8 — Datos iniciales

### [C-17] seed-libreria

- **Estado**: `[ ]` pendiente
- **Scope**:
  - `seed.py` en la raíz de `parcial/` que **vacía** y carga: 5 usuarios (`admin`, `admin2`, `vendedor`,
    `ana`, `nuevo` con cambio pendiente) con sus roles, 3 editoriales, 3 géneros, 6 autores y los 5 libros
    con stock 10/5/8/3/1.
  - Clientes: Lucía Fernández (con perfil, sin usuario), Tomás Ríos (sin usuario) y Ana Paz (con
    `usuario_id` → `ana@example.com`).
  - Venta 1 de Lucía **registrada por `vendedor@example.com`**: 1 Rayuela + 2 Ficciones = **69000.00**;
    un movimiento «Stock inicial» por libro (Rayuela y Ficciones con **11** y **10**) y las salidas
    **−1** y **−2** de la venta.
  - Una línea de `evento_seguridad` con `actor = 'SISTEMA'`: «Carga de los datos iniciales».
  - Vaciar con `TRUNCATE ... RESTART IDENTITY CASCADE`: un `DELETE` sobre `movimiento_stock` lo rechaza el
    disparador de `RN-12`.
  - Idempotente (`CV-11`): correrlo dos veces deja el mismo estado; corre **después** de
    `alembic upgrade head`; al terminar, `libro.stock = SUM(movimiento_stock.cantidad)` en los **cinco**
    libros.
- **Dependencias**: `C-09`, `C-15`, `C-16`
- **Governance**: **ALTO** — es el gate de los casos C: los `.http` asumen ids, totales y stocks del
  seed; un dato distinto hace fallar casos que funcionan.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §8, «Datos iniciales (`seed.py`)»: los **cuatro** ítems (usuarios y roles; editoriales, géneros,
    autores y libros con stock 10/5/8/3/1; los tres clientes; la venta 1, los movimientos y la línea
    `SISTEMA`; idempotencia).
  - §4: la query del invariante da 0 filas tras el seed.
  - §1: `seed.py` en la raíz y ejecutable.
  - Reglas: `RN-11`, `RN-12`; `CV-11`.
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` — §Seed data inicial (tablas de usuarios, catálogo, clientes, ventas y la verificación del invariante)
  - `knowledge-base/07_flujos_principales.md` — §Resumen de fronteras transaccionales
  - `knowledge-base/10_preguntas_abiertas.md` — §1, IN-07
  - `knowledge-base/09_decisiones_y_supuestos.md` — SU-04, SU-07

---

## FASE 9 — Casos de prueba y evidencia

> Lo que la corrección ejecuta. `test/` es lo exigido por la consigna; `tests/` es red de seguridad
> propia y va marcado como tal.

### [C-18] casos-c-http-y-solo-agregado

- **Estado**: `[ ]` pendiente
- **Scope**:
  - `test/` con un `.http` por módulo que cubre **C-01…C-16**, cada uno con la respuesta esperada escrita
    en un comentario, y todos corridos con REST Client **después** de `python seed.py`.
  - Dos sesiones simultáneas en el mismo archivo para C-07: cada login con `# @name` y los pedidos de esa
    sesión con `# @no-cookie-jar` y `Cookie: {{loginAdmin.response.headers.Set-Cookie}}`.
  - `test/solo_agregado.sql` con el `UPDATE` y el `DELETE` sobre `movimiento_stock` que el disparador
    rechaza (C-14), corrido con `psql -f`.
  - Caso del aviso: `uvicorn main:app` (sin configuración extra de logging), registrar una venta y
    comprobar que el mensaje del comprobante aparece **después** de la línea de la respuesta (C-10).
  - Cobertura explícita de cada resultado esperado: 422 de C-01 sin ejecutar el handler; 201/409 de C-02
    sin filas sueltas; 401 de C-03 con `Authorization: Bearer`; mismo cuerpo y tiempo de C-04; 429 +
    `Retry-After` de C-05 con los cinco fallos en la tabla; 401/403 y lo propio de C-06; revocación y
    vencimientos de C-07; 409 de C-08; 403 y misma cookie de C-09; totales, stock y movimientos de C-10;
    409 y 0 filas de C-11; los tres 409 de C-12; baja, re-alta y venta vieja de C-13; paginación,
    `' OR '1'='1` y PATCH de C-16.
- **Dependencias**: `C-12`, `C-14`, `C-17`
- **Governance**: **ALTO** — es la evidencia que se corrige caso por caso y el insumo de la carpeta
  `evidencia/`; un `.http` sin la respuesta esperada en el comentario no demuestra nada.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §10: **todos** los ítems, de «Hay un `.http` por caso `C-NN`…» hasta el ítem de `BackgroundTasks`.
  - §1: `test/` con los `.http` y `solo_agregado.sql`.
  - §12 (parcial): la captura de `psql` de C-14 y la de C-15 se producen acá y se archivan en `C-19`.
  - Reglas: cada caso cita su `RN` en el comentario.
- **Leer antes**:
  - `docs/CHECKLIST_ENTREGA.md` — §10 completo y §8 (resultados esperados por caso)
  - `docs/Parcial_Cap1a6_Consigna.pdf` — p. 21-22 (tabla de casos C) y el recuadro «Varias sesiones a la vez»
  - `knowledge-base/08_arquitectura_propuesta.md` — §Estrategia de pruebas
  - `knowledge-base/07_flujos_principales.md` — los 10 flujos, para saber qué escribir en cada caso

### [C-19] suite-pytest-y-evidencia

- **Estado**: `[ ]` pendiente
- **Scope**:
  - Suite `tests/` con **sólo** pytest (`CV-04`), contra PostgreSQL real y nunca SQLite (`CV-12`),
    comparando **status + body** y no `model_dump()`: al menos registro, login y 429, roles y revocación,
    venta con rollback, invariante del stock y baja lógica. Marcada `(RD-01)`: **no está en la consigna**.
  - `parcial/evidencia/`: captura de consola de C-15 (consultas del detalle de una venta con 2 y con 4
    renglones, con `SQL_ECHO=true`) y captura de `psql` de C-14.
  - `pytest -q` verde y verificación de que en `tests/` no quedan `.http` ni `.sql` sueltos.
- **Dependencias**: `C-18`
- **Governance**: **BAJO** — no es requisito corregible (la consigna sólo pide `test/`), pero la evidencia
  que produce sí entra al `.zip`, y por eso no se puede omitir.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §10, último ítem: «`pytest` pasa completo contra PostgreSQL real (nunca SQLite), comparando status +
    body».
  - §1: «`tests/` tiene **sólo** pytest, sin `.http` ni `.sql` sueltos».
  - §12: `parcial/evidencia/` con la captura de C-15 y la de `psql` de C-14.
  - Convenciones: `CV-04`, `CV-12`; `RD-01`.
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` — §Estrategia de pruebas
  - `docs/CHECKLIST_ENTREGA.md` — §10 (último ítem) y §12
  - `knowledge-base/05_reglas_de_negocio.md` — §Convenciones de ingeniería (`CV-04`, `CV-12`), §Reglas de diseño propias (`RD-01`)
  - `knowledge-base/04_modelo_de_datos.md` — §movimiento_stock (invariante a testear)

---

## FASE 10 — Despliegue (vía paralela)

> 18 % de la nota y **otro proyecto**: se empaqueta el TP cap. 1-4 *tal como se entregó*. Su lógica no se
> toca: sólo se le agregan `Dockerfile` y `.dockerignore`. Depende únicamente de `C-01`, así que arranca
> en `GATE 0` y corre en paralelo con todo el parcial.

### [C-20] imagen-docker-tp-cap1a4

- **Estado**: `[ ]` pendiente
- **Scope**:
  - `despliegue/Dockerfile` desde `python:3.12-alpine`: `COPY requirements.txt` + `pip install
    --no-cache-dir -r requirements.txt` **antes** de copiar el código; usuario sin privilegios creado con
    `addgroup`/`adduser` y activado con `USER` (nunca root); `EXPOSE 8000`.
  - `CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]`: si la
    base no responde, el contenedor termina con error.
  - `HEALTHCHECK` con `wget -qO- http://127.0.0.1:8000/health/ready || exit 1` — **`127.0.0.1`, nunca
    `localhost`** (en Alpine `wget` resuelve `localhost` a `::1` y uvicorn escucha IPv4).
  - `despliegue/.dockerignore` con `.env`, `.venv/`, `.git/`, `__pycache__/` y el resto de la higiene.
  - `despliegue/env.example` con la **forma** de `DATABASE_URL` (driver `postgresql+asyncpg`) y
    `SQL_ECHO`, sin valores reales.
  - Corregir y **anotar** en `DEPLOY.md` cualquier defecto propio del TP que impida arrancar en el
    contenedor (`D-05`: un default de `DATABASE_URL` en el código; la ruta de salud del TP).
  - Build desde cero (`--no-cache` una vez) y evidencia de **D-01**, **D-06** y **D-07**.
- **Dependencias**: `C-01`
- **Governance**: **ALTO** — 11 % de la rúbrica y tres casos D que se demuestran sobre la imagen; el
  `HEALTHCHECK` con `localhost` es el defecto que deja el contenedor `unhealthy` sin que nada parezca
  roto.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §11: «El `Dockerfile` parte de `python:3.12-alpine` y esa base mide menos de 100 MB» (D-01); «Copia e
    instala `requirements.txt` con `--no-cache-dir` **antes** de copiar el código, y corre con usuario sin
    privilegios»; «`.dockerignore` excluye `.env`, `.venv`, `.git` y `__pycache__`, y ni la dirección de
    la base ni su contraseña están en el `Dockerfile` ni en la imagen» (D-06); «Al arrancar aplica
    `alembic upgrade head` y luego levanta uvicorn en `--host 0.0.0.0`…»; «`HEALTHCHECK` contra
    `GET /health/ready` usando `127.0.0.1`».
  - §13, fila «Contenedor: la imagen» (11 %), con D-01, D-06 y D-07.
  - Reglas: `DD-15`; el despliegue **no** lleva nada del parcial.
- **Leer antes**:
  - `knowledge-base/11_despliegue_y_devops.md` — §La imagen, §`Dockerfile` de referencia, §`.dockerignore`, §Las dos trampas
  - `knowledge-base/09_decisiones_y_supuestos.md` — DD-15
  - `knowledge-base/02_descripcion_general.md` — stack (versiones que instala el `requirements.txt`)
  - `knowledge-base/10_preguntas_abiertas.md` — §1, IN-05 e IN-04

### [C-21] despliegue-vps-deploy-md

- **Estado**: `[ ]` pendiente
- **Scope**:
  - Construir la imagen **en el servidor** (o construirla afuera y llevarla) y documentar la elección;
    correr con
    `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file <archivo> libreria`,
    **sin Docker Compose**.
  - `--env-file` en el servidor, fuera del repo y de la imagen, con `DATABASE_URL` (sin `localhost`; si la
    base está en el host Linux, `host.docker.internal` + `--add-host=host.docker.internal:host-gateway`) y
    `SQL_ECHO=false`.
  - Cargar los datos iniciales **dentro del contenedor** con el comando que indica el README del TP
    (`docker exec libreria …`) y verificar desde **afuera**: `/health/ready` 200, `/libros/` 200 con
    datos, `POST /ventas/` 201 con precios copiados y total.
  - `despliegue/DEPLOY.md` con: URL pública, día y hora, `docker build` y `docker run` completos (con el
    **nombre** del archivo de variables y **sin su contenido**), cambios al TP y procedimiento de
    actualización (build → `docker rm -f` → `docker run`; los datos viven en la base del servidor).
  - `despliegue/evidencia/` con **D-01…D-08**, un archivo por caso con comando y salida; incluye D-04
    (`rm -f` + el mismo `run` → vuelve `healthy`, los datos siguen, las migraciones no se repiten) y D-08
    (el aviso aparece en `docker logs` **después** de la línea de la respuesta).
  - Sostener el despliegue en línea hasta que se publiquen las notas.
- **Dependencias**: `C-20`
- **Governance**: **ALTO** — 7 % que se corrige **sobre un sistema en línea** y con un recurso externo
  (credenciales y base de la cátedra); si el servidor no está accesible, sólo suman `DEPLOY.md` y la
  evidencia.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §11: «Se corre con `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped
    --env-file <archivo> libreria`, sin Docker Compose»; «La `DATABASE_URL` del `--env-file` no usa
    `localhost`…»; «Al TP sólo se le agregaron `Dockerfile` y `.dockerignore`…»; «**D-01…D-08** corridos,
    con comando y salida guardados uno por archivo en `despliegue/evidencia/`»; «`DEPLOY.md` tiene URL
    pública, día y hora, `docker build` y `docker run` completos…»; «La URL pública responde
    `/health/ready` 200, `/libros/` 200 con datos y `POST /ventas/` 201…»; D-04 y D-08; «El despliegue
    queda en línea hasta que se publiquen las notas».
  - §13, fila «Despliegue en el VPS» (7 %), con D-02, D-03, D-04, D-05 y D-08.
  - Reglas: `DD-15`; `RN-10` en el `POST /ventas/` verificado desde afuera.
- **Leer antes**:
  - `knowledge-base/11_despliegue_y_devops.md` — §Cómo se corre, §Despliegue en el VPS, §`DEPLOY.md`, §Casos D
  - `knowledge-base/11_despliegue_y_devops.md` — §El `.zip` de entrega (qué carpeta va en qué proyecto)
  - `knowledge-base/10_preguntas_abiertas.md` — §1, IN-04
  - `knowledge-base/06_funcionalidades.md` — US-061, US-062

---

## FASE 11 — Entrega

### [C-22] entrega-zip-y-autoevaluacion

- **Estado**: `[ ]` pendiente
- **Scope**:
  - `parcial/README.md` con **nombres y apellidos** de los integrantes y los pasos desde cero: entorno
    virtual, dependencias, `.env` explicando **cómo generar la clave de firma**, `alembic upgrade head`,
    `python seed.py` y arranque del servidor.
  - Armar `Parcial_Cap1a6_<NombreDelGrupo>.zip` con **dos** carpetas (`parcial/` y `despliegue/`), cada
    una con su `evidencia/`; sin `.venv`, `__pycache__` ni `.env` en **ninguna** de las dos.
  - Correr `docs/CHECKLIST_ENTREGA.md` **completo** en una carpeta temporal limpia (Python 3.12,
    PostgreSQL 16, base vacía) y archivar la salida; registrar los ítems que no se pudieron correr.
  - Autoevaluación contra la rúbrica (§13) criterio por criterio, y revisión de las condiciones que anulan
    la corrección (levanta, esquema por Alembic, sin credenciales reales en repo/imagen/zip).
  - Revisar el historial de git por credenciales y que `git status` quede limpio antes de comprimir.
- **Dependencias**: `C-18`, `C-19`, `C-21`
- **Governance**: **CRÍTICO** — es la puerta de entrega: un `.zip` con `.env`, una sola carpeta o una
  credencial en el historial no se corrige hasta subsanarlo, sin importar cuánto del parcial esté bien.
- **Aceptación**: `docs/CHECKLIST_ENTREGA.md`
  - §12 **completo** (nombre del archivo, dos carpetas, contenido de `parcial/`, contenido de
    `despliegue/`, sin `.venv`/`__pycache__`/`.env`, README con integrantes y pasos, git limpio).
  - §13 **completo**: los 10 criterios de la rúbrica y el ítem de condiciones que anulan la corrección.
  - §0, §2 y §3 en lo que hace a credenciales y esquema, como reverificación final en carpeta limpia.
- **Leer antes**:
  - `docs/CHECKLIST_ENTREGA.md` — §12 y §13 completos, y el recuadro de cierre
  - `knowledge-base/11_despliegue_y_devops.md` — §El `.zip` de entrega, §README de `parcial/`
  - `knowledge-base/10_preguntas_abiertas.md` — §1, IN-04 (dos carpetas)
  - `docs/Parcial_Cap1a6_Consigna.pdf` — p. 23-24 (rúbrica y formato de entrega)

---

## Resumen

| Fase | Changes | Foco |
|---|---|---|
| 1 — Base y fundación | `C-01`, `C-02` | adoptar el TP cap. 1-4, Settings, lifespan, repositorios base y UoW |
| 2 — Esquema versionado | `C-03`, `C-04` | modelos, los dos índices parciales, migraciones 0003 y 0004 |
| 3 — Convenciones | `C-05` | `RN-15`, contratos, errores, paginación |
| 4 — Módulos heredados | `C-06`…`C-10` | seis capas, stock, baja lógica, lecturas sin N+1 |
| 5 — Autenticación | `C-11`, `C-12` | login, cookie, rate limit, anti-enumeración, auto-registro |
| 6 — Autorización | `C-13`…`C-15` | `RN-04`, `RN-05`, `RN-06`, `RN-16` |
| 7 — Venta transaccional | `C-16` | `RN-09`, `RN-10`, `RN-11` y `BackgroundTasks` |
| 8 — Datos iniciales | `C-17` | seed idempotente con el invariante intacto |
| 9 — Pruebas y evidencia | `C-18`, `C-19` | 16 casos C, `solo_agregado.sql`, pytest y `evidencia/` |
| 10 — Despliegue (paralelo) | `C-20`, `C-21` | imagen Alpine y TP cap. 1-4 en línea en el VPS |
| 11 — Entrega | `C-22` | `.zip` de dos carpetas y autoevaluación |
| **Total** | **22 changes** | **11 fases** |

**Camino crítico**: 11 changes —
`C-01 → C-02 → C-05 → C-11 → C-13 → C-14 → C-15 → C-17 → C-18 → C-19 → C-22`.

**Gates de paralelismo**: 10 (`GATE 0`…`GATE 9`), con dos forks grandes: `GATE 0` abre la vía de
despliegue y `GATE 4` abre catálogo, ventas y cambio de contraseña a la vez.

**Primer change recomendado**: `C-02` (core-repositorios-uow-paginacion) — **pendiente de proponer**. `C-01`
ya está cerrado y archivado.

Estado de `C-01`:

- **Cerrado y archivado** (`openspec/changes/archive/2026-11-05-c-01-baseline-tp-y-fundacion/`).
- Mitad **(A)** — grupos 1 a 6: implementada y verificada en `parcial/`.
- Mitad **(B)** — grupo 7: cerrada. El TP cap. 1-4 se implementó desde la consigna
  (`docs/TP_Cap1a4_Consigna (1).pdf`), se adoptó en `parcial/`, se copió intacto a `despliegue/`, las
  migraciones `0001`/`0002` se aplicaron y el baseline quedó documentado en
  `docs/BASELINE_TP_CAP1a4.md` (`SU-01`…`SU-09`).
- Columnas heredadas cerradas: `SU-01` (bigint identity), `SU-07` (sin `usuario_id`, `cliente_id` con
  `ON DELETE NO ACTION`), `SU-08` (`precio_unitario`), `SU-09` (revisiones y archivos).
- **Auditoría de verificación (2026-11-07)**: se reabrieron las 8 tareas que quedaron `[ ]` en el archivo
  C-01 y se corrieron contra PostgreSQL 17.11 real. Quedaron cerradas `1.4`, `3.3`, `3.4`, `3.5`, `4.4`,
  `5.3`, `6.5` y `6.4`; `pytest -q` → **413 passed**. La `6.4` se desbloqueó corrigiendo el import
  faltante de `app.modules.usuarios.models` en `parcial/seed.py`: el seed existente ejecuta `Seed OK` y es
  idempotente sobre una base temporal migrada. El seed funcional completo con usuarios/roles/venta/eventos
  sigue siendo alcance de `C-17` (seed-libreria). C-01 pasó de `29/37` a **`37/37`** en
  `openspec validate --archived --strict`. Detalle en
  `openspec/changes/archive/2026-11-05-c-01-baseline-tp-y-fundacion/tasks.md`.

Para continuar: `/opsx:propose c-02-core-repositorios-uow-paginacion` y luego `/opsx:apply`.



