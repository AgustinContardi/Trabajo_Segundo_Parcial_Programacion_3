# Proposal

## Why

La auditoría final de C-01…C-19 (`docs/auditoria-final/INFORME-FINAL.md`, 2026-11-08) dejó **2 FAIL**
y **32 WARN**. Los dos FAIL son observables desde fuera y bloquean el cierre:

- `GET /mis-ventas` responde **404** porque el handler quedó montado como `/ventas/mis-ventas` (C-10, §6.7).
- `asignacion_rol.desde`, `intento_acceso.cuando`, `evento_seguridad.cuando`, `movimiento_stock.cuando`
  y `venta.fecha` tienen un `DEFAULT` con la **hora congelada de la migración**, no `now()` (C-04, §3).

Corregirlos antes de C-20 (imagen), C-21 (VPS) y C-22 (zip) evita arrastrar evidencia con rutas y sellos de
tiempo incorrectos, y permite cerrar los ítems §3, §4 y §6 del checklist sin reabrir changes archivados.

## What Changes

**Bloqueantes**

1. **C-10 — path canónico de mis ventas**: mover el handler a un router sin prefijo, montarlo en el grupo
   protegido y dejar `GET /mis-ventas` como única ruta publicada. Actualizar tests y evidencia `.http`.
2. **C-04 — defaults de fecha**: agregar una **migración nueva 0005** que ejecute
   `ALTER COLUMN … SET DEFAULT now()` en las 5 columnas y cambiar los 5 modelos a
   `server_default=text("now()")`. **No** se editan las migraciones 0001/0003 ni se reescriben filas
   históricas.

**Mayores**

3. **C-08/C-09 — actor del movimiento**: propagar el usuario autenticado a `crear_libro` y `reponer_libro`
   y eliminar el fallback `SELECT id FROM usuario LIMIT 1`.
4. **C-07 — paginación estable**: `ClienteRepository.ventas_de` ordena por `Venta.id` (criterio documentado)
   y expone el statement para poder probar el `ORDER BY`.
5. **C-06 — contrato editorial**: se retira la promesa inalcanzable de `409` por unicidad en `PATCH /autores`
   (el dominio no define unicidad de autor), se documenta la rama defensiva y se agrega `GET /generos/{id}`.
   Se unifica la numeración `CV-01/CV-02/CV-03` con la KB y se corrige la cita `import app.main` → `import main`.
6. **C-05 — contratos de error**: `bool_type` y `float_type` dejan de decir «número entero»; se agrega el
   comentario de contrato `CV-08` (`404 → 403 → 409 → 422`) en `autores`, `generos` y `libros`.

**Menores documentales (sin riesgo, sin depender de C-20/C-21/C-22)**

7. **C-14**: reemplazar el test con sólo `pass` por una prueba real del orden 401 → 403 y corregir la
   trazabilidad de `tasks.md` con una **errata**, sin alterar el resultado histórico del change archivado.
8. **C-15**: alinear `cerrar()` y su docstring: se documenta el reloj de aplicación en UTC (igual que
   `abrir()`) y se descarta `func.now()` por el riesgo de devolver una expresión SQL sin evaluar.
9. **C-01/C-13/C-17/C-18/C-19**: actualizar `parcial/README.md` (paso 4 y naming de migraciones), los
   comandos de §3/§6.1 del checklist, el procedimiento reproducible de C-07.11 y la ubicación de la captura
   de `BackgroundTasks`. El zip, los integrantes y el despliegue quedan para C-20/C-21/C-22.

## Capabilities

### New Capabilities

Ninguna. El change es correctivo: no introduce comportamiento nuevo de dominio, sólo alinea la
implementación y la documentación con las specs ya aprobadas.

### Modified Capabilities

- `ventas`: `GET /mis-ventas` se publica en el path standalone y `/ventas/mis-ventas` deja de existir.
- `schema-migrations`: pasan a ser **cinco** migraciones encadenadas y los defaults de fecha deben ser
  `now()` evaluado por la base, no un literal congelado.
- `libros`: el `usuario_id` de los movimientos «Stock inicial» y «Reposición» es el usuario autenticado.
- `clientes-y-perfil`: la paginación de ventas del cliente usa un orden determinista (`Venta.id`).
- `editoriales-generos-autores`: se acota el `409` de `PATCH /autores` a las unicidades realmente
  declaradas y se agrega `GET /generos/{id}`.
- `api-contracts`: los mensajes de validación describen el tipo esperado y los servicios documentan
  `CV-08`.
- `casos-de-prueba-c`: el caso C-06 demuestra el path standalone de mis ventas y C-07.11 queda
  reproducible con pasos explícitos.
- `suite-pytest-evidencia`: la suite distingue pruebas con base real de unitarias mockeadas, el test de
  orden 401/403 deja de ser vacío y la captura del aviso de comprobante se guarda en `evidencia/`.

## Impact

- **API**: se agrega `GET /mis-ventas` y `GET /generos/{id}`; se elimina `GET /ventas/mis-ventas`.
  `GET /libros/{id}/movimientos` empieza a mostrar el `usuario_id` real del actor.
- **Base de datos**: una migración nueva (`0005`) con 5 `SET DEFAULT now()`; sin cambios de columnas,
  constraints ni datos históricos. `alembic upgrade head` y `alembic check` deben seguir limpios.
- **Código**: `ventas/router.py`, `main.py`, `libros/{router,service}.py`, `clientes/repository.py`,
  `autores/{models,service}.py`, `generos/router.py`, `core/errors.py`, los 5 modelos con `server_default`
  y comentarios `CV-*` en `app/core`/`app/modules`.
- **Pruebas y evidencia**: `tests/test_ventas_authorization.py`, `test_cambio_password_api.py`,
  `test_control_cambio_password.py`, `test_errors_validation.py`, `test_catalogo_protegido.py`,
  `test_clientes_rbac.py`, nuevos tests de defaults y atribución; `parcial/test/roles.http` +
  `EVIDENCIA.md` + `parcial/evidencia/`.
- **Documentación**: `docs/CHECKLIST_ENTREGA.md` (§3, §4, §6.1, §12), `parcial/README.md`, `CHANGES.md`
  (entrada correctiva, sin renumerar C-01…C-22) y una errata puntual en el `tasks.md` archivado de C-14.
- **Fuera de alcance**: C-20 (imagen), C-21 (VPS), C-22 (zip), `despliegue/`, cualquier `commit`/`push`.
