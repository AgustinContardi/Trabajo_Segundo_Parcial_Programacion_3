# Tasks

> Convención TDD: cada grupo con comportamiento observable empieza con una tarea **RED** (la prueba
> escrita antes del cambio falla por la razón esperada) y sigue con **GREEN** (el cambio mínimo y la
> prueba pasa). Las tareas documentales no tienen RED. Todos los comandos se corren desde `parcial/`
> salvo los que indiquen otra ruta. No se hace `commit` ni `push`.

## 1. Baseline y base temporal

- [x] 1.1 Registrar el punto de partida: `git status --short` (sólo `docs/auditoria-final/` sin trackear),
  `python -m alembic current` = `c8d2dea5529f (head)` y `python -m alembic check` sin drift. Verificación:
  los tres comandos coinciden con el estado del informe final.
- [x] 1.2 Crear una base temporal vacía (`libreria_fix_audit`), correr `alembic upgrade head` y anotar las
  tablas creadas. Verificación: exit 0 y `\dt` muestra las 14 tablas de dominio; la base se elimina al
  terminar la tarea 3.4.
- [x] 1.3 Correr `pytest -q` completo antes de tocar código y anotar el resultado (esperado: 459 passed /
  1 skipped). Verificación: el número queda registrado para comparar al final.

## 2. B-1 · C-10 — `GET /mis-ventas` en su path canónico

- [x] 2.1 **RED**: cambiar en `tests/test_ventas_authorization.py` y `tests/test_cambio_password_api.py`
  las tres llamadas a `/ventas/mis-ventas` por `/mis-ventas`; agregar una prueba que lea `api_app.openapi()`
  y exija `/mis-ventas` presente y `/ventas/mis-ventas` ausente. Verificación: `pytest -q
  tests/test_ventas_authorization.py tests/test_cambio_password_api.py` falla con 404 en las rutas nuevas
  y con la ruta vieja todavía publicada.
- [x] 2.2 **GREEN**: en `app/modules/ventas/router.py` declarar `router_mis_ventas = APIRouter(tags=["ventas"])`,
  mover el handler `@router.get("/mis-ventas")` con su cuerpo intacto y quitar el decorador del router con
  prefijo; en `main.py` importar y montar `router_mis_ventas` dentro de `router_protegido` (después de
  `ventas_router`). Verificación: las pruebas de 2.1 pasan y `POST /ventas`, `GET /ventas/` y
  `GET /ventas/{id}` no cambian.
- [x] 2.3 Verificar el contrato en proceso: `GET /mis-ventas` sin cookie → 401; con cookie de cliente →
  200 con `{items,total,page,size,pages}`; `GET /ventas/mis-ventas` → 404; `openapi.json` contiene
  `/mis-ventas` y no `/ventas/mis-ventas`. Verificación: script corto con `httpx.ASGITransport` y salida
  registrada en la tarea.
- [x] 2.4 Actualizar `test/roles.http` con un bloque C-06.6 que llame a `GET /mis-ventas` con la cookie de
  Ana y declare `# Esperado: 200` con el envoltorio; actualizar la fila C-06 en `test/EVIDENCIA.md`.
  Verificación: `Select-String -Path parcial/test/*.http,parcial/test/EVIDENCIA.md -Pattern
  "/ventas/mis-ventas"` no devuelve ninguna ruta canónica y `Select-String -Pattern "GET /mis-ventas"` sí.

## 3. B-2 · C-04 — defaults `now()` reales

- [x] 3.1 **RED**: crear `tests/test_migrations_defaults.py` que consulte `pg_get_expr(adbin, adrelid)` para
  `asignacion_rol.desde`, `intento_acceso.cuando`, `evento_seguridad.cuando`, `movimiento_stock.cuando` y
  `venta.fecha`, exija `now()` en las cinco, e inserte dos `EventoSeguridad` en transacciones separadas
  afirmando que sus `cuando` están próximos a `now()` y no comparten el literal congelado (limpiar las dos
  filas al final). Verificación: la prueba falla hoy mostrando el literal `2026-11-…`.
- [x] 3.2 Crear la migración `0005` con `python -m alembic revision -m "0005_now_server_defaults"` (sin
  `--autogenerate`), comprobar que el archivo queda como `<rev>_0005_now_server_defaults.py` (renombrarlo
  si el `file_template` agrega otro prefijo) y escribir en `upgrade` los cinco
  `op.alter_column(..., server_default=sa.text("now()"))`; en `downgrade`, restaurar la forma histórica
  `server_default="now()"` con un comentario que explique que vuelve a congelar el valor.
  Verificación: leer el archivo entero antes de aplicar (regla 9), `alembic upgrade head` en la base
  temporal de 1.2, `pg_get_expr` = `now()` en las cinco columnas y `alembic check` limpio.
- [x] 3.3 Cambiar los cinco modelos a `server_default=text("now()")`: `app/modules/usuarios/models.py`
  (`AsignacionRol.desde`, `IntentoAcceso.cuando`, `EventoSeguridad.cuando`), `app/modules/libros/models.py`
  (`MovimientoStock.cuando`) y `app/modules/ventas/models.py` (`Venta.fecha`, agregando el import de
  `text`). Verificación: `alembic check` sobre la base temporal y sobre la base de trabajo sigue limpio.
- [x] 3.4 **GREEN**: correr `tests/test_migrations_defaults.py` contra la base de trabajo (después de
  `alembic upgrade head`), luego `python seed.py` **dos veces** y la query del invariante. Verificación: la
  prueba pasa, el seed imprime `Seed OK` en ambas corridas con los mismos conteos/idempotencia (C-17), los
  `cuando` de `evento_seguridad` y `movimiento_stock` del seed son cercanos a la hora real y la query de §4
  devuelve 0 filas; eliminar la base temporal y anotar que las filas históricas conservan su sello (no se
  reescribieron).

## 4. M-1 · C-08/C-09 — actor del movimiento de stock

- [x] 4.1 **RED**: agregar a `tests/test_catalogo_rbac.py` (o a un nuevo `tests/test_stock_atribucion.py`)
  una prueba que cree **dos** administradores con `usuario_factory`, autentique al segundo, cree con
  `POST /libros` un libro de ISBN único y `stock_inicial > 0`, reponga stock y registre el id en
  `catalogo_factory.registrar_libro`; consulte `GET /libros/{id}/movimientos` y exija que los movimientos
  «Stock inicial» y «Reposición» tengan `usuario_id` igual al id del segundo administrador (no al
  primero). Verificación: la prueba falla hoy porque el fallback asigna el primer usuario.
- [x] 4.2 **GREEN**: en `app/modules/libros/router.py` pasar `usuario_actual=_sesion.usuario` en
  `crear_libro` y `reponer_libro`; en `app/modules/libros/service.py` eliminar el `select id from usuario
  limit 1` y responder `409` con mensaje propio si hay que escribir un movimiento y no llegó actor.
  Verificación: la prueba de 4.1 pasa y el invariante global sigue en 0 filas.
- [x] 4.3 Agregar una prueba de servicio con UoW falso que llame `crear(..., stock_inicial>0)` y
  `reponer(...)` sin `usuario_actual` y espere `409` sin escribir movimiento. Verificación: ambos casos
  pasan y no se invoca el repositorio de movimientos.
- [x] 4.4 Verificar la atribución con un administrador distinto del seed: `GET /libros/{id}/movimientos`
  devuelve `usuario_id` igual al actor en «Stock inicial» y «Reposición». Verificación: la salida de la
  prueba 4.1 y la consulta SQL del movimiento lo confirman.

## 5. M-2 · C-07 — paginación determinista de ventas del cliente

- [x] 5.1 **RED**: en `tests/test_clientes_rbac.py` agregar una prueba de API con un cliente y tres ventas
  creadas por `venta_factory`: `size=2&page=1` devuelve los ids `[v1, v2]`, `size=2&page=2` devuelve
  `[v3]`, sin repetidos ni faltantes; agregar una prueba que compile `ClienteRepository.ventas_de_stmt` y
  exija `ORDER BY venta.id`. Verificación: la prueba de SQL falla porque el método/orden no existe.
- [x] 5.2 **GREEN**: en `app/modules/clientes/repository.py` extraer
  `ventas_de_stmt(cliente_id)` con `.order_by(Venta.id)` y hacer que `ventas_de` pagine ese statement.
  Verificación: ambas pruebas de 5.1 pasan y dos llamadas idénticas devuelven el mismo orden.

## 6. M-3 · C-06 — contrato editorial y `GET /generos/{id}`

- [x] 6.1 **RED**: agregar pruebas de `GET /generos/{id}` (200 con `{id,nombre}`, 404 con
  `"Género no encontrado"`) y actualizar `RUTAS_CATALOGO_ESPERADAS` de `tests/test_catalogo_protegido.py`
  con `("GET", "/generos/{genero_id}")`. Verificación: la prueba de ruta falla con 404/`faltan`.
- [x] 6.2 **GREEN**: agregar la ruta pública `@router.get("/{genero_id}", response_model=GeneroRead)` en
  `app/modules/generos/router.py` usando `service.obtener`. Verificación: 6.1 pasa y la tabla de rutas del
  catálogo queda completa.
- [x] 6.3 Acotar la promesa de `409` de `PATCH /autores`: documentar en `app/modules/autores/service.py`
  que `autor` no tiene unicidad y que la traducción de `IntegrityError` es defensa ante constraints
  futuras; agregar una prueba de API que cree dos autores homónimos y haga `PATCH` de uno a los valores del
  otro esperando `200`. Verificación: la prueba pasa y `openapi.json` no cambia para autores.
- [x] 6.4 Unificar la numeración `CV-01/CV-02/CV-03` con la KB: `CV-02` = precarga sólo en
  `repository.py`, `CV-03` = paths exactos, `CV-01` = router/servicio/UoW. Corregir los comentarios de
  `app/core/repository.py`, `app/core/database.py`, `app/modules/*/repository.py` y `main.py`.
  Verificación: `Select-String -Path parcial/app/core/*.py,parcial/app/modules/*/repository.py,parcial/main.py
  -Pattern "CV-0[123]"` muestra cada código con el significado de la KB; la suite sigue verde.
- [x] 6.5 Agregar una **errata** al final del `tasks.md` archivado de C-06 que corrija la evidencia
  `python -c "import app.main"` por `python -c "import main"` con `PYTHONPATH=parcial`, sin tocar tareas ni
  estados. Verificación: la errata existe fechada y el archivo conserva sus checkboxes originales.

## 7. M-4 · C-05 — mensajes de validación y contrato CV-08

- [x] 7.1 **RED**: en `tests/test_errors_validation.py` cambiar las expectativas de `bool_type` a
  «Debe ser un valor booleano válido» y de `float_type` a «Debe ser un número válido»; agregar
  `decimal_parsing` con el mismo texto. Verificación: la prueba falla con el mensaje «número entero».
- [x] 7.2 **GREEN**: corregir `MENSAJES_POR_TIPO` en `app/core/errors.py` y dejar los tres tipos enteros
  intactos. Verificación: 7.1 pasa y los tests de `test_ventas_api.py` que buscan «número entero válido»
  siguen verdes.
- [x] 7.3 Agregar el comentario de contrato `CV-08` con el orden real y las condiciones alcanzables en
  `app/modules/autores/service.py`, `app/modules/generos/service.py` y `app/modules/libros/service.py`.
  Verificación: `Select-String -Path parcial/app/modules/*/service.py -Pattern "CV-08"` devuelve los textos
  en los módulos que antes no lo tenían y ninguno promete una rama imposible.

## 8. Menores · C-14 y C-15

- [x] 8.1 Reemplazar `tests/test_control_cambio_password.py::test_control_cambio_password_sin_usuario_no_llega_a_la_verificacion`
  (sólo `pass`) por una prueba real: sin cookie, `GET /clientes/1` → 401; con cookie de un usuario
  `ADMIN` con `debe_cambiar_password=true`, la misma ruta → 403. Actualizar el docstring del archivo para
  declarar que mezcla unitarios y una integración. Verificación: la prueba falla si se invierte el orden y
  pasa con el código actual.
- [x] 8.2 Agregar una **errata** al final del `tasks.md` archivado de C-14: aclarar que
  `test_cambio_password_api.py` mockea y que la corrida real contra PostgreSQL es la de `EVIDENCIA.md`
  §C-09; no cambiar tareas ni estados. Verificación: la errata está fechada y el archivo no perdió sus
  checkboxes.
- [x] 8.3 Alinear `cerrar()` con su docstring en `app/modules/usuarios/repository.py`: documentar «reloj de
  la aplicación en UTC, igual que `abrir()`» y quitar la mención a «default `now()` del servidor».
  Verificación: `Select-String -Path parcial/app/modules/usuarios/repository.py -Pattern "now\(\)"`
  coincide con el texto nuevo y `pytest -q tests/test_admin_roles_service.py
  tests/test_admin_roles_concurrencia.py` sigue verde.

## 9. Documentación de cierre (C-01/C-13/C-17/C-18/C-19)

- [x] 9.1 Actualizar `parcial/README.md`: el paso 4 describe las cinco migraciones encadenadas y el naming
  `<rev>_0005_now_server_defaults.py`; aclarar que los integrantes siguen pendientes de C-22.
  Verificación: leer el README de punta a punta y correr los pasos en una copia limpia o señalar
  explícitamente el único paso que depende de la base del entorno.
- [x] 9.2 Actualizar `docs/CHECKLIST_ENTREGA.md`: §3 pasa a cinco versiones, agrega el check de
  `pg_get_expr = now()` y el naming; §4 corrige «8 columnas» de `asignacion_rol` por 7 y documenta la
  unicidad duplicada de `cliente.usuario_id`; §6.1 cambia el comando a `grep -n "roles_vigentes"
  app/core/dependencies.py` + `grep -n "AsignacionRol" app/modules/usuarios/repository.py`; §12 menciona
  las tres capturas críticas. Verificación: cada comando del checklist devuelve lo que el texto espera.
- [x] 9.3 Dejar reproducible C-07.11 en `parcial/test/roles.http`: encabezado con fecha relativa
  `now() + 1 minuto`, espera y repetición con la misma cookie; corregir la variable fija de 2030.
  Verificación: leer el bloque y confirmar que los pasos producen 200 antes y 403 después (sin editar
  valores fuera de los pasos).
- [x] 9.4 Copiar `parcial/test/evidencia/c-10-backgroundtasks.txt` a `parcial/evidencia/` y actualizar la
  fila correspondiente de `parcial/test/EVIDENCIA.md`. Verificación: `Get-ChildItem parcial/evidencia`
  muestra C-10, C-14 y C-15; `git ls-files parcial/evidencia` incluye el archivo nuevo.
- [x] 9.5 Agregar en `CHANGES.md` una sección correctiva después de C-19 para `fix-auditoria-final`, sin
  renumerar C-01…C-22 ni cambiar sus estados; resumir los 2 FAIL cerrados y los mayores. Verificación: el
  diff sólo agrega la sección y las filas de resumen siguen apuntando a los mismos changes.

## 10. Verificación de integración

- [x] 10.1 Correr `pytest -q` completo contra PostgreSQL y comparar con el baseline de 1.3: 0 fallos, el
  total sube por las pruebas nuevas y el skip E2E se mantiene. Verificación: salida registrada.
- [x] 10.2 Verificar el esquema: `alembic current` = `<rev 0005> (head)`, `alembic check` limpio,
  `pg_get_expr = now()` en las cinco columnas y la query del invariante de stock en 0 filas después de
  `python seed.py`. Verificación: los cuatro comandos y sus salidas.
- [x] 10.3 Verificar `openapi.json`: `/mis-ventas` presente, `/ventas/mis-ventas` ausente,
  `/generos/{genero_id}` presente; `GET /mis-ventas` sin cookie 401 y con cliente 200. Verificación: script
  con `api_app.openapi()` y `httpx.ASGITransport`.
- [x] 10.4 Correr los greps de reglas duras: sin `create_all`, sin `commit()` en repositorios, sin
  `float` para dinero, sin token en cuerpos, `selectinload` sólo en `repository.py`, `CV-08` en los siete
  servicios y ninguna ruta `/ventas/mis-ventas`. Verificación: todos los greps devuelven lo esperado.
- [x] 10.5 Re-ejecutar los bloques `.http` afectados (C-06.6 y C-07.11) tras `python seed.py` y actualizar
  `EVIDENCIA.md` con los status observados. Verificación: la tabla de evidencia coincide con la corrida.
- [x] 10.6 Correr `openspec validate fix-auditoria-final --strict` y `openspec status --change
  fix-auditoria-final`. Verificación: validación estricta OK y todos los artefactos en `done`.

## Workflow follow-up

- Archivar el change recién después de la revisión del usuario y de que la aceptación de §3, §4, §6.7 y §12
  se pueda correr literalmente.
- No hacer `commit` ni `push`: dejar los cambios en el working tree.
- No tocar C-20/C-21/C-22 ni `despliegue/` en este change.
