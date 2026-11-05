# Reglas de Negocio

> **Estas 16 reglas están transcriptas de la consigna** (p. 6-8) y se citan textualmente porque la
> corrección usa los números. «Las reglas de esta tabla se numeran de nuevo y **reemplazan a las del
> TP en lo que se superponen**».
>
> Los códigos `RN-NN` son de la consigna y **no se redefinen**. Todo lo que no está en la consigna
> vive en otro espacio de nombres: `CV-NN` (convención de ingeniería, ver `docs/CHECKLIST...`) y
> `RD-NN` (regla de diseño propia, **no está en la consigna**).

## Resumen

| Regla | Enunciado (textual) | Garante esperado | Caso |
|---|---|---|---|
| RN-01 | El correo de un usuario, el de un cliente, el nombre de una editorial y el de un género son únicos. El ISBN de un libro es único entre los que no están dados de baja. | UNIQUE e índice único parcial en la base; 409 con mensaje propio | C-02, C-13 |
| RN-02 | El auto-registro crea el usuario, su rol CLIENTE y su ficha de cliente: o quedan las tres filas, o ninguna. Si ya existe un cliente con ese correo, el registro da 409 y no se apropia de esa ficha. | Un solo Unit of Work | C-02 |
| RN-03 | Un usuario tiene a lo sumo una asignación abierta por rol. | Índice único parcial; 409 | C-07 |
| RN-04 | Los permisos se deciden con los roles vigentes en la base, en cada petición. Los roles que trae el token son informativos. | Dependencia que consulta `asignacion_rol` | C-06, C-07 |
| RN-05 | Un administrador no puede revocarse su propio rol ADMIN, y el sistema nunca queda sin administradores vigentes. | Comprobación en el servicio; 409 | C-08 |
| RN-06 | Mientras un usuario tenga el cambio de contraseña pendiente, sólo puede usar las rutas de `/auth` y las que no piden sesión. | Dos grupos de rutas; 403 | C-09 |
| RN-07 | Después de 5 intentos fallidos con el mismo correo desde la misma dirección en 60 segundos, el login responde 429 sin verificar la contraseña. Un login correcto reinicia la cuenta: los fallos anteriores siguen en la tabla, pero dejan de contar. | Conteo sobre `intento_acceso`; `Retry-After` | C-05 |
| RN-08 | El login responde lo mismo, y tarda lo mismo, exista o no el correo. | Mismo mensaje; verificación contra un hash ficticio | C-04 |
| RN-09 | Una venta nace con sus renglones (al menos uno, sin libros repetidos), con el precio de cada renglón copiado del libro y el total calculado por el servidor. Las ventas no se modifican. | DTO; el precio y el total nunca viajan en el cuerpo; no hay PATCH | C-10, C-16 |
| RN-10 | Registrar una venta descuenta el stock de cada libro y deja un movimiento por renglón. Si un libro no alcanza, no queda ninguna de esas escrituras: ni la venta, ni los renglones, ni los descuentos, ni los movimientos. | Un solo Unit of Work; 409 | C-11, C-12 |
| RN-11 | El stock de un libro sólo cambia a través de movimientos: el alta con stock inicial, la reposición y la venta. No se edita por PATCH. | Punto único de escritura de stock | C-13, C-16 |
| RN-12 | `movimiento_stock` es de sólo agregado: nadie puede modificar ni borrar sus filas. | Disparador en la base, instalado por migración | C-14 |
| RN-13 | Un libro dado de baja deja de aparecer en el catálogo y no se puede vender ni reponer, pero sus datos se conservan y las ventas anteriores lo siguen mostrando. | Borrado lógico; 409 | C-12, C-13 |
| RN-14 | Lo propio sólo pide estar autenticado: un cliente ve sus ventas y ninguna otra. | `/mis-ventas` y comprobación de dueño; 403 | C-06 |
| RN-15 | Ningún error devuelve al cliente texto interno de la base, que le entregaría el mapa del esquema. Ninguna entrada inválida termina en un 500. | Traducción del `IntegrityError`; validación en el contrato | C-01, C-02, C-16 |
| RN-16 | Cada alta de personal, cambio de rol y cambio de contraseña deja una línea en `evento_seguridad`, en la misma transacción que el cambio. | Un solo Unit of Work | C-07, C-09 |

## Detalle por regla

### RN-01 — Unicidad

- Cuatro unicidades de negocio: `usuario.email`, `cliente.email`, `editorial.nombre`, `genero.nombre`.
- Más una **unicidad condicionada**: `libro.isbn` único **sólo entre los vigentes**
  (`WHERE borrado_en IS NULL`).
- **La garantiza la base**, no una consulta previa: «Unicidad garantizada por la base; no se verifica
  con una consulta previa» (requisitos no funcionales).
- El servicio traduce el `IntegrityError` de unicidad a **409 con mensaje propio** («Ya existe un
  libro con ese ISBN», «Ya existe una editorial con ese nombre»), nunca al texto de PostgreSQL
  (RN-15).
- Reusar el ISBN de un libro dado de baja es **válido** y da **201**; un segundo libro **vigente**
  con ese ISBN da **409** (C-13).

### RN-02 — Auto-registro atómico

- Tres escrituras: fila en `usuario`, fila en `asignacion_rol` con `rol = 'CLIENTE'`, fila en
  `cliente` con `usuario_id` apuntando al usuario nuevo.
- **Un solo `async with uow`**: o quedan las tres, o ninguna. Un fallo en la tercera revierte las dos
  anteriores.
- El rol **no viaja en el cuerpo**: el contrato de entrada tiene `extra="forbid"`, así que mandar
  `rol` da **422**.
- Si ya existe un **cliente** con ese correo → **409**, y **no se apropia de esa ficha** (no setea
  `usuario_id` sobre el cliente existente). Si ya existe un **usuario** con ese correo → **409**.
- El alta de personal (`POST /usuarios`, ADMIN) es distinta: crea usuario + rol, **no** crea ficha de
  cliente.

### RN-03 — Una asignación abierta por rol

- Índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL`.
- Intentar abrir una segunda asignación del mismo rol sin cerrar la anterior → **409**.
- **Reasignar un rol vencido** es válido: el servicio cierra la fila anterior (escribe `revocada_en`)
  y abre una nueva, en la misma transacción.
- Revocar y volver a asignar el mismo rol también funciona: la fila revocada ya no participa del
  índice parcial.

### RN-04 — Los roles se leen de la base en cada petición

- `requiere_rol` **no** confía en el claim `roles` del token: consulta `asignacion_rol` con la misma
  sesión del Unit of Work.
- El claim del token es **información**, y `GET /auth/yo` lo devuelve junto con los roles vigentes
  para que la diferencia se vea (C-07).
- Consecuencia buscada: **revocar un rol le quita el permiso a una sesión ya abierta**, sin esperar a
  que el token venza.
- También se aplica el **vencimiento**: una asignación con `vence_en <= now()` no otorga permiso
  aunque el token diga lo contrario.

### RN-05 — Autoprotección del administrador

- Un ADMIN **no puede revocarse su propio rol ADMIN** → **409**.
- El sistema **nunca queda sin administradores vigentes**: revocar el último ADMIN vigente → **409**,
  aun cuando lo haga otro administrador.
- Es «comprobación en el servicio» (no hay restricción de base que lo pueda expresar sin un
  disparador). El índice parcial de RN-03 no cubre esto.
- Ojo con el orden: la comprobación corre **después** de saber quién pide y **antes** de escribir
  `revocada_en`.

### RN-06 — Cambio obligatorio de contraseña

- Con `usuario.debe_cambiar_password = true`, el usuario **sólo** puede usar:
  - las rutas de `/auth` (incluida `POST /auth/cambiar-password`, que es la salida), y
  - las que **no piden sesión** (catálogo público, health, login, registro, logout).
- Cualquier ruta del grupo protegido → **403**.
- Se implementa con **dos grupos de rutas en `main.py`**, con el control montado **una sola vez** en
  el protegido. FastAPI suma dependencias y no las resta: por eso `/auth/cambiar-password` vive en el
  grupo abierto.
- Tras el cambio, `debe_cambiar_password` queda en `false` y **la misma cookie sirve** para las rutas
  protegidas (200), sin iniciar sesión de nuevo (C-09).

### RN-07 — Límite de intentos

- Ventana: **60 segundos**, contada sobre `intento_acceso` con
  `email = :email AND ip = :ip AND cuando > now() - 60s AND exito = false`.
- Umbral: **5 intentos fallidos**. El **sexto** responde **429** con `Retry-After`.
- El 429 se decide **antes de verificar la contraseña** y **sin calcular ningún hash**: «cuesta una
  consulta» y el caso C-05 exige que responda **en pocos milisegundos**.
- **Un login correcto reinicia la cuenta**: los fallos anteriores **siguen en la tabla** (no se
  borran) pero **dejan de contar**. El conteo mira sólo los fallos posteriores al último éxito.
- La fila del intento se escribe **siempre**, incluso cuando la petición termina en 401, 429 o
  revienta: ver `07_flujos_principales.md`, flujo 2.
- El umbral y la ventana salen de `Settings` (`LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`) — los
  nombres de las variables son convención (`CV-09`), los valores 5 y 60 son de la consigna.

### RN-08 — No revelar qué cuentas existen

- **Mismo cuerpo** y **mismo tiempo** con correo existente y con correo inexistente.
- Mecanismo: si el correo no existe, se verifica igual contra un **hash ficticio** calculado **una
  vez en el lifespan** (no por petición).
- C-04 mide que las dos respuestas tarden parecido: el hash ficticio debe tener el **mismo costo**
  bcrypt que uno real.

### RN-09 — La venta nace completa

- Al menos **un renglón**; **sin libros repetidos** en la misma venta.
- **Precio copiado del libro** al momento de registrar (`renglon_venta.precio_unitario`).
- **Total calculado por el servidor** = Σ (cantidad × precio copiado).
- **El precio y el total nunca viajan en el cuerpo**: el DTO de entrada sólo acepta `cliente_id` y
  `renglones: [{libro_id, cantidad}]`; mandar `precio` o `total` da **422** (`extra="forbid"`).
- **No hay `PATCH /ventas/{id}`**: las ventas no se modifican.

### RN-10 — Venta transaccional

- Cuatro clases de escritura en **una sola transacción**: `venta`, `renglon_venta` (uno por renglón),
  `libro.stock` (descuento) y `movimiento_stock` (uno por renglón, `cantidad` negativa).
- Si **un** libro no alcanza → **409** y **no queda ninguna** de esas escrituras (ni la venta, ni los
  renglones, ni los descuentos, ni los movimientos). Lo garantiza el `async with uow`: la excepción
  de negocio sale del bloque y el `__aexit__` revierte.
- Un libro **dado de baja** o un cliente/libro inexistente → también **409**, sin dejar escrituras
  (C-12).
- El chequeo de stock se hace **dentro** de la transacción y antes de escribir, pero la garantía
  última es el rollback, no el chequeo.
- **La concurrencia no se evalúa** (capítulo 7): dos ventas simultáneas del último ejemplar pueden
  pisarse. Es una limitación aceptada y explícita.

### RN-11 — Un solo punto de escritura del stock

- `libro.stock` **sólo** cambia por tres caminos, y los tres dejan movimiento:
  1. **Alta del libro** con `stock_inicial` → movimiento «Stock inicial».
  2. **Reposición** (`POST /libros/{id}/reponer`) → movimiento de entrada.
  3. **Venta** → un movimiento de salida por renglón.
- **No hay `PATCH` que toque el stock**: `POST /libros` recibe `stock_inicial` (no `stock`) y
  `PATCH /libros/{id}` acepta sólo título y precio. Mandar `stock` → **422** (C-16).
- El punto único es **un método del repositorio/servicio** que usan los tres caminos: escribe el
  `libro.stock` **y** agrega el `movimiento_stock` en el mismo lugar, para que no exista forma de
  escribir uno sin el otro.
- Invariante verificable en cualquier momento:
  `libro.stock = SUM(movimiento_stock.cantidad) WHERE libro_id = libro.id`.

### RN-12 — Sólo agregado

- `UPDATE` y `DELETE` sobre `movimiento_stock` son **rechazados por la base**, venga de donde venga
  (aplicación, `psql`, un script).
- Garante: **disparador** instalado por la **cuarta migración, escrita a mano** (la comparación
  automática de Alembic no ve funciones ni disparadores).
- Corregir un movimiento = **compensarlo con otro** de signo contrario.
- C-14 lo prueba con `test/solo_agregado.sql` corrido en `psql`: las dos sentencias fallan.
- Mecanismo alternativo (rol de base sin permiso de escritura sobre la tabla): **no se pide**; con el
  disparador alcanza. Tener los dos sería defensa en profundidad.

### RN-13 — Baja lógica

- `DELETE /libros/{id}` **no borra**: escribe `borrado_en = now()` y responde **204**.
- Efectos inmediatos: deja de aparecer en **todos** los listados y en el detalle público
  (`SoftDeleteRepository` filtra `borrado_en IS NULL`); **no se puede vender** ni **reponer**
  (→ 409).
- Lo que **no** cambia: la fila sigue, `GET /ventas/{id}` sigue mostrando el título en los renglones
  viejos, y el ISBN se puede volver a usar en un alta nueva.
- Dar de baja un libro ya dado de baja (o inexistente) → **404**.

### RN-14 — Lo propio

- `GET /mis-ventas`: **sólo pide estar autenticado**, no un rol. Devuelve las ventas del cliente
  ligado al usuario autenticado (`cliente.usuario_id = usuario.id`).
- Si el usuario autenticado **no tiene ficha de cliente** (por ejemplo un VENDEDOR), `/mis-ventas`
  devuelve una página vacía. **Suposición** — ver `09_decisiones_y_supuestos.md` (SU-05).
- `GET /ventas/{id}`: si no es personal ni dueño → **403** (nunca 404 «para no revelar»: la consigna
  fija 403).
- `GET /clientes/{id}/ventas` es de personal (VENDEDOR/ADMIN); un CLIENTE recibe **403**.

### RN-15 — Nada de texto interno, nada de 500

- Ningún error devuelve el texto de PostgreSQL (que entregaría el mapa del esquema: nombres de
  tablas, columnas, constraints).
- Toda violación de unicidad/FK/CHECK se **traduce** a 409 o 422 con mensaje propio.
- **Ninguna entrada inválida termina en 500**: cubre id no entero en la ruta (422, C-01), cuerpo que
  no cumple el contrato (422), `size` gigante (422), `' OR '1'='1` (lista vacía o resultados
  literales, nunca error), JSON malformado (422), contraseña de más de 72 bytes (422).
- No se filtra la traza: sin `debug=True` y con manejadores de error propios.

### RN-16 — Auditoría en la misma transacción

- Tres operaciones dejan línea en `evento_seguridad`:
  1. **Alta de personal** (`POST /usuarios`),
  2. **Cambio de rol** (asignar o revocar),
  3. **Cambio de contraseña**.
- La línea se escribe en **la misma transacción** que el cambio: si el cambio se revierte, la línea
  también.
- `actor` es **texto**: el email del usuario que ejecuta, o `'SISTEMA'` cuando no hay usuario humano
  (seed: «Carga de los datos iniciales»).
- `GET /eventos` (ADMIN) lista el historial con el envoltorio de paginación.

## Reglas del TP que siguen vigentes sin renumerar

La consigna dice: «Siguen vigentes, aunque no se repitan acá, los `CHECK` de precio y de stock del
libro y la búsqueda por título con parámetros ligados».

| Regla heredada | Estado |
|---|---|
| `CHECK (libro.precio > 0)` | Vigente |
| `CHECK (libro.stock >= 0)` | Vigente (el `CHECK` impide el stock negativo; **no** impide la actualización perdida) |
| `UNIQUE (perfil_cliente.cliente_id)` | Vigente: un cliente tiene a lo sumo un perfil (consigna RN-09) |
| Búsqueda de libros por título con **parámetros ligados**, sin distinguir mayúsculas | Vigente; `' OR '1'='1` no debe romper ni devolver todo |

## Reglas del TP cap 1-4 (numeración original de la consigna)

> La consigna de los capítulos 1 a 4 numera sus propias reglas `RN-01…RN-12`. El parcial las
> **renumeró** («las reglas de esta tabla se numeran de nuevo y reemplazan a las del TP en lo que se
> superponen»), por eso los números ya no coinciden. Esta tabla conserva la **numeración original del TP**
> para que se pueda cotejar contra el PDF, y dice **dónde vive hoy** cada regla en este documento.

| TP RN | Enunciado (consigna) | Garante esperado | Dónde vive hoy |
|---|---|---|---|
| RN-01 (TP) | El ISBN de un libro es único. | `UNIQUE` en la base; 409 | Parcial `RN-01` (ampliada: único entre los vigentes) |
| RN-02 (TP) | El email de un cliente es único. | `UNIQUE` en la base; 409 | Parcial `RN-01` (cliente.email) |
| RN-03 (TP) | El precio de un libro es mayor que cero y el stock nunca es negativo. | `CHECK` en la base y validación del DTO | «Reglas del TP que siguen vigentes» (CHECKs) |
| RN-04 (TP) | Una venta se crea con sus renglones: los datos de cada renglón viajan dentro del cuerpo del alta de la venta, y no existe un alta de renglones por separado. | DTO anidado; los renglones se agregan a `venta.renglones` | Parcial `RN-09` |
| RN-05 (TP) | Una venta tiene al menos un renglón, y un mismo libro no aparece en dos renglones. | Validación del DTO; 422 | Parcial `RN-09` |
| RN-06 (TP) | El precio de cada renglón se copia del libro al registrar la venta y no cambia aunque después cambie el precio del libro. | El servidor lo lee de la base; nunca viaja en el DTO | Parcial `RN-09` |
| RN-07 (TP) | El total de la venta lo calcula el servidor como suma de cantidad por precio unitario. | No viaja en el DTO | Parcial `RN-09` |
| RN-08 (TP) | Las ventas no se modifican: registran un hecho. | No hay `PATCH` de ventas | Parcial `RN-09` / `RN-11` (DD-11) |
| RN-09 (TP) | Un cliente tiene como máximo un perfil. | `UNIQUE` en `perfil_cliente.cliente_id`; 409 | Esquema (`perfil_cliente.cliente_id` UNIQUE); «Reglas del TP que siguen vigentes» |
| RN-10 (TP) | Todo listado se pagina con `limit` (de 1 a 100, por defecto 20) y `offset` (desde 0). | Restricciones en `Query`; 422 | `02_descripcion_general.md` (envoltorio) y DD-18 (renumerado a `page`/`size`) |
| RN-11 (TP) | El listado de libros se puede filtrar por parte del título, sin distinguir mayúsculas. | Parámetro ligado, nunca SQL armado con texto | `02_descripcion_general.md` y «Reglas del TP que siguen vigentes» |
| RN-12 (TP) | Ningún error devuelve al cliente texto interno de la base (nombres de tablas, restricciones o trazas). | Traducción del `IntegrityError` a un mensaje propio | Parcial `RN-15` |

## Convenciones de ingeniería (`CV`) — **no son reglas de la consigna**

Salen de `docs/CHECKLIST_ANTES_DE_ENTREGAR.md` y de las secciones de la consigna que describen
*estructura* (Ejercicios 1, 3, 6, 7). Se numeran aparte **para no contaminar los `RN`**: la
corrección cita `RN-NN` y espera el significado de la consigna.

| Código | Convención | Origen |
|---|---|---|
| CV-01 | El **router construye** el Unit of Work con una dependencia y se lo pasa al servicio **sin abrirlo**; el **servicio lo abre** con `async with` y **nunca lo construye**; **sólo `__aexit__` confirma**. | Consigna Ej. 6 + checklist §0/§7 |
| CV-02 | Ningún `selectinload` (ni otra precarga) **fuera de `repository.py`**. La precarga se declara adentro del método del repositorio que la necesita. | Consigna Ej. 6/8 + checklist §0 |
| CV-03 | Paths exactos: `app/core/{config,database,security,dependencies,repository,paginacion,unit_of_work}.py`, `app/modules/<módulo>/{models,schemas,repository,unit_of_work,service,router}.py`, `main.py`, `seed.py`, `migrations/`, `test/`. Sin shims ni alias. | Consigna «Estructura obligatoria» + checklist §0/§1 |
| CV-04 | `test/` guarda los `.http` por módulo y `solo_agregado.sql`; `tests/` es **sólo pytest** (nada de `.http` ni `.sql` sueltos). | Checklist §1 |
| CV-05 | `env.example` va **sin punto inicial**; `.gitignore` incluye `.env`. | Checklist §1 |
| CV-06 | `alembic.ini` **sin** `sqlalchemy.url` con credenciales; `migrations/env.py` lee de `Settings`. | Checklist §2 |
| CV-07 | Un schema por operación (`Create`, `Update`, `Read`), todos con `extra="forbid"`; ninguno incluye `password_hash`. | Consigna Ej. 3 + checklist §4 |
| CV-08 | Orden de errores al resolver una petición: **404 → 403 → 409 → 422**. | Checklist §4 |
| CV-09 | Nombres de variables de entorno del checklist: `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`, `BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`, `POOL_SIZE`, `SQL_ECHO`. | Checklist §2 (la consigna fija el **concepto**, no el nombre) |
| CV-10 | `alembic check` sin operaciones nuevas antes de entregar. | Checklist §3 |
| CV-11 | El seed corre después de `alembic upgrade head` y es **idempotente**. | Checklist §9 |
| CV-12 | Tests contra **PostgreSQL real** (nunca SQLite); comparan **status + body**, no `model_dump()`. | Checklist §10 |
| CV-13 | `health` es el único módulo con **sólo** `router.py`. | Consigna p. 9 |
| CV-14 | La base no se crea con `create_all`: **sólo Alembic**. | Consigna Ej. 2 + requisito no funcional |

## Reglas de diseño propias (`RD`) — **no están en la consigna**

| Código | Regla | Por qué existe |
|---|---|---|
| RD-01 | Existencia de una suite `tests/` con pytest, además de los `.http` de `test/`. | El formato de entrega de la consigna sólo menciona `test/`; la suite es una decisión de calidad del grupo, no un requisito corregible. |
| RD-02 | `motivo` de `movimiento_stock` se escribe con las etiquetas `'Stock inicial'`, `'Reposición'` y `'Venta'`. | La consigna nombra «Stock inicial» y habla de reposición y venta, pero no fija el vocabulario de la columna. Ver SU-04. |
| RD-03 | Los mensajes de error de negocio se escriben en español, en segunda persona, sin jerga de base. | Consecuencia operativa de RN-15; el texto exacto no está en la consigna. |
