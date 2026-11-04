# Parcial Cap. 1-6 — «la librería» — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/`, `CHANGES.md` y `.atl/skill-registry.md`.
> Si cambiás uno de esos tres, re-sincronizá ambos archivos (`AGENTS.md` y `CLAUDE.md` deben quedar idénticos).

---

## Stack Tecnológico

| Capa | Tecnología | Versión mínima |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Framework web | FastAPI (`async def` en todos los handlers) | 0.111 |
| Modelos de tabla | SQLModel | 0.0.24 |
| ORM | SQLAlchemy asincrónico | 2.0 |
| Driver | asyncpg (`postgresql+asyncpg`) | 0.30 |
| Base de datos | PostgreSQL | 16 |
| Migraciones | Alembic (plantilla asincrónica) | 1.13 |
| Configuración | pydantic-settings | 2.0 |
| Hash | bcrypt | 4.0 |
| Token | PyJWT | 2.8 |
| Servidor ASGI | uvicorn | vía `fastapi[standard]` |
| Contenedor | Docker | 20.10 |

Decisiones de stack fijadas por la consigna (no negociables): dinero en `NUMERIC`/`Decimal` (nunca `float`); fechas nuevas siempre `timestamptz`; esquema creado **solo** con Alembic (sin `create_all`); bcrypt siempre fuera del event loop; el token viaja **solo** en cookie.

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---|---|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, alcance, rúbrica |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura, API |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, rutas públicas, 401 vs 403 |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | ERD, columnas, CHECKs, índices parciales |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | `RN-01…RN-16` (consigna) · `CV-01…CV-14` (convención) · `RD-01…RD-03` (propia) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por épica |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E con fronteras de transacción |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Capas, UoW, Settings, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | `DD-01…DD-18`, `SU-01…SU-15` |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Conflictos y preguntas abiertas |
| [11_despliegue_y_devops.md](knowledge-base/11_despliegue_y_devops.md) | Docker, VPS, casos `D-01…D-08` |

Criterio de aceptación ejecutable: [docs/CHECKLIST_ENTREGA.md](docs/CHECKLIST_ENTREGA.md) (14 secciones, 136 ítems con comando y fuente).

`docs/_legacy/` contiene una plantilla heredada de **otro dominio**: no es criterio, no se usa.

---

## Skills Disponibles

| Agente | Rol | Skills que carga |
|---|---|---|
| **Backend Core** | FastAPI, SQLModel, UoW, migraciones | `fastapi-templates`, `python-design-patterns`, `postgresql-table-design` |
| **Auth y seguridad** | Login, cookie, RBAC, rate limiting | `auth-implementation-patterns`, `security-and-hardening` |
| **Datos y consultas** | Esquema, constraints, reportes, paginación | `postgresql-table-design`, `postgresql-optimization` |
| **Testing y evidencia** | Casos `C-01…C-16`, `test/solo_agregado.sql` | `python-testing-patterns`, `api-security-testing` |
| **Despliegue** | `C-20`/`C-21`: imagen, VPS, evidencia | *Ninguna instalada* → [11_despliegue_y_devops.md](knowledge-base/11_despliegue_y_devops.md) + documentación oficial |
| **Orquestación** | SDD/OPSX, KB, roadmap, registry | `openspec-*`, `active-orchestrator`, `skill-registry` |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde [.atl/skill-registry.md](.atl/skill-registry.md). Está **versionado en el repo**: regeneralo con `/active-orchestrator:registry` cuando instales o quites skills.

---

## Roadmap de Changes

El plan completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 22 changes en 11 fases, 10 gates de paralelismo.
- **Camino crítico** (11): `C-01 → C-02 → C-05 → C-11 → C-13 → C-14 → C-15 → C-17 → C-18 → C-19 → C-22`.
- **Primer change**: `C-01` (baseline-tp-y-fundacion).

Cada change trae su `Aceptación`: qué sección de `docs/CHECKLIST_ENTREGA.md` y qué `RN-xx` debe poder correrse al terminar. **Si el comando no se puede correr, el ítem no está cumplido.**

**Estado actual del repo**: no hay código todavía (`app/`, `tests/`, `migrations/` no existen). `C-01` necesita el baseline del TP de los capítulos 1-4 (catálogo, clientes, ventas), que **no está en el repo**; las tablas heredadas están marcadas en `04_modelo_de_datos.md` como *«heredado TP cap 1-4 — confirmar»*.

**Antes de cualquier `/opsx:propose`**: leé `CHANGES.md`, verificá que las dependencias del change estén en `[x]` y abrí los archivos de su sección **Leer antes**.

---

## Reglas Duras

> Las reglas globales se heredan y no se repiten acá: *design stage* en `~/.config/opencode/AGENTS.md`, y orquestación / governance / TDD / engram en la configuración del harness. Lo que sigue es **específico de este proyecto** y prevalece ante cualquier conflicto con la KB.

**Arquitectura y capas**
1. NUNCA construir el UoW en el servicio → lo construye el router y el servicio lo abre con `async with` (`CV-01`).
2. NUNCA `commit()` en un repositorio → solo `flush()`; confirma el `__aexit__` del UoW (`CV-02`).
3. NUNCA pasar la sesión a un servicio → recibe el UoW.
4. NUNCA precarga (`selectinload`) fuera de `repository.py` (`CV-03`).
5. NUNCA lógica de negocio en el router → solo HTTP, construcción del UoW y traducción de errores.

**Datos**
6. NUNCA `float` para dinero → `NUMERIC` en la base y `Decimal` en Python.
7. NUNCA fechas sin zona → `timestamptz`.
8. NUNCA `create_all` → el esquema nace solo de Alembic.
9. NUNCA editar una migración ya aplicada → migración nueva; la autogenerada se **lee** antes de aplicarla.
10. NUNCA una clave foránea sin índice.
11. NUNCA escribir `stock` directo → solo a través de `movimiento_stock` (`RN-11`, `RN-12`).

**Seguridad**
12. NUNCA un secreto con valor por defecto → `Settings` obligatorio, `env.example` sin punto, `.env` fuera del repo y del zip.
13. NUNCA token en el cuerpo ni leído de `Authorization` → solo cookie `access_token` HttpOnly.
14. NUNCA `bcrypt` dentro del event loop → `to_thread` + semáforo.
15. NUNCA autorizar con los roles del token → releer `asignacion_rol` vigente en cada petición (`RN-04`).

**Proceso**
16. NUNCA proponer un change con dependencias sin `[x]`, ni agregar reglas que no estén en la consigna (lo propio se marca `CV-xx`/`RD-xx`).
17. NUNCA hacer `commit` ni `push` sin pedido explícito → dejar los cambios en el working tree.
18. Commits en formato Conventional Commits, sin co-autoría de IA.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y "Leer antes"
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks cargando las skills     → respetando las 18 reglas duras
5. Correr la Aceptación del change               → ítems de docs/CHECKLIST_ENTREGA.md
6. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar todas las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, prevalecen las reglas duras; ante conflicto entre la KB y la consigna, prevalece la consigna.
