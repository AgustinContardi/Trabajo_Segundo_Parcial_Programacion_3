# Design — C-17 seed-libreria

## Context

Ver `proposal.md` (motivación) y `specs/datos-iniciales/spec.md` (contrato observable). Estado real del
repo que condiciona el diseño:

- `parcial/seed.py` **existe** pero es el seed heredado del TP cap. 1-4: crea `Libro(stock=N)` directo
  (viola `RN-11`), no conoce `usuario`, `asignacion_rol`, `evento_seguridad` ni `movimiento_stock`, limpia
  con `DELETE` (lo que el disparador rechaza) y el archivo está en una codificación corrupta (`EmecǸ`,
  `Poes��a`). El estado que importa no es «no hay seed», es «hay un seed que ya no puede correr contra el
  esquema del parcial».
- `migrations/versions/` tiene exactamente cuatro revisiones (`0001`, `0002`, `dd4a0e5e9cf7` = 0003,
  `c8d2dea5529f` = 0004). La `0004` crea `trg_movimiento_stock_no_modificable` como
  `BEFORE UPDATE OR DELETE … FOR EACH ROW`: **`TRUNCATE` no lo dispara**, `DELETE` sí.
- `LibroRepository.aplicar_movimiento(libro, cantidad, motivo, usuario_id, venta_id=None)` es el punto único
  de escritura de stock (`libro.stock += cantidad` + `MovimientoStock` + `flush()`), y
  `VentasService.registrar_venta` lo usa con `motivo='Venta'` y `cantidad` negativa.
- `MovimientoStock.usuario_id` es **NOT NULL** (FK a `usuario`), así que ningún movimiento puede existir
  antes de los usuarios.
- `Venta` tiene sólo `id, cliente_id, fecha, total`: `SU-07` quedó confirmado en
  `docs/BASELINE_TP_CAP1a4.md`. No hay columna de vendedor.
- `hash_password(password, *, rounds, semaphore)` es `async` (bcrypt en `to_thread` bajo semáforo) y
  `validar_password_bytes` sólo impone el tope de 72 bytes.
- Repositorios disponibles: `UsuarioRepository`, `AsignacionRolRepository` (con `abrir(usuario_id, rol, …)`),
  `EventoSeguridadRepository`, `EditorialRepository`, `GeneroRepository`, `AutorRepository`,
  `LibroRepository`, `ClienteRepository` (con `add_perfil`), `VentaRepository`, `RenglonVentaRepository`.
  Todos hacen `flush()` y nunca `commit()`.
- `crear_engine(settings)` y `crear_sessionmaker(engine)` existen en `app/core/database.py` y no crean nada
  al importar.

Restricciones que el diseño respeta: rutas exactas de la consigna (`seed.py` en la raíz de `parcial/`, §1);
`RN-11`/`RN-12` (stock sólo por movimientos, movimientos de sólo agregado); `CV-11` (idempotencia);
`CV-14` (sin `create_all`); nada de `despliegue/`; sin migraciones nuevas (exactamente cuatro).

## Goals / Non-Goals

**Goals:**

- Dejar `parcial/seed.py` como la puesta en marcha real del proyecto: `python seed.py` después de
  `alembic upgrade head` produce, sin error y de forma repetible, el estado que asumen los 16 casos `.http`.
- Que todo el stock del seed nazca del punto único de C-08, con el invariante global en 0 filas.
- Que el propio script verifique el resultado y falle ruidosamente si no cuadra, para que la evidencia
  (§4 y §8) sea el propio exit code más los `SELECT`.
- Poder probar los datos del seed sin base (`tests/test_seed_datos.py`) y, opcionalmente, la ejecución real.

**Non-Goals:**

- No agregar `venta.usuario_id` ni ninguna columna: `SU-07` está confirmado y `venta` es «heredada, sin
  cambios de esquema».
- No cambiar contratos de API, servicios ni routers: el seed escribe con repositorios, no por HTTP.
- No tocar `despliegue/` (conserva la copia intacta del TP) ni `migrations/`.
- No cargar datos «de ejemplo» distintos de los del PDF/TP: el checklist heredado (estados, consumibles,
  «Laura», «Jorge») queda descartado por IN-07.
- No llenar `intento_acceso`: el seed deja esa tabla vacía para que C-05 cuente desde cero.

## Decisions

### 1. Reescribir `parcial/seed.py`, no crear un script nuevo

La consigna exige `seed.py` en la raíz de `parcial/` (§1) y `python seed.py` en la puesta en marcha (§12).
Un `scripts/seed.py` alternativo obligaría a un shim que no está en la estructura. **Alternativa
descartada**: adaptar el heredado línea por línea — arrastra la codificación rota y la forma de limpiar que
el disparador rechaza; el reemplazo es más simple y verificable.

### 2. `SeedUnitOfWork` local al script, construido por el script y abierto una sola vez

`seed.py` define un `SeedUnitOfWork(UnitOfWork)` que compone, sobre **la misma sesión**, los repositorios de
usuarios, roles, eventos, editoriales, géneros, autores, libros, clientes, ventas y renglones. El script
hace de *composition root* —el mismo papel que cumple el router con `Depends`— y abre la transacción con
`async with`; sólo el `__aexit__` confirma. Se respeta el espíritu de `CV-01`: ni el servicio ni la lógica
de carga construyen el UoW, y ningún repositorio hace `commit()`.

**Alternativas descartadas**: (a) llamar a los servicios de cada módulo —dependen de `IdentidadActual`,
`BackgroundTasks` y del mapeo de errores HTTP, y obligarían a simular una petición para sembrar datos—;
(b) `INSERT` por SQL crudo —saltearía `aplicar_movimiento` y con él `RN-11`, y el invariante quedaría a
cargo de la memoria de quien escribe el SQL—; (c) varios `async with` por bloque —el seed dejaría de ser
atómico: un fallo en la venta dejaría catálogo y usuarios cargados a medias.

### 3. Limpiar con `TRUNCATE` explícito y `RESTART IDENTITY CASCADE`

Se vacían las 14 tablas de dominio en un solo `TRUNCATE TABLE …, …, … RESTART IDENTITY CASCADE`, sin
mencionar `alembic_version`. Motivos: `DELETE` sobre `movimiento_stock` lo rechaza la función de `RN-12`
(la de `0004` es `BEFORE UPDATE OR DELETE FOR EACH ROW`, no un trigger de `TRUNCATE`); `RESTART IDENTITY`
garantiza que la venta 1 sea `1` y los libros `1…5` en **cada** corrida, que es de lo que dependen los
`.http` de C-18; y `alembic_version` no se toca para no fingir una base sin migrar.

**Alternativas descartadas**: `DELETE` ordenado por FKs —imposible por el disparador—; `DROP SCHEMA` +
`CREATE SCHEMA` —borraría el historial de Alembic y obligaría a migrar en cada seed—; `TRUNCATE` sin
`RESTART IDENTITY` —ids crecientes entre corridas y `.http` frágiles.

### 4. El stock se carga con `aplicar_movimiento`, nunca asignando `libro.stock`

Cada libro se crea con `stock = 0` y el stock inicial entra como movimiento `'Stock inicial'` con
`usuario_id` del `admin`: `+11` Rayuela, `+10` Ficciones, `+5` Antología, `+3` Respiración artificial y
`+1` Bestiario. Luego la venta 1 aplica `−1` y `−2` con `motivo='Venta'` y `venta_id=1`. Los valores finales
salen de la aritmética (`11−1=10`, `10−2=8`), no de una constante: si alguien cambia una cantidad, el
invariante del seed falla en vez de mentir.

**Por qué así**: `RN-11` prohíbe escribir `stock` por fuera del punto único y `RN-12` prohíbe corregirlo
después; un seed que asigna `stock` directo rompe el invariante desde el primer minuto y hace fallar los
casos de venta. **Alternativa descartada**: `Libro(stock=N)` (lo que hace el seed heredado) —viola ambas
reglas y es exactamente el defecto que este change corrige.

### 5. El vendedor de la venta 1 se registra en `movimiento_stock.usuario_id`

`venta` no tiene columna de vendedor (`SU-07` confirmado, `docs/BASELINE_TP_CAP1a4.md`), así que «registrada
por `vendedor@example.com`» se cumple donde el modelo lo permite: las dos salidas de la venta llevan el
`usuario_id` del vendedor, igual que hace `POST /ventas` en C-16. Los movimientos de «Stock inicial» llevan
el `usuario_id` del `admin`, porque la columna es NOT NULL y el cargador es el administrador. El docstring
del seed deja escrita la limitación para que nadie la lea como un olvido.

**Alternativa descartada**: agregar `venta.usuario_id` con una migración `0005` —cambia el esquema heredado,
obliga a reabrir C-04 y contradice «`venta` heredada, sin cambios de esquema»—.

### 6. Hash bcrypt real, calculado antes de abrir la transacción

Las cinco contraseñas ficticias se hashean con `hash_password(..., rounds=settings.BCRYPT_ROUNDS,
semaphore=asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY))` **antes** del `async with`, igual que el
auto-registro (`RN-02`) y el alta de personal (`C-15`): bcrypt nunca dentro del bucle de eventos ni dentro
de la transacción. Los valores de las contraseñas viven sólo en `seed.py` y se listan en su docstring para
que C-18 los use.

**Alternativa descartada**: poner un hash fijo precalculado en el archivo —se desincroniza si cambia
`BCRYPT_ROUNDS` y deja de demostrar que el login funciona con el costo real—.

### 7. Verificación final dentro del script, con exit code

Tras el commit, el script corre en la misma sesión: (a) la query del invariante de §4, que debe dar 0 filas;
(b) conteos de `usuario` 5, `asignacion_rol` 5, `editorial` 3, `genero` 3, `autor` 6, `libro` 5,
`cliente` 3, `perfil_cliente` 1, `venta` 1, `renglon_venta` 2, `movimiento_stock` 7, `evento_seguridad` 1;
(c) `venta.id = 1` y `total = 69000.00`; (d) un resumen impreso por pantalla. Si algo no cuadra, imprime el
detalle y termina con `exit 1`.

Esto convierte la Aceptación (§4 y §8) en un artefacto ejecutable: la evidencia es la salida del script más
los `SELECT` que el checklist pide literalmente.

### 8. Datos en constantes de módulo y ejecución opcional en la suite

`seed.py` declara las listas de datos (`USUARIOS`, `EDITORIALES`, `GENEROS`, `AUTORES`, `LIBROS`,
`AUTORIAS`, `CLIENTES`, `RENGLONES_VENTA`) y las funciones `vaciar(session)`, `cargar(uow, …)` y
`verificar(session)`, con `main()` sólo bajo `if __name__ == "__main__"`. Importar el módulo no exige
entorno: no se llama `get_settings()` al importar.

`parcial/tests/test_seed_datos.py` prueba la coherencia de esas constantes sin base (conteos, stocks
esperados, total `69000.00`, que las cantidades de venta no superen el stock inicial, que los roles sean los
cinco del PDF). La ejecución real contra PostgreSQL —que **trunca** la base de desarrollo— queda en un test
separado, saltado por defecto salvo que se exporte `SEED_E2E=1`, para no destruir datos de la suite mientras
corre. La evidencia oficial sigue siendo `python seed.py` dos veces.

## Risks / Trade-offs

- **[El seed apunta a la base de `Settings` y la vacía]** → Mitigación: el script imprime host, puerto y
  base destino antes de truncar (nunca la contraseña), y el README/§12 ya indican que el seed es parte de la
  puesta en marcha local. No se agrega una confirmación interactiva porque `python seed.py` debe correr sin
  intervención en la carpeta limpia.
- **[Ids estables dependen de `RESTART IDENTITY`]** → Si otra persona trunca sin reiniciar identidades, los
  `.http` fallan con datos que «parecen» correctos. Mitigación: la verificación del script exige `venta.id = 1`
  y cuenta las filas; si no, exit code distinto de cero.
- **[Cinco bcrypt de costo 12 agregan ~1–2 s]** → Aceptable para un script de puesta en marcha; se hace con
  un solo semáforo y fuera de la transacción para no estirar el bloque de escritura.
- **[`TRUNCATE … CASCADE` es más amplio que la lista]** → Se enumera explícitamente las 14 tablas y se deja
  `CASCADE` sólo para que las FKs no bloqueen; `alembic_version` no está en la lista y no tiene FK desde
  ninguna tabla de dominio.
- **[`CASCADE` sobre `usuario` arrastra `cliente` y `movimiento_stock`]** → Es lo deseado: la limpieza tiene
  que ser total para que el resultado sea idéntico entre corridas; el orden de carga posterior repone todo.
- **[Un cambio de datos del PDF obliga a tocar constantes y tests]** → Mitigación: la verificación final y
  `test_seed_datos.py` fallan a la vez, señalando el dato desalineado en vez de dejar la base a medias.

## Migration Plan

1. Reemplazar `parcial/seed.py` (no hay migración de esquema ni de datos: el seed es la carga, no un
   upgrade).
2. Sobre una base local ya migrada: `python seed.py` → verificación verde; `python seed.py` otra vez →
   mismo estado.
3. Si hiciera falta revertir: `git checkout -- parcial/seed.py` recupera el heredado; la base se reconstruye
   con `alembic downgrade base && alembic upgrade head` y el seed anterior/anterior commit.

## Open Questions

- El literal exacto de `evento_seguridad.accion` («Carga de los datos iniciales») podría ajustarse si la
  corrección compara el texto. Se puede cambiar en un solo lugar (`ACCION_SEED`) sin tocar el resto del
  diseño ni las tareas.
