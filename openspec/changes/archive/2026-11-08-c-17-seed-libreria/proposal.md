# Proposal — C-17 seed-libreria

## Why

La API ya tiene catálogo, clientes, ventas transaccionales, acceso con roles y auditoría, pero el único
seed del repo es el heredado del TP cap. 1-4 (`parcial/seed.py`): escribe `libro.stock` directo (viola
`RN-11`), no conoce usuarios, roles ni `movimiento_stock`, borra con `DELETE` sobre una tabla que el
disparador de `RN-12` rechaza, arrastra la codificación corrupta del baseline y no está pensado para ser
idempotente. Los 16 casos `.http` de C-18 asumen ids, totales y stocks concretos —venta 1 = `69000.00`,
libros con stock `10/5/8/3/1`, usuarios `admin`/`admin2`/`vendedor`/`ana`/`nuevo`—, así que sin este
change los casos no se pueden ni escribir. El seed **es parte de la puesta en marcha** del proyecto, no
un extra de prueba (consigna p. 19-20, IN-07).

## What Changes

- Reemplazar `parcial/seed.py` por el seed de la librería del PDF, no el del checklist heredado (IN-07):
  5 usuarios con sus roles, 3 editoriales, 3 géneros, 6 autores, 5 libros, 3 clientes, la venta 1, sus
  movimientos de stock y una línea de `evento_seguridad` con `actor = 'SISTEMA'`.
- Vaciar antes de cargar con **`TRUNCATE … RESTART IDENTITY CASCADE`** sobre una lista explícita de las 14
  tablas de dominio (nunca `alembic_version`). Un `DELETE` sobre `movimiento_stock` lo rechaza el
  disparador de `RN-12`; `RESTART IDENTITY` es lo que hace que la venta 1 sea la 1 y los libros 1…5 en
  cada corrida, que es lo que los `.http` asumen.
- Cargar todo el stock por el **punto único** de C-08 (`LibroRepository.aplicar_movimiento`), con motivo
  `'Stock inicial'`: Rayuela **+11**, Ficciones **+10**, Antología **+5**, Respiración artificial **+3**,
  Bestiario **+1**; y las salidas de la venta **−1** y **−2** con `usuario_id` del vendedor.
- Hashear las cinco contraseñas con `app.core.security.hash_password` (`to_thread` + semáforo, costo de
  `Settings`) **antes** de abrir la transacción, igual que `RN-02`; las contraseñas son de mentira y viven
  sólo en `seed.py`.
- Escribir el seed completo en **un solo** `async with` y confirmar sólo en el `__aexit__`; el script es el
  *composition root* (lo que el router es para una petición), el servicio/UoW no se construye dentro de la
  lógica.
- Verificación final dentro del propio script: la query del invariante
  `libro.stock = SUM(movimiento_stock.cantidad)` debe dar **0 filas** en los cinco libros, más los conteos
  y el total de la venta 1. Si no cuadra, el script termina con código distinto de cero y un mensaje propio.
- Idempotencia (`CV-11`): correr `python seed.py` dos veces deja exactamente el mismo estado.
- Reemplazar el archivo heredado con codificación corrupta por uno en UTF-8 con los acentos correctos.
- Pruebas: `parcial/tests/test_seed_datos.py` con los datos puros (conteos, stocks, total, coherencia del
  invariante aritmético) y una verificación de ejecución real contra PostgreSQL, marcada como opcional para
  no truncar la base durante la suite.

## Capabilities

### New Capabilities

- `datos-iniciales`: el conjunto de datos de arranque que el proyecto debe poder cargar de forma
  reproducible, idempotente y coherente con `RN-11`/`RN-12`, con usuarios y roles, catálogo, clientes, la
  venta 1 y el registro de seguridad del sistema.

### Modified Capabilities

Ninguna. El seed no cambia contratos de API, esquema ni reglas de negocio: cumple las que ya existen.

## Impact

- **Producción**: sólo `parcial/seed.py` (reescrito). No se toca `app/`, `main.py` ni `migrations/`.
- **Reutiliza** `app/core/config.py` (`get_settings`), `app/core/database.py` (`crear_engine`,
  `crear_sessionmaker`), `app/core/security.py` (`hash_password`), `app/core/unit_of_work.py` (`UnitOfWork`),
  `LibroRepository.aplicar_movimiento`, `EventoSeguridadRepository.add`, `ClienteRepository.add_perfil` y los
  repositorios de catálogo (`EditorialRepository`, `GeneroRepository`, `AutorRepository`).
- **Sin migraciones y sin cambios de esquema**: las tablas, los índices parciales y el disparador ya existen
  desde C-03/C-04/C-16. El seed corre **después** de `alembic upgrade head`.
- **Decisiones heredadas que el seed respeta**: `SU-07` está confirmado en `docs/BASELINE_TP_CAP1a4.md` —
  `venta` tiene sólo `id, cliente_id, fecha, total`, así que «registrada por `vendedor@example.com`» se
  expresa donde el modelo lo permite: `movimiento_stock.usuario_id` de las salidas de la venta. Los precios
  de Respiración artificial (`27000.00`) y Bestiario (`18000.00`), que la KB dejaba «a confirmar contra el
  repo», quedan confirmados con el seed del TP que ya está en `parcial/`.
- **Pruebas y evidencia**: `parcial/tests/test_seed_datos.py` (nuevo) y la evidencia manual que exige la
  Aceptación (`python seed.py` dos veces + `SELECT` de usuarios/roles, libros/stocks, clientes, venta total,
  `evento_seguridad` y la query del invariante).
- **Habilita** C-18 (los `.http` se corren después de cada `python seed.py`) y C-19 (suite + evidencia).
  No toca `despliegue/`, que conserva su copia intacta del TP.
- **Dependencias ya cumplidas**: C-09 (baja/reposición y movimientos), C-15 (usuarios, roles y eventos),
  C-16 (venta transaccional y punto único de stock).
