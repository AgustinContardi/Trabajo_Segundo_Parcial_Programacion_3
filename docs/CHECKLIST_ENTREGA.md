# Checklist de entrega — Parcial «la librería» (capítulos 1 a 6)

> **Qué es.** Criterio de aceptación verificable, usable como *definition of done* de cada change. Cada ítem tiene la forma
> `afirmación — *verificar:* comando u observación — *fuente:* …`; si el comando escrito no se puede correr, el ítem no está cumplido.
>
> **Origen.** Adaptado del checklist de un TP anterior (otro dominio), archivado en `docs/_legacy/CHECKLIST_ANTES_DE_ENTREGAR_taller.md`
> y **no autoritativo**. Los **12 conflictos** resueltos a favor de la consigna (`docs/Parcial_Cap1a6_Consigna.pdf`) están documentados
> como IN-01…IN-12 en `knowledge-base/10_preguntas_abiertas.md`: dominio librería; **una** tabla de sólo agregado y no tres; cambiar la
> contraseña **no** rota la cookie; `.zip` con **dos** carpetas; `/health/live` + `/health/ready` y no `/health`; sin
> `password_cambiada_en` ni comparación de `iat`; seed de la librería; sólo los `CHECK` del PDF (`venta.total` sin `CHECK`); `test/` es
> lo corregible y `tests/` es interno (RD-01); secuencia de errores como convención (CV-08); nombres de variables de entorno del
> checklist (CV-09); `env.example` **sin** punto inicial.
>
> **Cómo se corre.** Carpeta limpia, Python 3.12, PostgreSQL 16, dentro de `parcial/`: `python -m venv .venv` → `pip install -r
> requirements.txt` → `.env` desde `env.example` → `alembic upgrade head` sobre base vacía → `python seed.py` → `uvicorn main:app
> --reload`. Los `.http` se corren con REST Client **después de cada** `python seed.py`. §11–§12 se corren en `despliegue/` y contra el
> VPS. `(heredado)` = columna del TP cap. 1-4 que el PDF no reimprime: confirmar contra el repo antes de dar el ítem por bueno.
## 0. Reglas que no se negocian

- [ ] Los paths son exactamente los de la consigna, sin shims ni alias — *verificar:* `ls app/core app/modules/*` contra la tabla de §1 — *fuente:* CV-03, consigna p.8-9.
- [ ] Ninguna credencial en `alembic.ini`, `env.example`, README, código, imagen ni historial de git — *verificar:* `git log -p | Select-String -Pattern 'password|secret|DATABASE_URL'` — *fuente:* consigna p.4, p.20, p.24.
- [ ] El **router construye** el UoW y se lo pasa al servicio; el **servicio lo abre** con `async with`; **sólo `__aexit__` confirma** — *verificar:* `grep -n "async with" app/modules/*/router.py` y `grep -n "UnitOfWork(" app/modules/*/service.py` (ambos vacíos) — *fuente:* CV-01, consigna p.12.
- [ ] Toda precarga (`selectinload`) vive en `repository.py`, nunca en modelos, servicios ni routers — *verificar:* `grep -rn "selectinload" app/ | grep -v repository.py` (vacío) — *fuente:* CV-02, consigna p.12-13.
- [ ] Ninguna regla de negocio fuera de la consigna: cada validación del servicio cita una `RN-xx` — *verificar:* revisar los `service.py` contra `05_reglas_de_negocio.md` — *fuente:* consigna p.6-8.
- [ ] Ninguna respuesta incluye `password_hash` — *verificar:* `grep -rn "password_hash" app/modules/*/schemas.py` (vacío) — *fuente:* CV-07, consigna p.10.
## 1. Estructura

- [ ] `main.py` con `lifespan` y **dos** grupos de rutas (abierto / protegido) — *verificar:* `grep -n "include_router" main.py` (dos bloques) — *fuente:* consigna p.8, p.11 (RN-06).
- [ ] `seed.py` en la raíz de `parcial/` y ejecutable — *verificar:* `python seed.py` sin error tras `alembic upgrade head` — *fuente:* consigna p.8, p.19.
- [ ] `app/core/` con `config.py`, `database.py`, `security.py`, `dependencies.py`, `repository.py`, `paginacion.py`, `unit_of_work.py` — *verificar:* `ls app/core` — *fuente:* CV-03, consigna p.8.
- [ ] `app/modules/{health,usuarios,clientes,editoriales,generos,autores,libros,ventas}/`, y cada uno (salvo `health`) con las seis capas `models.py`, `schemas.py`, `repository.py`, `unit_of_work.py`, `service.py`, `router.py` — *verificar:* `for m in app/modules/*; do ls $m; done` — *fuente:* CV-03, consigna p.8-9.
- [ ] `health` sólo tiene `router.py` — *verificar:* `ls app/modules/health` — *fuente:* CV-13, consigna p.9.
- [ ] Entidades en su módulo obligatorio: `AsignacionRol`/`IntentoAcceso`/`EventoSeguridad` en `usuarios`, `MovimientoStock` y `LibroAutor` en `libros`, `PerfilCliente` en `clientes`, `RenglonVenta` en `ventas` — *verificar:* `grep -rn "class \(AsignacionRol\|IntentoAcceso\|EventoSeguridad\|MovimientoStock\|LibroAutor\|PerfilCliente\|RenglonVenta\)" app/modules` — *fuente:* consigna p.9.
- [ ] `migrations/` con `env.py` y `versions/`, y `alembic history` lista las cuatro versiones — *verificar:* `ls migrations/versions; alembic history` — *fuente:* consigna p.9-10.
- [ ] `test/` tiene los `.http` de los casos C y `solo_agregado.sql`; `tests/` tiene **sólo** pytest, sin `.http` ni `.sql` sueltos — *verificar:* `ls test tests` — *fuente:* CV-04, RD-01, consigna p.9, p.21.
- [ ] `env.example` (sin punto inicial) y `.gitignore` con `.env` — *verificar:* `ls -a | Select-String env` — *fuente:* CV-05, consigna p.4, p.24.
- [ ] La aplicación **no** usa `create_all` — *verificar:* `grep -rn "create_all" . --include=*.py` (vacío) — *fuente:* CV-14, consigna p.10, p.20.
## 2. Configuración

- [ ] `Settings` de `pydantic-settings` con `POSTGRES_USER/PASSWORD/DB/HOST/PORT`, `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`, `POOL_SIZE`, `SQL_ECHO` — *verificar:* `open app/core/config.py` — *fuente:* CV-09, consigna p.4.
- [ ] La URL de la base se arma con `@computed_field` y driver `postgresql+asyncpg` — *verificar:* `python -c "from app.core.config import Settings; print(Settings().database_url)"` — *fuente:* consigna p.4, p.9.
- [ ] `POSTGRES_PASSWORD` y `JWT_SECRET` sin default: la app **no arranca** si faltan — *verificar:* renombrar `.env` y correr `uvicorn main:app` → error de validación; restaurar — *fuente:* consigna p.4.
- [ ] Motor y `sessionmaker` se crean **sólo** en el `lifespan`, guardados en `app.state` (`pool_size=POOL_SIZE`, `expire_on_commit=False`), y `get_session` toma la fábrica de `app.state`, entrega una sesión por petición y la cierra — *verificar:* `grep -n "create_async_engine\|async_sessionmaker\|app.state" app/core/database.py` y leer `get_session` — *fuente:* consigna p.9.
- [ ] El `lifespan` calcula **una vez** el hash ficticio del login y al apagar hace `engine.dispose()` — *verificar:* `grep -n "hash_ficticio\|dispose" main.py` — *fuente:* consigna p.9, p.11 (RN-08).
- [ ] `alembic.ini` sin `sqlalchemy.url` con credenciales (`migrations/env.py` lee de `Settings`), y `.env` existe en la máquina pero **no** está versionado ni entra al zip — *verificar:* `grep -n "sqlalchemy.url" alembic.ini migrations/env.py`, `git check-ignore .env` y `git ls-files | Select-String "^\.env$"` (vacío) — *fuente:* CV-06, consigna p.4, p.20, p.24.
## 3. Migraciones

- [ ] Hay **exactamente cuatro** versiones: las dos del TP + una autogenerada + una escrita a mano — *verificar:* `ls migrations/versions` — *fuente:* consigna p.2, p.10.
- [ ] La tercera se generó con `--autogenerate` y trae las 4 tablas de acceso, `movimiento_stock`, `cliente.usuario_id`, `libro.borrado_en` y los **dos** índices únicos parciales — *verificar:* leer la migración y contar las 8 piezas — *fuente:* consigna p.10.
- [ ] Cada migración nueva lleva un comentario que dice que se leyó antes de aplicarla y qué se corrigió a mano — *verificar:* `head -30 migrations/versions/0003_*.py migrations/versions/0004_*.py` — *fuente:* consigna p.10.
- [ ] La cuarta es manual y crea **función + disparador** de sólo agregado sobre `movimiento_stock`, con `downgrade` que borra los dos — *verificar:* `grep -n "CREATE TRIGGER\|DROP TRIGGER\|DROP FUNCTION" migrations/versions/0004_*.py` — *fuente:* RN-12, consigna p.10, p.12.
- [ ] `upgrade head` → `downgrade base` → `upgrade head` sobre base vacía sin error, y `alembic check` no detecta diferencias entre modelos y esquema — *verificar:* `alembic upgrade head; alembic downgrade base; alembic upgrade head; alembic check` — *fuente:* CV-10, consigna p.10, rúbrica p.23.
- [ ] Toda FK nueva tiene índice, las fechas nuevas son `timestamptz` y el dinero es `NUMERIC` — *verificar:* `\d asignacion_rol`, `\d movimiento_stock`, `\d+ libro`, `\d+ venta` en `psql` — *fuente:* consigna p.6.
## 4. Modelo de datos

- [ ] Nombres de tablas y columnas **exactamente** los impresos; ninguna renombrada ni faltante — *verificar:* `\dt` y `\d <tabla>` contra la tabla de consigna p.5-6 — *fuente:* consigna p.4.
- [ ] `usuario` tiene `id, email, nombre, password_hash, activo, debe_cambiar_password`, con `email` **UNIQUE** y **ninguna columna `rol`** — *verificar:* `\d usuario` y `grep -rn "rol" app/modules/usuarios/models.py` — *fuente:* consigna p.5-6, RN-01.
- [ ] `asignacion_rol` tiene las **8** columnas (`id, usuario_id, rol, desde, vence_en, revocada_en, otorgada_por`) y `CHECK (rol IN ('ADMIN','VENDEDOR','CLIENTE'))` — *verificar:* `\d asignacion_rol` — *fuente:* consigna p.5.
- [ ] `asignacion_rol` tiene índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` — *verificar:* `\d asignacion_rol` y `grep -n "postgresql_where" app/modules/usuarios/models.py` — *fuente:* RN-03, consigna p.5.
- [ ] `libro.borrado_en` existe (`timestamptz`, nulo), `isbn` **ya no** es `UNIQUE` común sino índice único parcial `(isbn) WHERE borrado_en IS NULL`, y se conservan `CHECK (precio > 0)` y `CHECK (stock >= 0)` — *verificar:* `\d libro` (sin `libro_isbn_key`) — *fuente:* RN-01, RN-13, consigna p.5-6.
- [ ] `cliente.usuario_id` existe, admite nulo y es `UNIQUE` — *verificar:* `\d cliente` — *fuente:* consigna p.2, p.5.
- [ ] `Cliente.usuario` devuelve un objeto y no una lista, con la navegación declarada en los dos extremos — *verificar:* leer las relaciones de `Cliente` y `Usuario` en `models.py` — *fuente:* consigna p.6, p.10.
- [ ] `movimiento_stock` tiene las **7** columnas (`id, libro_id, venta_id, usuario_id, cantidad, motivo, cuando`), con `venta_id` nulo y `CHECK (cantidad <> 0)` — *verificar:* `\d movimiento_stock` — *fuente:* RN-12, consigna p.6.
- [ ] `intento_acceso` tiene `id, cuando, email, ip, exito` e índice `(email, ip, cuando)` — *verificar:* `\d intento_acceso` — *fuente:* consigna p.5.
- [ ] `evento_seguridad` tiene `id, cuando, actor, accion`; `actor` es **texto** y **sin FK** a `usuario` — *verificar:* `\d evento_seguridad` (sin `REFERENCES`) — *fuente:* consigna p.5-6, p.11.
- [ ] `perfil_cliente.cliente_id` sigue siendo FK `UNIQUE` (1—1) y las tablas del TP no fueron redefinidas; las columnas `(heredado)` se confirman contra el repo del TP cap. 1-4 — *verificar:* `\d perfil_cliente` y `alembic history` del TP — *fuente:* consigna p.4, IN-07.
- [ ] Invariante: para cada libro, `stock = SUM(movimiento_stock.cantidad)` — *verificar:* `SELECT l.id FROM libro l LEFT JOIN movimiento_stock m ON m.libro_id=l.id GROUP BY l.id, l.stock HAVING l.stock <> COALESCE(SUM(m.cantidad),0);` → 0 filas tras el seed y tras cada venta — *fuente:* RN-11, consigna p.6.
## 5. Autenticación

- [ ] bcrypt con costo desde `Settings` (no fijo en el código) y toda llamada bajo `to_thread` + semáforo — *verificar:* `grep -rn "bcrypt\|to_thread\|Semaphore" app/core/security.py` — *fuente:* consigna p.11.
- [ ] El hash se calcula **antes** de abrir la transacción — *verificar:* el `hash` está fuera del `async with uow` en el servicio de registro/alta — *fuente:* consigna p.11.
- [ ] Todo campo que termina en bcrypt (registro, alta de personal, login, cambio) acepta **≤ 72 bytes** y devuelve **422**, no 500 — *verificar:* cambiar-password con 73 bytes y con 40 «ñ» → 422 — *fuente:* consigna p.11, RN-15.
- [ ] El login no devuelve el token en el cuerpo; viaja sólo en `Set-Cookie: access_token` con `HttpOnly`, `SameSite=Lax`, `Max-Age` = TTL y `Secure` configurable, y la dependencia lo lee de `request.cookies`, **nunca** de `Authorization` — *verificar:* `.http` de C-03 y `grep -rn "Authorization" app/` (vacío) — *fuente:* consigna p.11, p.19-20.
- [ ] El JWT lleva `sub`, `exp` y los roles vigentes al emitirlo; `exp` lo valida PyJWT y no hay comparación con `iat` — *verificar:* decodificar el token de C-03 — *fuente:* consigna p.11, IN-06.
- [ ] El login aplica el límite **antes** de verificar credenciales: el 6.º fallo en 60 s → **429 + `Retry-After`**, en milisegundos y sin calcular hash — *verificar:* `.http` de C-05 midiendo el tiempo — *fuente:* RN-07, consigna p.11.
- [ ] Un login correcto reinicia la cuenta: los fallos previos quedan en la tabla pero dejan de contar — *verificar:* 4 fallos → login OK → 4 fallos → el siguiente sigue en 401, no 429 — *fuente:* RN-07.
- [ ] La respuesta y el tiempo son iguales exista o no el correo (hash ficticio) — *verificar:* `.http` de C-04 comparando cuerpo y duración de los dos 401 — *fuente:* RN-08, consigna p.7.
- [ ] `GET /auth/yo` devuelve el usuario, sus roles **vigentes** y los que dice el token — *verificar:* respuesta de C-07 — *fuente:* consigna p.11, p.16.
- [ ] `POST /auth/logout` borra la cookie (`Set-Cookie` con `Max-Age=0`), de modo que la siguiente petición protegida da **401**, igual que sin cookie, con token inválido o vencido, o con usuario inexistente o inactivo — *verificar:* `.http` de logout y de C-03/C-06 — *fuente:* consigna p.11, p.16, p.21.
- [ ] `POST /auth/cambiar-password` **no** emite token nuevo ni invalida la cookie anterior, y deja `debe_cambiar_password = false` — *verificar:* `.http` de C-09: la misma cookie entra a rutas protegidas (200) sin volver a loguear — *fuente:* consigna p.11, p.21, IN-03.
- [ ] Con `debe_cambiar_password = true` todo el grupo protegido da **403** y sólo pasan `/auth` y las rutas abiertas — *verificar:* `.http` de C-09 con `nuevo@example.com` — *fuente:* RN-06, consigna p.7, p.12.
## 6. Autorización

- [ ] `requiere_rol` consulta `asignacion_rol` en **cada** petición y no confía en el claim `roles` — *verificar:* `grep -n "AsignacionRol" app/core/dependencies.py` y C-07 — *fuente:* RN-04, consigna p.11.
- [ ] Revocar un rol quita el permiso a una sesión ya abierta (sin esperar el vencimiento del token) y una asignación con `vence_en <= now()` no otorga permiso — *verificar:* `.http` de C-07 con la misma cookie, más un vencimiento cercano reintentado después — *fuente:* RN-04, consigna p.11, AB-10.
- [ ] Un vencimiento en el pasado o sin zona horaria da **422**, no 409 — *verificar:* `.http` de C-07 con las dos fechas inválidas — *fuente:* consigna p.11, p.21.
- [ ] Reasignar un rol vencido cierra la fila anterior y abre una nueva; la fila revocada **nunca se borra** — *verificar:* `SELECT * FROM asignacion_rol` antes y después (C-07) — *fuente:* RN-03, consigna p.11.
- [ ] Un ADMIN no puede revocarse su propio ADMIN y el sistema nunca queda sin administradores vigentes → **409** — *verificar:* `.http` de C-08 — *fuente:* RN-05, consigna p.7.
- [ ] `GET /ventas/{id}` **no** lleva `requiere_rol`: decide el servicio (personal o dueño 200; ajeno 403) — *verificar:* `grep -n "requiere_rol" app/modules/ventas/router.py` (ausente en esa ruta) y C-06 — *fuente:* consigna p.18.
- [ ] `/mis-ventas` sólo pide estar autenticado y devuelve únicamente las ventas del cliente ligado al usuario; lo ajeno da **403** — *verificar:* `.http` de C-06 con `ana@example.com` — *fuente:* RN-14, consigna p.8, p.18.
## 7. Capas y transacciones

- [ ] `BaseRepository[T]` recibe `(session, model_class)` y ofrece `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `SoftDeleteRepository[T]` hereda, filtra los dados de baja y agrega `get_by_id_including_deleted` y `soft_delete`, que la base **no** tiene — *verificar:* `open app/core/repository.py` — *fuente:* consigna p.12.
- [ ] Ningún repositorio hace `commit()`: sólo `flush()` — *verificar:* `grep -rn "commit()" app/core/repository.py app/modules/*/repository.py` (vacío) — *fuente:* consigna p.12, p.20.
- [ ] El UoW base confirma en `__aexit__` sin excepción, revierte con excepción y **no cierra** la sesión — *verificar:* `open app/core/unit_of_work.py` — *fuente:* CV-01, consigna p.12, p.20.
- [ ] Cada módulo tiene su UoW, que compone sus repositorios con **la misma** sesión — *verificar:* `ls app/modules/*/unit_of_work.py` — *fuente:* consigna p.12.
- [ ] Ningún servicio recibe una `AsyncSession` ni construye su UoW — *verificar:* `grep -rn "AsyncSession\|UnitOfWork(" app/modules/*/service.py` (vacío) — *fuente:* CV-01, consigna p.12, p.20.
- [ ] Las dependencias de usuario actual y de rol usan **la misma sesión** que el UoW (una conexión por petición autenticada) — *verificar:* leer `get_usuario_actual` y `requiere_rol` en `dependencies.py` — *fuente:* consigna p.12.
- [ ] El auto-registro (RN-02) escribe usuario + rol CLIENTE + ficha de cliente en **un** `async with uow` — *verificar:* forzar un fallo en la ficha → `SELECT count(*) FROM usuario` no crece — *fuente:* RN-02, consigna p.7.
- [ ] Registrar una venta escribe venta + renglones + descuento de stock + un movimiento por renglón en **un** `async with uow` — *verificar:* `.http` de C-11 (409 sin escrituras) — *fuente:* RN-10, consigna p.7, p.12.
- [ ] Cada `intento_acceso` se escribe en sesión y transacción **propias**, confirmadas siempre, y el código lo declara en un comentario con qué hace distinto, por qué no comparte transacción y cuál es su costo — *verificar:* `grep -n -B2 -A8 "propia" app/modules/usuarios/service.py` — *fuente:* consigna p.12.
- [ ] El stock se escribe en **un único punto**, usado por el alta, la reposición y la venta — *verificar:* `grep -rn "stock" app/modules/libros/service.py` (una sola asignación de `libro.stock`) — *fuente:* RN-11, consigna p.12.
- [ ] Los eventos de seguridad (RN-16) se escriben en la misma transacción del cambio — *verificar:* forzar rollback en un alta de personal → no queda línea en `evento_seguridad` — *fuente:* RN-16, consigna p.8.
## 8. Ventas, stock y catálogo

- [ ] No existe `PATCH /ventas/{id}`: las ventas no se modifican — *verificar:* `grep -n "patch" app/modules/ventas/router.py` (vacío) y `GET /openapi.json` — *fuente:* RN-09, consigna p.7.
- [ ] El cuerpo de `POST /ventas` sólo acepta `cliente_id` y `renglones[{libro_id, cantidad}]`; mandar `precio`, `total` o `fecha` da **422** — *verificar:* `.http` de C-16 — *fuente:* RN-09, consigna p.18-19.
- [ ] La venta exige ≥ 1 renglón y sin libros repetidos — *verificar:* `POST /ventas` con `renglones: []` y con `libro_id` repetido → 422 — *fuente:* RN-09.
- [ ] El precio de cada renglón se copia del libro y el total lo calcula el servidor — *verificar:* `.http` de C-10: precios y total coinciden con `libro.precio` — *fuente:* RN-09, consigna p.22.
- [ ] Si un libro no alcanza, no queda **ninguna** escritura (ni venta, ni renglones, ni descuentos, ni movimientos) → **409** — *verificar:* `.http` de C-11 + la query del invariante (0 filas) — *fuente:* RN-10, consigna p.22.
- [ ] Cliente inexistente, libro inexistente o libro dado de baja en una venta → **409** sin escrituras — *verificar:* `.http` de C-12 — *fuente:* RN-10, RN-13.
- [ ] `POST /libros/{id}/reponer` responde **200**, sube el stock y deja su movimiento, y `GET /libros/{id}/movimientos` responde **200** con los movimientos del libro — *verificar:* `.http` de C-13 y luego el listado de movimientos — *fuente:* RN-11, consigna p.17, p.22.
- [ ] `DELETE /libros/{id}` es baja lógica: **204**, escribe `borrado_en` y el libro desaparece de todos los listados y del detalle público — *verificar:* `.http` de C-13 + `SELECT borrado_en FROM libro WHERE id=…` — *fuente:* RN-13, consigna p.10, p.22.
- [ ] Un libro dado de baja no se puede vender ni reponer → **409** — *verificar:* `.http` de C-12/C-13 — *fuente:* RN-13.
- [ ] Dar de baja un libro ya dado de baja o inexistente → **404** — *verificar:* repetir el `DELETE` — *fuente:* RN-13, consigna p.10.
- [ ] Re-alta con el ISBN de un libro dado de baja → **201**; un segundo libro **vigente** con ese ISBN → **409** — *verificar:* `.http` de C-13 — *fuente:* RN-01, consigna p.22.
- [ ] `PATCH /libros/{id}` sólo acepta título y precio; mandar `stock` da **422**; aplica sólo lo enviado — *verificar:* `.http` de C-16 — *fuente:* RN-11, consigna p.10, p.17.
- [ ] `POST /libros` recibe `stock_inicial` (no `stock`) y deja el movimiento «Stock inicial» — *verificar:* alta + `GET /libros/{id}/movimientos` — *fuente:* RN-11, consigna p.17-19.
- [ ] El detalle de una venta sigue mostrando el título de un libro dado de baja — *verificar:* `.http` de C-13 tras la baja — *fuente:* RN-13, consigna p.22.
### Datos iniciales (`seed.py`)

- [ ] Vacía las tablas y carga los 5 usuarios (`admin`, `admin2`, `vendedor`, `ana` y `nuevo` con cambio pendiente) con sus roles, 3 editoriales, 3 géneros, 6 autores y los 5 libros con stock 10/5/8/3/1 — *verificar:* `SELECT u.email, a.rol FROM usuario u JOIN asignacion_rol a ON a.usuario_id=u.id;` y `SELECT titulo, stock FROM libro;` — *fuente:* consigna p.19-20.
- [ ] Carga Lucía (con perfil), Tomás (sin usuario) y Ana (con `usuario_id`) — *verificar:* `SELECT nombre, usuario_id FROM cliente;` — *fuente:* consigna p.20.
- [ ] Carga la venta 1 (1 Rayuela + 2 Ficciones, total 69000.00), un «Stock inicial» por libro con los movimientos −1 y −2, y una línea de `evento_seguridad` con actor `SISTEMA` — *verificar:* `SELECT total FROM venta WHERE id=1;`, la query del invariante y `SELECT actor, accion FROM evento_seguridad;` — *fuente:* consigna p.20.
- [ ] El seed es idempotente: correrlo dos veces deja el mismo estado — *verificar:* `python seed.py; python seed.py` — *fuente:* CV-11.
## 9. Errores y paginación

- [ ] Todo listado devuelve `{items, total, page, size, pages}` — *verificar:* `GET /libros?size=2` (C-16) — *fuente:* consigna p.10, p.19.
- [ ] `page` empieza en 1; `size` va de 1 a 100 con default **20** — *verificar:* `size=500` → 422 y sin `size` → `size: 20` — *fuente:* consigna p.10.
- [ ] Pedir una página más allá de la última da **422** con mensaje propio («La página 4 no existe: hay 3») — *verificar:* `.http` de C-16 — *fuente:* consigna p.10, p.19.
- [ ] `total` se cuenta con **los mismos filtros** que la página y con cero resultados hay **una** página vacía (`items: []`, `pages: 1`) — *verificar:* `titulo=ficc&size=1` → `total: 1, pages: 1`; `page=2` → 422; búsqueda sin coincidencias — *fuente:* consigna p.10, p.22.
- [ ] Ningún error devuelve texto interno de la base ni una traza — *verificar:* provocar violación de unicidad y de FK y leer el body — *fuente:* RN-15, consigna p.8, p.20.
- [ ] Ninguna entrada inválida termina en **500**: id no entero, JSON malformado, NUL, `size` gigante, contraseña de 73 bytes — *verificar:* `.http` de C-01 y C-16 — *fuente:* RN-15, consigna p.21.
- [ ] La búsqueda por título usa parámetros ligados y no distingue mayúsculas; `' OR '1'='1` no rompe ni devuelve todo — *verificar:* `.http` de C-16 (lista vacía, `total: 0`) — *fuente:* consigna p.6, p.10, p.22.
- [ ] Todo schema de entrada declara `extra="forbid"` y los PATCH usan `exclude_unset`; los códigos son los de la tabla de endpoints (201 al crear, 204 al dar de baja, 404 recurso de la ruta, 409 choque, 422 contrato) — *verificar:* `grep -rn "extra=\"forbid\"\|exclude_unset" app/modules` y los `.http` de cada módulo — *fuente:* CV-07, consigna p.10, p.16-18.
## 10. Pruebas

- [ ] Hay un `.http` por caso `C-NN`, con la respuesta esperada en un comentario, y todos se corrieron tras `python seed.py` — *verificar:* `ls test/*.http` y ejecutar con REST Client — *fuente:* consigna p.21.
- [ ] **C-01** `GET /libros/abc` con sesión → 422, sin ejecutar el handler — *verificar:* `.http` + log sin la query — *fuente:* consigna p.21.
- [ ] **C-02** registro 201; correo repetido de usuario y de cliente → 409 con mensaje propio y sin filas sueltas — *verificar:* `.http` + `SELECT count(*)` en `usuario` y `cliente` — *fuente:* consigna p.21.
- [ ] **C-03** `Set-Cookie` con `HttpOnly`, `SameSite=Lax`, `Max-Age`; cuerpo sin token; sin cookie o con `Authorization: Bearer` → 401 — *verificar:* `.http` — *fuente:* consigna p.21.
- [ ] **C-04** correo existente con contraseña mala y correo inexistente → 401, mismo cuerpo y tiempo parecido — *verificar:* `.http` comparando duración — *fuente:* consigna p.21.
- [ ] **C-05** seis fallos seguidos → el sexto 429 con `Retry-After` en pocos ms y los cinco fallos en `intento_acceso` — *verificar:* `.http` + `SELECT * FROM intento_acceso` — *fuente:* consigna p.21.
- [ ] **C-06** sin sesión 401; un VENDEDOR creando libro 403; la cliente ve su venta 200 y la ajena 403 — *verificar:* `.http` — *fuente:* consigna p.21.
- [ ] **C-07** revocar rol con sesión abierta → 403 en la petición siguiente; `/auth/yo` muestra la diferencia; la fila revocada sigue; vencimiento pasado o sin zona → 422 — *verificar:* `.http` con dos sesiones (`# @name`, `# @no-cookie-jar`) — *fuente:* consigna p.21, p.23.
- [ ] **C-08** el administrador no se revoca su ADMIN → 409 — *verificar:* `.http` — *fuente:* consigna p.21.
- [ ] **C-09** cambio obligatorio bloqueado (403) salvo `/auth`; después `debe_cambiar_password` en falso y la misma cookie entra al grupo protegido (200) — *verificar:* `.http` con `nuevo@example.com` — *fuente:* consigna p.21.
- [ ] **C-10** venta válida con dos renglones → 201 con precios copiados y total, stock bajado, un movimiento por renglón y el aviso en el registro después de la respuesta — *verificar:* `.http` + consola del servidor — *fuente:* consigna p.22.
- [ ] **C-11** Rayuela (1, alcanza) + Bestiario (2, hay 1) → 409 sin venta, descuentos ni movimientos; el invariante sigue en 0 filas — *verificar:* `.http` + query del invariante — *fuente:* consigna p.22.
- [ ] **C-12** cliente inexistente, libro inexistente o libro dado de baja → 409 en los tres, sin escrituras — *verificar:* `.http` — *fuente:* consigna p.22.
- [ ] **C-13** reponer 200 con movimiento; baja 204; el libro sale del catálogo; re-alta con el mismo ISBN 201; segundo vigente 409; la venta vieja sigue mostrando el título — *verificar:* `.http` — *fuente:* consigna p.22.
- [ ] **C-14** `UPDATE` y `DELETE` sobre `movimiento_stock` en `psql` son rechazados por el disparador — *verificar:* `psql -f test/solo_agregado.sql` (dos errores) — *fuente:* RN-12, consigna p.21-22.
- [ ] **C-15** el detalle de una venta con 2 y con 4 renglones emite **la misma cantidad** de consultas — *verificar:* `SQL_ECHO=true` y contar las líneas `SELECT` en consola — *fuente:* consigna p.13, p.22.
- [ ] **C-16** `' OR '1'='1` → lista vacía con `total: 0`; paginación con filtro; PATCH parcial; `PATCH` con `stock` → 422 — *verificar:* `.http` — *fuente:* consigna p.22.
- [ ] Al registrar una venta se agenda el aviso con `BackgroundTasks`, `await asyncio.sleep(0.5)` y un log **visible** con el arranque normal de uvicorn — *verificar:* `uvicorn main:app` y ver el mensaje después de la respuesta — *fuente:* consigna p.13, p.20.
- [ ] Todos los handlers son `async def`, ninguna ruta ejecuta una llamada bloqueante y `pytest` pasa completo contra PostgreSQL real (nunca SQLite), comparando status + body — *verificar:* `grep -rn "def " app/modules/*/router.py | grep -v "async def"` (vacío) y `pytest -q` con `POSTGRES_*` apuntando a la base de prueba — *fuente:* CV-12, RD-01, consigna p.13, p.20.
## 11. Despliegue (carpeta `despliegue/`, TP cap. 1-4)

- [ ] El `Dockerfile` parte de `python:3.12-alpine` y esa base mide menos de 100 MB — *verificar:* `docker images` → D-01 — *fuente:* consigna p.14, p.22.
- [ ] Copia e instala `requirements.txt` con `--no-cache-dir` **antes** de copiar el código, y corre con usuario sin privilegios (`USER`), nunca root — *verificar:* leer el `Dockerfile` y `docker exec libreria id` — *fuente:* consigna p.14, p.23 (D-07).
- [ ] `.dockerignore` excluye `.env`, `.venv`, `.git` y `__pycache__`, y ni la dirección de la base ni su contraseña están en el `Dockerfile` ni en la imagen — *verificar:* `cat .dockerignore`, `docker run --rm --entrypoint env <imagen>` y `--entrypoint ls <imagen> -a /app` — *fuente:* consigna p.14, p.23 (D-06).
- [ ] Al arrancar aplica `alembic upgrade head` y luego levanta uvicorn en `--host 0.0.0.0`; si la base no responde, el contenedor termina con error — *verificar:* `docker logs libreria` y D-02/D-05 — *fuente:* consigna p.14, p.22.
- [ ] `HEALTHCHECK` contra `GET /health/ready` usando `127.0.0.1` (Alpine no trae curl y `localhost` resuelve a `::1`) — *verificar:* `grep -n "HEALTHCHECK" Dockerfile` y `docker exec libreria wget -qO- http://127.0.0.1:8000/health/live` — *fuente:* consigna p.14-15.
- [ ] Se corre con `docker run -d --name libreria -p <puerto>:8000 --restart unless-stopped --env-file <archivo> libreria`, sin Docker Compose — *verificar:* comparar con `DEPLOY.md` — *fuente:* consigna p.14-15.
- [ ] La `DATABASE_URL` del `--env-file` no usa `localhost`; si la base está en el host Linux, se usa `host.docker.internal` con `--add-host` — *verificar:* D-03 desde afuera — *fuente:* consigna p.15.
- [ ] Al TP sólo se le agregaron `Dockerfile` y `.dockerignore`; su lógica no cambió (o el defecto propio se corrigió y se anotó) — *verificar:* `git diff` contra la entrega del TP cap. 1-4 — *fuente:* consigna p.14.
- [ ] **D-01…D-08** corridos, con comando y salida guardados uno por archivo en `despliegue/evidencia/` — *verificar:* `ls despliegue/evidencia` (8 archivos) — *fuente:* consigna p.21-23.
- [ ] `DEPLOY.md` tiene URL pública, día y hora, `docker build` y `docker run` completos (con el **nombre** del archivo de variables y sin su contenido), cambios al TP y procedimiento de actualización — *verificar:* leer `DEPLOY.md` — *fuente:* consigna p.16.
- [ ] La URL pública responde `/health/ready` 200, `/libros/` 200 con datos y `POST /ventas/` 201 con precios copiados y total — *verificar:* `curl` desde fuera del VPS (D-03) — *fuente:* consigna p.22.
- [ ] El aviso del comprobante aparece en `docker logs libreria` **después** de la línea de la respuesta — *verificar:* D-08 — *fuente:* consigna p.23.
- [ ] `docker rm -f libreria` + el mismo `docker run` → vuelve `healthy`, los datos siguen y las migraciones no se repiten — *verificar:* D-04 — *fuente:* consigna p.22.
- [ ] El despliegue queda en línea hasta que se publiquen las notas — *verificar:* `curl` el día de la corrección — *fuente:* consigna p.16, p.24.
## 12. Formato de entrega

- [ ] El archivo se llama `Parcial_Cap1a6_<NombreDelGrupo>.zip`, lo sube un solo integrante y contiene **dos** carpetas: `parcial/` y `despliegue/` — *verificar:* nombre del archivo en el campus y extracción en carpeta temporal — *fuente:* consigna p.1, p.24, IN-04.
- [ ] `parcial/` trae código fuente, `requirements.txt`, `env.example`, `alembic.ini`, `migrations/`, `test/`, `README.md` y `evidencia/`, y esa `evidencia/` tiene la captura de C-15 (consultas con 2 y con 4 renglones) y la de `psql` de C-14 — *verificar:* `ls parcial parcial/evidencia` — *fuente:* consigna p.24.
- [ ] `despliegue/` trae el TP cap. 1-4 + `Dockerfile` + `.dockerignore` + `env.example` (forma de `DATABASE_URL`, sin valores) + `DEPLOY.md` + `evidencia/` — *verificar:* `ls despliegue` — *fuente:* consigna p.24, IN-04.
- [ ] El zip **no** contiene `.venv`, `__pycache__` ni `.env` en **ninguna** de las dos carpetas — *verificar:* `Get-ChildItem -Recurse -Force` sobre lo extraído, buscando `.venv`, `__pycache__` y `.env` — *fuente:* consigna p.1, p.24.
- [ ] `parcial/README.md` tiene nombres y apellidos y los pasos desde cero: venv, dependencias, `.env` con cómo generar la clave de firma, `alembic upgrade head`, `python seed.py` y arranque — *verificar:* leer el README — *fuente:* consigna p.24.
- [ ] Si se incluye `.git`, el historial no tiene credenciales; `git status` está limpio y el zip sale del commit final — *verificar:* `git log -p | Select-String -Pattern "password|secret|DATABASE_URL"` y `git status --short` — *fuente:* consigna p.24.
## 13. Autoevaluación contra la rúbrica (p. 23-24)

| Criterio | Peso | Ítems que lo evidencian | Verificado |
|---|---|---|---|
| Proyecto, configuración y ciclo de vida | 6 % | §1 completo; §2 (seis primeros); C-01 | [ ] |
| Modelos, relaciones y migraciones | 10 % | §3 completo; §4 completo | [ ] |
| Contratos y CRUD | 8 % | §9 completo; §8 (PATCH, reponer, baja); C-16 | [ ] |
| Autenticación | 14 % | §5 completo; C-03, C-04, C-05, C-09 | [ ] |
| Autorización | 12 % | §6 completo; C-06, C-07, C-08, C-09 | [ ] |
| Repositorios y Unit of Work | 16 % | §7 completo; venta transaccional (§8); C-11 | [ ] |
| Integridad | 10 % | §3 (cuarta migración); §7 (intento propio, eventos); C-14 | [ ] |
| Lecturas sin N+1 y asincronía | 6 % | §10 (C-15, `async def`, aviso con `BackgroundTasks`) | [ ] |
| Contenedor: la imagen | 11 % | §11 (seis primeros); D-01, D-02, D-05, D-06, D-07 | [ ] |
| Despliegue en el VPS | 7 % | §11 (URL, `DEPLOY.md`, `evidencia/`); D-03, D-04, D-08 | [ ] |

- [ ] Ninguna condición anula la corrección: el proyecto levanta, el esquema sale de `alembic upgrade head` sobre base vacía y no hay credenciales reales en el repo, la imagen ni el zip — *verificar:* recorrer §0, §2, §3 y §11 — *fuente:* consigna p.24.

> **Frase de cierre.** Si un caso `C-NN` no se corrió literalmente, no está verificado. Si el JSON real no se miró, no está
> verificado. Si no se corrió en una carpeta limpia, no está verificado.
