# Design

## Context

Ver `proposal.md` — Why. El código afectado ya existe y está auditado:

- `parcial/app/modules/ventas/router.py` declara `APIRouter(prefix="/ventas")` y el handler
  `@router.get("/mis-ventas")`; `main.py` monta ese router completo en `router_protegido`.
- La migración `dd4a0e5e9cf7` (0003) y `0ba1752f7c23` (0001) usan `server_default='now()'` como cadena;
  PostgreSQL la compiló a un literal `timestamptz` con la hora del DDL. Los modelos replican la cadena
  (`server_default="now()"`), por eso `alembic check` no detecta el defecto.
- `libros/service.py` mantiene el fallback `select id from usuario limit 1` cuando `usuario_actual` es
  `None`; los routers `crear_libro` y `reponer_libro` reciben `_sesion` pero no lo pasan.
- `ClienteRepository.ventas_de` construye `select(Venta).where(...)` sin `ORDER BY`.
- `Autor` no tiene ningún `UNIQUE`; `GeneroService.obtener()` existe sin ruta.
- Los comentarios `CV-02`/`CV-03` del código están invertidos respecto de la KB: la KB define
  `CV-02 = precarga sólo en repository.py` y `CV-03 = paths exactos`.
- `tests/test_control_cambio_password.py:35-38` es un test con sólo `pass`.

Restricciones duras: no editar migraciones aplicadas (regla 9), no `create_all`, no `float` para dinero,
no token en el body, UoW en router/servicio como ya está, no commit/push, no tocar `despliegue/`.

## Goals / Non-Goals

**Goals:**

- Dejar el repo apto para iniciar C-20: los 2 FAIL cerrados, los mayores resueltos y la documentación
  alineada con lo que el código hace.
- Que cada corrección tenga una verificación ejecutable y una prueba que falle antes del cambio cuando
  hay comportamiento observable.
- No reabrir ni renumerar changes archivados; la historia se corrige con erratas explícitas.

**Non-Goals:**

- C-20 (imagen), C-21 (VPS), C-22 (zip), `despliegue/`, integrantes del README y autoevaluación.
- Reescribir filas históricas con timestamps congelados: falsearía la auditoría.
- Introducir unicidad de autor o cualquier regla de dominio que la consigna no pida.
- Cambiar la firma pública de los servicios más allá de completar el parámetro `usuario_actual` que ya
  existía.

## Decisions

### D-01 · `/mis-ventas` en un router propio sin prefijo

Se declara en `ventas/router.py` un segundo router:

```python
router_mis_ventas = APIRouter(tags=["ventas"])

@router_mis_ventas.get("/mis-ventas", response_model=Pagina[VentaRead])
async def mis_ventas(...): ...
```

y se monta en `main.py` dentro de `router_protegido`, después de `ventas_router`. El handler y
`service.mis_ventas` no cambian. **Alternativa descartada:** `APIRouter(prefix="/mis-ventas")` con
`@router.get("")`; también funciona, pero exige cuidar la barra final y el `redirect_slashes`. Un router
sin prefijo con el path completo es explícito y no compite con `/ventas/{venta_id}`.

`openapi.json` se usa como contrato: debe contener `/mis-ventas` y no `/ventas/mis-ventas`. Los tests que
hoy usan el path viejo se renombran; `test_cambio_password_api.py` conserva su intención (403 del control)
sólo cambiando la URL.

### D-02 · Migración 0005 nueva; modelos con `text("now()")`

Se crea una revisión nueva con `alembic revision -m "0005_now_server_defaults"` (sin autogenerate) y se
renombra el archivo a `<rev>_0005_now_server_defaults.py` para conservar la convención ordinal de
`0001`/`0002`. La revisión encadena desde `c8d2dea5529f` (0004) y ejecuta, para las cinco columnas:

```python
op.alter_column("asignacion_rol", "desde", server_default=sa.text("now()"), existing_type=sa.DateTime(timezone=True), existing_nullable=False)
```

El `downgrade` repite la forma histórica (`server_default="now()"` como cadena) para que el descenso deje
la base como la dejó 0003, con un comentario que advierte que esa forma vuelve a congelar el valor. No se
tocan 0001/0003. Los cinco modelos pasan a `server_default=text("now()")`
(`ventas/models.py` necesita importar `text`).

**Alternativas descartadas:** editar 0003 (prohibido por la regla 9 y rompería bases ya migradas); escribir
`cuando` explícito en todos los servicios (deja el `DEFAULT` trampa para cualquier escritura futura y no
corrige `venta.fecha`); usar `func.now()` en los modelos (SQLAlchemy lo renderiza distinto según el
dialecto y complica `alembic check`).

**Semántica de `now()`:** en PostgreSQL `now()` es el inicio de la transacción. Dos inserciones en la misma
transacción comparten el instante; por eso la prueba de comportamiento inserta en transacciones separadas
y, además, valida `pg_get_expr = now()` para las cinco columnas. La prueba no duerme un segundo: comprueba
que el valor insertado está próximo al reloj real (no un literal de noviembre de 2026) y que dos
transacciones separadas no comparten el mismo timestamp.

**Datos históricos:** la migración sólo cambia defaults; no hay `UPDATE`. Los `cuando` ya congelados se
conservan y se documenta en `tasks.md`/`CHANGES.md` que la corrección aplica a las escrituras nuevas.

### D-03 · Actor del movimiento: propagar y quitar el fallback

`crear_libro` y `reponer_libro` pasan `usuario_actual=_sesion.usuario` (la `IdentidadActual` envuelve el
`Usuario`; `_usuario_id` ya sabe leer `.id`). Se elimina el `select id from usuario limit 1`. Si un
servicio necesita escribir un movimiento y no recibe actor, responde `409` con un mensaje propio, igual
que la reposición ya hacía; así un error de cableado se ve en tests y nunca atribuye el movimiento a otra
cuenta. **Alternativa descartada:** dejar el fallback como red de seguridad; es justamente lo que la
auditoría señaló y produce evidencia falsa en el VPS.

La prueba usa dos administradores creados por la factory y afirma que el `usuario_id` es el segundo, sin
depender de que el seed tenga `admin2` con id 2.

### D-04 · Paginación estable de ventas del cliente

`ClienteRepository` gana `ventas_de_stmt(cliente_id)` que devuelve
`select(Venta).where(Venta.cliente_id == cliente_id).order_by(Venta.id)`, y `ventas_de` pagina ese
statement. Se elige `Venta.id` y no `fecha` porque el id es único y ya es el criterio de desempate del
listado general. La prueba compila el statement y exige `ORDER BY venta.id`; además hay una prueba de API
con tres ventas y dos páginas. **Alternativa descartada:** `fecha DESC, id DESC`; también es determinista,
pero cambia el orden visible del endpoint sin que la consigna lo pida.

### D-05 · C-06: retirar la promesa de 409 de autores, sin migración

Se elige la opción (b) del informe: `autor` no tiene unicidad de dominio y la consigna no la pide. Se
modifica la spec para acotar el 409 a editorial/género, se documenta en `autores/service.py` que la
traducción de `IntegrityError` queda como defensa ante constraints futuras y `PATCH /autores` sólo puede
devolver 404/422. **Alternativa descartada:** agregar `UNIQUE(nombre, nacionalidad)` con una migración
nueva; agrega una regla que la consigna no exige, puede chocar con datos existentes y suma riesgo a un
change correctivo.

`GET /generos/{genero_id}` se agrega como ruta pública en `router` (no en `router_admin`) con
`response_model=GeneroRead` y el 404 que ya produce `service.obtener`. La tabla de rutas de
`test_catalogo_protegido.py` se actualiza para incluirla.

### D-06 · `CV-02`/`CV-03`: la KB es la fuente de verdad

Se corrige el código, no la KB: `CV-02` = precarga sólo en `repository.py`; `CV-03` = paths exactos;
`CV-01` = router construye UoW, servicio lo abre, sólo `__aexit__` confirma. Los comentarios que hoy dicen
`CV-02` para `flush()`/`commit` pasan a `CV-01`, y los que dicen `CV-03` para precarga pasan a `CV-02`.
La cita de evidencia `import app.main` se corrige a `import main` con `PYTHONPATH=parcial`.

### D-07 · Mensajes de validación por tipo

`MENSAJES_POR_TIPO` agrega `bool_type → "Debe ser un valor booleano válido"` y
`float_type`/`decimal_parsing → "Debe ser un número válido"`; los tres tipos enteros conservan su texto.
La prueba de `test_errors_validation.py` se actualiza primero (RED) y luego se corrige el mapa (GREEN).
Se agrega el comentario `CV-08` en `autores`, `generos` y `libros` con el orden real de cada dominio.

### D-08 · C-14: prueba real y errata, sin reabrir el change

El test vacío se reemplaza por una prueba de integración: sin cookie, una ruta del grupo protegido (por
ejemplo `GET /clientes/1`) responde 401; con un usuario `debe_cambiar_password=true`, 403. La prueba
falla si se invierte el orden. La corrección de `tasks.md` archivado se hace como **errata** al final del
archivo (fecha, texto original, corrección), sin cambiar tareas ni el estado histórico. **Alternativa
descartada:** reabrir o reescribir el change archivado; rompería la trazabilidad y el pedido explícito.

### D-09 · C-15: reloj de aplicación documentado

`cerrar()` sigue usando `datetime.now(timezone.utc)` y su docstring pasa a decir «reloj de la aplicación en
UTC, igual que `abrir()`», en lugar de «default `now()` del servidor». Se descarta `func.now()` porque
asignaría una expresión SQL al atributo que el servicio devuelve en la respuesta (`revocar_rol` retorna la
asignación) y obligaría a un `refresh` dentro del UoW; el beneficio funcional es nulo (la vigencia se
decide con `now()` de PostgreSQL en las lecturas).

### D-10 · Barrido documental acotado

- `parcial/README.md`: paso 4 describe las cinco migraciones y el naming real; los integrantes siguen
  pendientes de C-22.
- `docs/CHECKLIST_ENTREGA.md`: §3 pasa de cuatro a cinco versiones, agrega la verificación de
  `pg_get_expr = now()` y el naming; §4 corrige el conteo de columnas de `asignacion_rol` (7, no 8) y la
  unicidad duplicada de `cliente.usuario_id`; §6.1 cambia el grep a
  `grep -n "roles_vigentes" app/core/dependencies.py` + `grep -n "AsignacionRol" app/modules/usuarios/repository.py`;
  §12 menciona las tres capturas críticas.
- `parcial/test/roles.http`: C-06.6 con `GET /mis-ventas` y encabezado reproducible de C-07.11.
- `parcial/test/EVIDENCIA.md`: filas C-06.6 y C-10 actualizadas; se copia
  `test/evidencia/c-10-backgroundtasks.txt` a `parcial/evidencia/`.
- `CHANGES.md`: entrada correctiva después de C-19, sin renumerar C-01…C-22.

## Risks / Trade-offs

- **[La migración 0005 corre sobre una base con datos]** → Sólo `ALTER COLUMN … SET DEFAULT`; no reescribe
  filas. Se prueba primero en una base temporal (`createdb`/`dropdb`) con `upgrade head`, `alembic check` y
  `pg_get_expr`, y recién después en la base de trabajo.
- **[El downgrade no es byte-a-byte igual a 0003]** → Restaura la forma de cadena que congela el valor y lo
  documenta; `alembic check` se exige limpio en head, no en una revisión intermedia. El round-trip
  `upgrade head → downgrade base → upgrade head` sigue siendo la prueba de reversibilidad.
- **[`now()` es el inicio de la transacción]** → La prueba de comportamiento usa transacciones separadas y
  complementa con `pg_get_expr`; no se promete unicidad de timestamps dentro de una misma transacción.
- **[Cambiar el path de `/mis-ventas` puede dejar evidencia vieja]** → Se actualizan tests, `.http`,
  `EVIDENCIA.md` y `openapi.json`; se agrega una prueba que verifica que el path viejo ya no existe.
- **[La prueba de atribución depende de ids del seed]** → Se crean dos administradores con la factory y se
  compara contra el id del actor autenticado, nunca contra `1`/`2` fijos.
- **[El barrido `CV-*` toca muchos archivos]** → Son comentarios y docstrings; se revisa con
  `grep -rn "CV-0[123]"` y se corre la suite completa para detectar cualquier cambio accidental.
- **[La errata del change archivado se confunde con una reapertura]** → Se agrega al final, fechada y
  firmada como errata; no se modifican tareas, estados ni checkboxes.

## Migration Plan

1. Crear una base temporal vacía, aplicar `alembic upgrade head` (incluye 0005) y verificar `pg_get_expr` y
   `alembic check`. Repetir `downgrade base → upgrade head`.
2. Aplicar `alembic upgrade head` en la base de trabajo; **no** reescribir datos. Verificar las cinco
   columnas con `psql`.
3. Ejecutar `python seed.py` y la query del invariante; luego `pytest -q`.
4. Re-ejecutar la evidencia `.http` afectada (C-06.6, C-07.11) y actualizar `EVIDENCIA.md`.
5. Rollback: `alembic downgrade -1` restaura los defaults históricos (con el comentario de advertencia); no
   hay pérdida de datos. Si se detecta un problema de aplicación, revertir el código mantiene la migración
   aplicada sin efectos sobre filas.

## UI Mockups

Decision: no (no UI)

El change no modifica pantallas, componentes, layout, estilos ni interacciones: es API, base de datos,
pruebas y documentación. No se crean mockups ni se requiere la aprobación del design system.

## Open Questions

Ninguna que cambie las specs, el enfoque o las tareas. Los integrantes del README y el zip quedan
explícitamente para C-22.
