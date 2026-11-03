# Visión y Objetivos

> Fuente autoritativa: `docs/Parcial_Cap1a6_Consigna.pdf` (24 páginas), materia Programación III,
> «UNIDAD 1 A 6 · DEL OBJETO A LA TRANSACCIÓN». Este documento resume la consigna; ante cualquier
> duda, gana el PDF.

## Propósito del sistema

La librería —ya construida en el TP de los capítulos 1 a 4 con su catálogo, sus clientes y sus
ventas— abre el sistema a su personal y a sus clientes: un administrador mantiene el catálogo,
repone el stock y administra al personal y sus roles; un vendedor registra las ventas y atiende el
mostrador; los clientes se registran solos en la web y consultan sus compras. El catálogo de libros
es público y se puede ver sin iniciar sesión.

El parcial lleva el proyecto hasta el capítulo 6 y agrega, aparte, el despliegue en el VPS del TP de
los capítulos 1 a 4 dentro de un contenedor. El objetivo de fondo es demostrar que el grupo sabe
reorganizar una API asincrónica en capas, evolucionar un esquema versionado con Alembic, autenticar
con bcrypt y cookie HttpOnly, autorizar consultando la base en cada petición, agrupar las escrituras
de una operación en una sola transacción, delegar en la base las garantías que la base puede dar, y
empaquetar y poner en línea el trabajo anterior sin filtrar secretos.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Visitante (sin sesión) | Consultar el catálogo de libros | Buscar por título, filtrar por género, ver el detalle de un libro, registrarse |
| CLIENTE | Registrarse solo y consultar sus compras | Ver `/mis-ventas`, ver el detalle de sus propias ventas, cambiar su contraseña |
| VENDEDOR | Registrar ventas en el mostrador | Dar de alta clientes y sus perfiles, ver ventas y clientes, consultar el catálogo |
| ADMIN | Administrar catálogo, stock y personal | Alta de libros con stock inicial, reposición, baja lógica, asignar y revocar roles con vigencia, ver el historial de seguridad (`GET /eventos`) |
| SISTEMA (actor textual) | Dejar rastro de las operaciones sensibles | Escribir `evento_seguridad` con `actor = 'SISTEMA'` en el seed y en las operaciones sin usuario humano |

## Objetivos técnicos (los 7 que la consigna pide demostrar)

1. Reorganizar la API en capas **Router → Service → UoW → Repository → Model**, donde cada capa sabe
   lo suyo y nada más.
2. Evolucionar el esquema con Alembic: una migración autogenerada **leída antes de aplicarla** y otra
   **escrita a mano** para lo que la comparación automática no ve (funciones y disparadores).
3. Autenticar con contraseñas guardadas con **bcrypt** y un token en una **cookie HttpOnly**, sin
   frenar el servidor y sin revelar qué cuentas existen.
4. Autorizar consultando los roles **en la base en cada petición**, con vigencia, y distinguir
   siempre entre **401 y 403**.
5. Agrupar en **una sola transacción** las escrituras de una operación de negocio, de modo que un
   fallo en el medio no deje datos a medias.
6. Delegar en la base las garantías que la base puede dar: unicidad entre los vigentes, claves
   foráneas, comprobaciones (`CHECK`) y el sólo agregado.
7. Empaquetar el TP de los capítulos 1 a 4 en una imagen de Docker y ponerlo en línea en el VPS con
   una configuración que no filtra secretos ni expone lo que no debe.

## Alcance de esta entrega (capítulos 5 y 6 + despliegue)

**Sobre el proyecto ampliado (`parcial/`):**

- Tablas nuevas `usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad` y módulo `usuarios`.
- `cliente.usuario_id` nulo permitido y UNIQUE: un cliente puede tener, o no, acceso por la web.
- `libro.borrado_en` (borrado lógico) y el ISBN único **entre los vigentes** (índice único parcial).
- `movimiento_stock`, de sólo agregado; el stock deja de editarse por `PATCH` y cambia con el alta,
  la reposición y las ventas.
- Registro de venta que descuenta stock y deja un movimiento por renglón, todo en una transacción.
- Todos los módulos pasan a **repositorios + Unit of Work**; los servicios dejan de recibir la sesión.
- `Settings` con pydantic-settings, **sin secretos por defecto**.
- Listados con el envoltorio `{items, total, page, size, pages}` en lugar de `limit`/`offset`.
- Dos migraciones nuevas: la tercera autogenerada y la cuarta escrita a mano (disparador).
- `GET /health/live` y `GET /health/ready`.
- Aviso simulado del comprobante con `BackgroundTasks` (`asyncio.sleep(0.5)` + línea de registro).
- Archivos `.http` en `test/` para los casos C-01…C-16 y `test/solo_agregado.sql` para C-14.

**Sobre el despliegue (`despliegue/`), que es un proyecto distinto:**

- El TP de los capítulos 1 a 4 **tal como se entregó**, sin ninguna de las modificaciones de arriba.
- `Dockerfile` + `.dockerignore`, imagen base `python:3.12-alpine`, usuario sin privilegios,
  migraciones al arrancar, `HEALTHCHECK` sobre `/health/ready`, `docker run` con `--env-file`.
- `DEPLOY.md` con URL pública, fecha y hora, comandos completos y procedimiento de actualización.
- `evidencia/` con la salida de los casos D-01…D-08.

## Fuera de alcance (explícito en la consigna)

- **Concurrencia (capítulo 7).** Dos ventas del último ejemplar registradas al mismo tiempo pueden
  leer las dos `stock = 1`, darlo las dos por suficiente y escribir las dos `0`: el segundo descuento
  pisa al primero y la librería vende un ejemplar que no tenía, sin que el stock llegue a ser
  negativo (el `CHECK` lo impediría). Es una actualización perdida; el bloqueo que la evita es tema
  de la próxima clase. **No se evalúa.**
- **Colas de tareas con Redis (capítulo 8).** El aviso al cliente se resuelve con `BackgroundTasks`,
  que corre en el mismo proceso. Si el proceso se reinicia, el aviso se pierde y nadie lo reintenta;
  se acepta porque el aviso es simulado.
- **Docker Compose.** La base de datos no forma parte del paquete: el servidor ya tiene PostgreSQL.
- **Un segundo rol de base de datos** para reforzar el sólo agregado (mecanismo alternativo de la
  sección 6.9): no se pide, el parcial usa un solo rol de base.
- **Interfaz gráfica propia.** No hay pantallas ni frontend en la consigna; el catálogo «público» se
  consume por HTTP.
- **Modificar ventas.** No hay `PATCH` de ventas (`RN-09`).

## Métricas de éxito

| Métrica | Criterio verificable |
|---|---|
| Proyecto levanta limpio | `alembic upgrade head` sobre base vacía, `downgrade base`, `upgrade head` otra vez; `python seed.py`; servidor arriba |
| Casos C | C-01…C-16 corridos literalmente con los `.http` de `test/`, con la respuesta esperada en un comentario |
| Casos D | D-01…D-08 con salida guardada en `despliegue/evidencia/` |
| Integridad del stock | Invariante `libro.stock = SUM(movimiento_stock.cantidad)` verificada después de cada caso de venta |
| Aislamiento por rol | Un vendedor que crea un libro recibe 403; un cliente ve su venta (200) y no la ajena (403) |
| Despliegue en línea | El TP cap 1-4 accesible desde afuera en la URL declarada en `DEPLOY.md` hasta que se publiquen las notas |
| Rúbrica | 100 puntos repartidos en 10 criterios (ver `11_despliegue_y_devops.md` para el desglose de despliegue) |
