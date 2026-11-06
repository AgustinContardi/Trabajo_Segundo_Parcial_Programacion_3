# Limpieza de `despliegue/` — 2026-11-06

## Resumen

`despliegue/` no era una copia intacta del TP de los capítulos 1-4: era una
copia de `parcial/` (el proyecto del parcial, cap. 1-6) con el módulo
`usuarios/` borrado, pero aún conservaba conceptos de auth/seguridad del
parcial que no pertenecen al TP cap. 1-4.

La consigna del parcial (C-20 / C-21) exige desplegar el TP cap. 1-4 **tal
como se entregó**. Esta limpieza retira los conceptos ajenos para que
`despliegue/` represente únicamente el baseline de caps 1-4.

> **Nota de honestidad**: no se pudo comparar byte a byte contra el TP
> original entregado por el compañero (no está versionado en el repo: no hay
> carpeta `_incoming/`, ni `.zip`, ni rama). La limpieza se hizo sobre la copia
> existente retirando conceptos del parcial. Las migraciones `0001` y `0002`
> se conservaron **byte-idénticas** a las de `parcial/` y del baseline.

## Archivos tocados

| Archivo | Qué se quitó | Por qué |
|---|---|---|
| `despliegue/app/core/config.py` | Campos `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG` y la nota de contrato de `C-11` | Son de auth/autorización (C-11…C-15), no del TP cap. 1-4 |
| `despliegue/app/core/__init__.py` | Referencia `(C-02/C-11) seguridad` → `(C-02) capas` | `C-11` es del parcial |
| `despliegue/main.py` | `import bcrypt`, constante `HASH_DUMMY`, semáforo bcrypt y cómputo de `hash_ficticio` en el `lifespan`; referencias a `C-11`, `access_token`, `RN-08` en el docstring | `hash_ficticio` y bcrypt son del login (C-11) |
| `despliegue/app/modules/ventas/router.py` | Import `BackgroundTasks`, parámetro `background_tasks` y `background_tasks.add_task(service.aviso_comprobante, ...)` | `aviso_comprobante` es un concepto del parcial (notificación de comprobante) |
| `despliegue/app/modules/ventas/service.py` | `import asyncio` y función `aviso_comprobante()` | Misma razón |
| `despliegue/env.example` | Líneas `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG` | Variables de auth, no del TP cap. 1-4 |
| `despliegue/requirements.txt` | `bcrypt>=4.0` y `PyJWT>=2.8` | Dependencias de auth, no del TP cap. 1-4 |
| `despliegue/README.md` | Título «capítulos 1 a 6», referencia a «stock y acceso con roles», párrafo de `JWT_SECRET`, instrucción de correr en `parcial/`, nota de «aún no hay migraciones propias» | `despliegue/` es caps 1-4, tiene 2 migraciones, y corre desde `despliegue/` |

## Archivos NO tocados (por diseño)

- `despliegue/migrations/versions/0ba1752f7c23_0001_initial_tp_baseline.py` — byte-idéntica a `parcial/` (SHA256 `2CBD1D68…D537`).
- `despliegue/migrations/versions/5f67a857f685_0002_add_genero.py` — byte-idéntica a `parcial/` (SHA256 `DA8EEBBA…ADB82`).
- La lógica CRUD de todos los módulos (editoriales, géneros, autores, libros, clientes, ventas): no se renombró ruta ni contrato.
- `parcial/` — sin modificaciones.

## Verificación realizada

1. **grep de conceptos prohibidos** en `despliegue/` → 0 hits para `UnitOfWork`, `AsignacionRol`, `movimiento_stock`, `JWT_SECRET`, `BCRYPT`, `LOGIN_`, `hash_ficticio`, `access_token`, `evento_seguridad`, `aviso_comprobante`. Quedan 3 hits benignos: referencias a cambios `C-02`, `C-03`, `C-04` en comentarios/docstrings (no son conceptos de código).
2. **Migraciones** — 2 archivos, SHA256 idénticos a `parcial/`.
3. **Sintaxis** — `ast.parse` sobre todos los `.py`: OK.
4. **Import** — `python -c "import main; print('ok')"` → `ok` (sin `.env` requerido para importar).
5. **Alembic en base fresca** — `alembic upgrade head` aplica `0001` y `0002` y crea las 10 tablas del TP (`autor`, `cliente`, `editorial`, `libro`, `genero`, `libro_autor`, `perfil_cliente`, `renglon_venta`, `venta` + `alembic_version`).
6. **Arranque de la API** — uvicorn levanta, `/health/live` → `{"status":"ok"}`, `/health/ready` → `ok` (base conectada), `/editoriales/` responde sin error.

## Queda pendiente (no parte de esta limpieza)

- El TP original entregado por el compañero no está en el repo, así que no se pudo hacer la comparación byte a byte exigida por la tarea 7.3/7.5 de `C-01`.
- `despliegue/` no incluye semilla de datos (`seed.py` sí existe y se conserva, pero no se ejecutó aquí).
