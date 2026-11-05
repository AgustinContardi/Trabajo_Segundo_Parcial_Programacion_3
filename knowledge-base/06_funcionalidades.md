# Funcionalidades

Organizadas por **épica** y luego por **historia de usuario** (`US-NNN`). Alcance: capítulos 5 y 6 del
TP de la librería, más el despliegue del TP de los capítulos 1 a 4. Cada historia cita las reglas
(`RN`) y las convenciones (`CV`) que la restringen.

**Fuera de este alcance**: concurrencia (cap. 7), colas con Redis (cap. 8), `PATCH` de ventas,
envío real de correo.

---

## Épica 1 — Acceso y sesión

### US-001 — Auto-registro de un cliente

**Como** visitante
**Quiero** registrarme con mi correo, mi nombre y una contraseña
**Para** consultar mis compras desde la web

**Criterios de aceptación**:
- [ ] `POST /auth/registro` → **201**; crea **tres** filas: `usuario`, `asignacion_rol` con
      `rol = 'CLIENTE'` y `cliente` con `usuario_id` apuntando al usuario nuevo.
- [ ] Las tres escrituras ocurren en **un solo Unit of Work**: si la tercera falla, no queda ninguna.
- [ ] El rol **no viaja en el cuerpo**; mandarlo da **422** (`extra="forbid"`).
- [ ] Correo ya usado por un **usuario** → **409**; correo ya usado por un **cliente** → **409** y
      **no se apropia** de esa ficha (no se le setea `usuario_id`).
- [ ] Contraseña de más de **72 bytes** → **422** (bytes, no caracteres: una «ñ» ocupa dos).
- [ ] La respuesta **no** incluye `password_hash`.

**Reglas**: RN-01, RN-02, RN-15 · **Casos**: C-02

### US-002 — Iniciar sesión

**Como** usuario con cuenta
**Quiero** iniciar sesión con correo y contraseña
**Para** acceder a lo que mi rol permite

**Criterios de aceptación**:
- [ ] `POST /auth/login` → **200** con el cuerpo
      `{"mensaje": "Sesión iniciada", "debe_cambiar_password": false, "expira_en_segundos": 1800}`.
- [ ] El token **no viaja en el cuerpo**: viaja en `Set-Cookie` como `access_token` con
      **`HttpOnly`**, **`SameSite=Lax`**, **`Max-Age`** igual a la duración del token y **`Secure`**
      configurable.
- [ ] `expira_en_segundos` coincide con la duración configurada del token.
- [ ] Credenciales inválidas → **401** con el **mismo cuerpo** exista o no el correo.
- [ ] El tiempo de respuesta es **parecido** en los dos casos (hash ficticio).
- [ ] Un login correcto **reinicia** el conteo de intentos fallidos (RN-07).
- [ ] El JWT tiene `sub`, `exp` y los **roles vigentes al emitirlo** (informativos).

**Reglas**: RN-04, RN-07, RN-08 · **Casos**: C-03, C-04

### US-003 — Cerrar sesión

**Como** usuario autenticado
**Quiero** cerrar mi sesión
**Para** que la cookie deje de servir en este navegador

**Criterios de aceptación**:
- [ ] `POST /auth/logout` → **200** y borra la cookie (`Max-Age=0`).
- [ ] Responde 200 incluso sin sesión (está en el grupo abierto).

### US-004 — Consultar mi identidad y mis roles

**Como** usuario autenticado
**Quiero** ver quién soy y qué roles tengo
**Para** entender por qué puedo o no puedo hacer algo

**Criterios de aceptación**:
- [ ] `GET /auth/yo` → **200** con el usuario (sin `password_hash`), los **roles vigentes leídos de
      `asignacion_rol`** y los **roles que dice el token**.
- [ ] Los dos conjuntos pueden diferir: es exactamente lo que evidencia C-07.
- [ ] Sin cookie, con token inválido o vencido, o con usuario inactivo → **401**.

**Reglas**: RN-04 · **Casos**: C-03, C-07

### US-005 — Cambiar mi contraseña

**Como** usuario autenticado
**Quiero** cambiar mi contraseña
**Para** dejar de usar la provisoria

**Criterios de aceptación**:
- [ ] `POST /auth/cambiar-password` → **200**; recibe la contraseña **actual** y la nueva.
- [ ] La nueva contraseña se hashea con bcrypt **antes de abrir la transacción**.
- [ ] Al terminar, `debe_cambiar_password` queda en **`false`**.
- [ ] **La misma cookie sigue sirviendo** para las rutas protegidas (200) sin volver a iniciar
      sesión; no se emite un token nuevo. (Ver `10_preguntas_abiertas.md`, IN-03: el checklist
      heredado decía lo contrario.)
- [ ] Contraseña actual incorrecta → **401**; nueva de más de 72 bytes → **422**.
- [ ] Deja una línea en `evento_seguridad` en la **misma transacción**.

**Reglas**: RN-06, RN-16 · **Casos**: C-09

### US-006 — Bloqueo por cambio obligatorio

**Como** administrador que dio de alta a alguien
**Quiero** que esa persona no pueda operar hasta cambiar la contraseña provisoria
**Para** que nadie trabaje con una contraseña conocida por otro

**Criterios de aceptación**:
- [ ] Con `debe_cambiar_password = true`, toda ruta del **grupo protegido** responde **403**.
- [ ] Las rutas de `/auth` y las que no piden sesión siguen accesibles.
- [ ] El control está montado **una sola vez**, a nivel del router protegido.

**Reglas**: RN-06 · **Casos**: C-09

### US-007 — Límite de intentos de login

**Como** responsable del sistema
**Quiero** que el login frene la fuerza bruta
**Para** que no se puedan probar contraseñas en serie

**Criterios de aceptación**:
- [ ] Sexto intento fallido con el mismo **correo** desde la misma **IP** dentro de **60 s** → **429**
      con `Retry-After`.
- [ ] El 429 se resuelve **sin calcular ningún hash** (responde en milisegundos).
- [ ] Los cinco fallos quedan registrados en `intento_acceso` (`exito = false`).
- [ ] Cada intento, correcto o fallido, se escribe en `intento_acceso` desde **una sesión y una
      transacción propias que se confirman siempre**.
- [ ] El código que lo hace lleva un comentario con tres cosas: qué hace distinto, por qué no puede
      compartir la transacción y su costo (deja filas aunque la petición falle).

**Reglas**: RN-07 · **Casos**: C-05

### US-008 — No revelar qué cuentas existen

**Como** responsable de seguridad
**Quiero** que el login no distinga correo existente de inexistente
**Para** que no se pueda enumerar la base de usuarios

**Criterios de aceptación**:
- [ ] Mismo status y mismo cuerpo en los dos casos.
- [ ] Tiempos comparables: se verifica contra un **hash ficticio** del mismo costo bcrypt.
- [ ] El hash ficticio se calcula **una vez, en el lifespan**, no por petición.

**Reglas**: RN-08 · **Casos**: C-04

---

## Épica 2 — Administración de personal y roles

### US-010 — Alta de personal

**Como** ADMIN
**Quiero** dar de alta a un vendedor o a otro administrador con una contraseña provisoria
**Para** que empiece a trabajar y la cambie en su primer ingreso

**Criterios de aceptación**:
- [ ] `POST /usuarios` → **201**; crea el usuario y su asignación de rol en **un solo UoW**.
- [ ] La contraseña provisoria se guarda hasheada (bcrypt, `to_thread` + semáforo).
- [ ] El usuario nace con `debe_cambiar_password = true`.
- [ ] Correo repetido → **409**; campos de más → **422**.
- [ ] Deja línea en `evento_seguridad` (alta de personal) en la misma transacción.
- [ ] Un VENDEDOR o un CLIENTE que lo intente → **403**; sin sesión → **401**.

**Reglas**: RN-01, RN-15, RN-16 · **Suposición**: el cuerpo acepta el rol inicial ADMIN o VENDEDOR
(SU-02). CLIENTE se crea por auto-registro.

### US-011 — Asignar un rol con vigencia opcional

**Como** ADMIN
**Quiero** otorgar un rol con una fecha de vencimiento opcional
**Para** que un reemplazo temporal se revoque solo

**Criterios de aceptación**:
- [ ] `POST /usuarios/{id}/roles` → **201**.
- [ ] `vence_en` es **opcional**; si viene, es **con zona horaria** y en el **futuro**.
- [ ] `vence_en` en el pasado o **sin zona** → **422** (no 409).
- [ ] Una segunda asignación **abierta** del mismo rol → **409** (índice único parcial).
- [ ] Usuario inexistente → **404**.
- [ ] Deja línea en `evento_seguridad` en la misma transacción.

**Reglas**: RN-03, RN-16 · **Casos**: C-07

### US-012 — Revocar un rol

**Como** ADMIN
**Quiero** revocar un rol sin borrar el historial
**Para** saber quién tuvo qué rol y hasta cuándo

**Criterios de aceptación**:
- [ ] `DELETE /usuarios/{id}/roles/{rol}` → **200**; escribe `revocada_en = now()`.
- [ ] **La fila no se borra nunca.**
- [ ] El efecto es inmediato sobre una sesión ya abierta: la petición siguiente con la misma cookie
      recibe **403** en las rutas que exigían ese rol.
- [ ] Rol no asignado o ya revocado → **404** / **409** según el caso.
- [ ] Deja línea en `evento_seguridad`.

**Reglas**: RN-03, RN-04, RN-16 · **Casos**: C-07

### US-013 — Reasignar un rol vencido

**Como** ADMIN
**Quiero** volver a otorgar un rol que venció
**Para** que la persona recupere el permiso

**Criterios de aceptación**:
- [ ] El servicio **cierra la fila anterior** (escribe `revocada_en`) y **abre una nueva**, en la
      misma transacción.
- [ ] No choca con el índice único parcial: la anterior deja de estar abierta.
- [ ] El historial completo queda visible en `GET /usuarios/{id}/roles`.

**Reglas**: RN-03 · **Casos**: C-07

### US-014 — Autoprotección del administrador

**Como** ADMIN
**Quiero** que el sistema me impida quedarme sin administradores
**Para** no dejar el sistema sin quien lo administre

**Criterios de aceptación**:
- [ ] Revocar mi propio rol ADMIN → **409**.
- [ ] Revocar el **último** ADMIN vigente (aunque lo haga otro admin) → **409**.
- [ ] La comprobación corre en el **servicio**, después de identificar al solicitante.

**Reglas**: RN-05 · **Casos**: C-08

### US-015 — Consultar las asignaciones de un usuario

**Como** ADMIN
**Quiero** ver todos los roles de una persona, vigentes y cerrados
**Para** auditar su historial

**Criterios de aceptación**:
- [ ] `GET /usuarios/{id}/roles` → **200** con todas las filas, incluidas las revocadas y vencidas.
- [ ] Usuario inexistente → **404**.

### US-016 — Historial de seguridad

**Como** ADMIN
**Quiero** ver las operaciones sensibles registradas
**Para** auditar quién hizo qué y cuándo

**Criterios de aceptación**:
- [ ] `GET /eventos` (`page`, `size`) → **200** con el envoltorio `{items, total, page, size, pages}`.
- [ ] Cada ítem trae `cuando`, `actor` y `accion`.
- [ ] `actor` puede valer `'SISTEMA'` (seed).
- [ ] `size=500` → **422**; página fuera de rango → **422**.

---

## Épica 3 — Catálogo y stock

### US-020 — Explorar el catálogo sin sesión

**Como** visitante
**Quiero** ver y buscar libros
**Para** decidir qué comprar antes de registrarme

**Criterios de aceptación**:
- [ ] `GET /libros?page=&size=&titulo=&genero_id=` → **200** con el envoltorio.
- [ ] Excluye los libros con `borrado_en IS NOT NULL`.
- [ ] `titulo` busca con **parámetros ligados**, sin distinguir mayúsculas; `' OR '1'='1` no rompe
      ni devuelve todo (lista vacía con `total = 0`).
- [ ] `size` fuera de **1..100** → **422**; página más allá de la última → **422**; cero resultados →
      una página vacía con `pages = 1`.
- [ ] `total` cuenta con **los mismos filtros** que la página (`titulo=ficc&size=1` → `total 1`,
      `pages 1`, y `page=2` da 422).

**Reglas**: RN-13 · **Casos**: C-16

### US-021 — Ver el detalle de un libro

**Como** visitante
**Quiero** ver un libro puntual
**Para** conocer precio y disponibilidad

**Criterios de aceptación**:
- [ ] `GET /libros/{id}` → **200**.
- [ ] Libro inexistente o dado de baja → **404**.
- [ ] `{id}` no entero → **422 sin ejecutar el handler** (C-01).

**Casos**: C-01

### US-022 — Navegar editoriales, géneros y autores

**Como** visitante
**Quiero** ver las editoriales y géneros y los libros de cada uno
**Para** explorar por esas dimensiones

**Criterios de aceptación**:
- [ ] `GET /editoriales`, `GET /generos` → **200** con el envoltorio.
- [ ] `GET /editoriales/{id}/libros`, `/generos/{id}/libros`, `/autores/{id}/libros` → **200**.
- [ ] Id inexistente → **404**.

### US-023 — Alta de un libro con stock inicial

**Como** ADMIN
**Quiero** cargar un libro indicando con cuántos ejemplares entra
**Para** que el stock arranque con su movimiento correspondiente

**Criterios de aceptación**:
- [ ] `POST /libros` → **201**; recibe `isbn`, `titulo`, `precio`, **`stock_inicial`**, `editorial_id`,
      `genero_id` y `autores: [{autor_id, rol, orden}]`.
- [ ] **`stock` no se acepta en el cuerpo** (sólo `stock_inicial`).
- [ ] Deja un `movimiento_stock` con `motivo = 'Stock inicial'` y `cantidad = stock_inicial`, en la
      misma transacción que el alta.
- [ ] ISBN repetido **entre los vigentes** → **409**; ISBN de un libro **dado de baja** → **201**.
- [ ] Editorial/género/autor inexistente → **409** (choca con lo guardado).
- [ ] `precio <= 0` → **422**; `stock_inicial < 0` → **422**.
- [ ] Un VENDEDOR → **403**.

**Reglas**: RN-01, RN-11, RN-15 · **Casos**: C-13, C-16

### US-024 — Editar título y precio

**Como** ADMIN
**Quiero** corregir el título o el precio de un libro
**Para** mantener el catálogo al día

**Criterios de aceptación**:
- [ ] `PATCH /libros/{id}` → **200**; aplica **sólo los campos enviados** (`exclude_unset`).
- [ ] Acepta **únicamente** título y precio.
- [ ] Mandar `stock` → **422** (RN-11).
- [ ] Libro dado de baja → **404**.

**Reglas**: RN-11 · **Casos**: C-16

### US-025 — Dar de baja un libro

**Como** ADMIN
**Quiero** descatalogar un libro sin perder su historia
**Para** que no se venda más pero las ventas viejas sigan mostrándolo

**Criterios de aceptación**:
- [ ] `DELETE /libros/{id}` → **204**; escribe `borrado_en` (borrado lógico).
- [ ] El libro deja de aparecer en el catálogo y en el detalle público.
- [ ] Venderlo o reponerlo → **409**.
- [ ] La venta vieja que lo contiene **sigue mostrando el título**.
- [ ] El ISBN queda libre para un alta nueva.
- [ ] Libro ya dado de baja o inexistente → **404**.

**Reglas**: RN-13 · **Casos**: C-12, C-13

### US-026 — Reponer stock

**Como** ADMIN
**Quiero** sumar ejemplares a un libro
**Para** volver a tener stock disponible

**Criterios de aceptación**:
- [ ] `POST /libros/{id}/reponer` → **200** con el libro actualizado.
- [ ] Deja un `movimiento_stock` de entrada (`cantidad > 0`) con su `motivo`, en la misma transacción.
- [ ] `cantidad <= 0` → **422**; libro dado de baja → **409**; libro inexistente → **404**.
- [ ] El `stock` resultante respeta `libro.stock = SUM(movimiento_stock.cantidad)`.

**Reglas**: RN-11, RN-13 · **Casos**: C-13

### US-027 — Ver los movimientos de un libro

**Como** ADMIN
**Quiero** ver todos los movimientos de stock de un libro
**Para** explicar por qué el stock es el que es

**Criterios de aceptación**:
- [ ] `GET /libros/{id}/movimientos` → **200**.
- [ ] Cada movimiento trae `cantidad` (con signo), `motivo`, `cuando`, `usuario_id` y `venta_id`
      (nulo si no vino de una venta).
- [ ] Libro inexistente → **404**.

**Reglas**: RN-11 · **Casos**: C-13

---

## Épica 4 — Clientes

### US-030 — Alta de cliente de mostrador

**Como** VENDEDOR o ADMIN
**Quiero** dar de alta un cliente sin acceso web
**Para** registrarle ventas en el mostrador

**Criterios de aceptación**:
- [ ] `POST /clientes` → **201**; `usuario_id` queda **nulo**.
- [ ] Correo repetido → **409**.
- [ ] Campos de más → **422**.

**Reglas**: RN-01

### US-031 — Consultar y editar un cliente

**Como** VENDEDOR o ADMIN
**Quiero** ver y corregir los datos de un cliente con su perfil
**Para** mantener la ficha al día

**Criterios de aceptación**:
- [ ] `GET /clientes/{id}` → **200** con su perfil (si tiene).
- [ ] `PATCH /clientes/{id}` → **200**, sólo los campos enviados.
- [ ] Inexistente → **404**; correo que choca → **409**.

### US-032 — Alta del perfil de un cliente

**Como** VENDEDOR o ADMIN
**Quiero** cargar los datos de contacto de un cliente
**Para** tener su ficha completa

**Criterios de aceptación**:
- [ ] `POST /clientes/{id}/perfil` → **201**.
- [ ] Cliente inexistente → **404**; el cliente ya tiene perfil → **409**.

### US-033 — Ver las ventas de un cliente

**Como** VENDEDOR o ADMIN
**Quiero** ver el historial de compras de un cliente
**Para** atender un reclamo

**Criterios de aceptación**:
- [ ] `GET /clientes/{id}/ventas` → **200**.
- [ ] Cliente inexistente → **404**.
- [ ] Un CLIENTE que lo intente → **403**.

**Reglas**: RN-14

---

## Épica 5 — Ventas

### US-040 — Registrar una venta

**Como** VENDEDOR o ADMIN
**Quiero** registrar una venta con uno o más libros
**Para** cobrar en el mostrador

**Criterios de aceptación**:
- [ ] `POST /ventas` → **201** con los precios copiados y el total calculado por el servidor.
- [ ] El cuerpo es `{"cliente_id": 2, "renglones": [{"libro_id": 1, "cantidad": 2}]}`: **no** viajan
      `precio`, `total` ni `fecha` (mandarlos → **422**).
- [ ] Al menos **un renglón**; **libros repetidos** → **422**.
- [ ] Descuenta el stock de cada libro y deja **un movimiento por renglón** (`cantidad` negativa),
      todo en **una sola transacción**.
- [ ] Si un libro **no alcanza** → **409** y **no queda ninguna escritura** (ni venta, ni renglones,
      ni descuentos, ni movimientos).
- [ ] Cliente o libro inexistente, o libro **dado de baja** → **409**, sin dejar escrituras.
- [ ] Agenda con `BackgroundTasks` el aviso del comprobante (ver US-042).
- [ ] Un CLIENTE → **403**.

**Reglas**: RN-09, RN-10, RN-11, RN-13 · **Casos**: C-10, C-11, C-12

### US-041 — Listar ventas

**Como** VENDEDOR o ADMIN
**Quiero** ver las ventas registradas
**Para** hacer el cierre del día

**Criterios de aceptación**:
- [ ] `GET /ventas?page=&size=` → **200** con el envoltorio.
- [ ] Orden estable y paginación consistente (`total` con los mismos filtros).

### US-042 — Ver el detalle de una venta

**Como** personal **o** como el cliente dueño de la venta
**Quiero** ver una venta con sus renglones y los libros
**Para** revisar qué se cobró

**Criterios de aceptación**:
- [ ] `GET /ventas/{id}` → **200** con cliente, renglones y **el libro de cada renglón, aunque esté
      dado de baja**.
- [ ] **No lleva `requiere_rol`**: el servicio decide. Si no es personal ni dueño → **403**;
      inexistente → **404**.
- [ ] El número de consultas es **fijo** y **no crece** con la cantidad de renglones (mismo conteo
      con 2 y con 4 renglones).
- [ ] Toda la precarga está declarada en el **repositorio**; ninguna lectura depende de carga
      perezosa.
- [ ] Si la venta se acaba de crear, el aviso del comprobante sale en el registro **después** de la
      respuesta: `await asyncio.sleep(0.5)` y una línea visible con el logging por defecto de uvicorn.

**Reglas**: RN-13, RN-14 · **Casos**: C-06, C-15, C-10

### US-043 — Ver mis compras

**Como** CLIENTE
**Quiero** ver sólo mis ventas
**Para** consultar mi historial sin ver el de otros

**Criterios de aceptación**:
- [ ] `GET /mis-ventas?page=&size=` → **200** con **sólo** las ventas del cliente ligado a mi
      usuario.
- [ ] No exige rol, sólo sesión (RN-14).
- [ ] Sin sesión → **401**.

**Reglas**: RN-14 · **Casos**: C-06

---

## Épica 6 — Operación, esquema y datos iniciales

### US-050 — Sonda de vida

**Como** operador
**Quiero** un endpoint que diga si el proceso está vivo
**Para** distinguir «proceso caído» de «base caída»

**Criterios de aceptación**:
- [ ] `GET /health/live` → **200** siempre que el proceso responda; **no toca la base**.

### US-051 — Sonda de disponibilidad

**Como** operador
**Quiero** un endpoint que diga si la aplicación puede atender
**Para** que el `HEALTHCHECK` del contenedor y el balanceador sepan si mandar tráfico

**Criterios de aceptación**:
- [ ] `GET /health/ready` ejecuta `SELECT 1` → **200**.
- [ ] Si la base no contesta → **503** (el proceso puede estar vivo y no estar listo; reiniciarlo no
      arregla una base caída).

### US-052 — Evolucionar el esquema con Alembic

**Como** equipo
**Quiero** versionar el esquema en migraciones
**Para** poder crear la base desde cero y volver atrás

**Criterios de aceptación**:
- [ ] A las migraciones del TP se suman **dos**: la **tercera autogenerada** (tablas de acceso,
      `movimiento_stock` y cambios en `cliente` y `libro`) y la **cuarta escrita a mano** (disparador
      de sólo agregado).
- [ ] Cada migración nueva **se lee antes de aplicarla** y lleva un **comentario que lo diga**; si la
      versión generada tuvo un problema, se corrige a mano y el comentario lo explica.
- [ ] Incluye los **dos índices únicos parciales** (`postgresql_where`).
- [ ] `alembic upgrade head` sobre base vacía, `alembic downgrade base` y otra vez `upgrade head`
      funcionan.
- [ ] **No se usa `create_all`** en ningún lado.

**Casos**: D-02 (en el despliegue, sobre el TP)

### US-053 — Dejar la base en el estado inicial conocido

**Como** equipo
**Quiero** un `seed.py` reproducible
**Para** que los casos de prueba arranquen siempre igual

**Criterios de aceptación**:
- [ ] Vacía las tablas y carga los usuarios, el catálogo, los clientes, la venta 1, los movimientos y
      la línea de auditoría `SISTEMA` (ver `04_modelo_de_datos.md`).
- [ ] Es **idempotente** y corre **después** de `alembic upgrade head`.
- [ ] Al terminar, `libro.stock = SUM(movimiento_stock.cantidad)` en los **cinco** libros.

### US-054 — Ciclo de vida de los recursos

**Como** equipo
**Quiero** que el motor y la fábrica de sesiones se creen al arrancar
**Para** no construirlos al importar (antes de que exista el bucle de eventos)

**Criterios de aceptación**:
- [ ] `Settings` se lee del entorno; la URL se arma con un **`@computed_field`** y driver
      `postgresql+asyncpg`.
- [ ] Motor y `sessionmaker` se crean **en el `lifespan`** y se guardan en **`app.state`**.
- [ ] `get_session` toma la fábrica de `app.state`, entrega **una sesión por petición** con
      `expire_on_commit=False` y la cierra al terminar.
- [ ] El `lifespan` calcula **una vez** el hash ficticio del login.
- [ ] Al apagar, `dispose()` del motor.
- [ ] `POOL_SIZE` sale de la configuración.

**Reglas**: RN-08

---

## Épica 7 — Empaquetado y puesta en línea

### US-060 — Empaquetar el TP cap 1-4 en una imagen

**Como** equipo
**Quiero** una imagen Docker del TP de los capítulos 1 a 4
**Para** correrlo igual en mi máquina y en el VPS

**Criterios de aceptación**:
- [ ] `Dockerfile` + `.dockerignore`, sin Docker Compose y sin base de datos adentro.
- [ ] Imagen base `python:3.12-alpine` (por debajo de 100 MB).
- [ ] `requirements.txt` se copia e instala **antes** del código, con `--no-cache-dir`.
- [ ] La aplicación **no corre como root**.
- [ ] **Ningún secreto** en la imagen.
- [ ] Al arrancar: `alembic upgrade head` y después uvicorn en `0.0.0.0`.
- [ ] `HEALTHCHECK` sobre `GET /health/ready`.

**Casos**: D-01, D-06, D-07

### US-061 — Poner el TP en línea en el VPS

**Como** equipo
**Quiero** el TP cap 1-4 accesible desde afuera
**Para** que la corrección lo pueda probar

**Criterios de aceptación**:
- [ ] `docker run` con `-p`, `--restart unless-stopped` y `--env-file`.
- [ ] `DEPLOY.md` con URL pública, día y hora, comandos completos y procedimiento de actualización.
- [ ] El despliegue sigue en línea **hasta que se publiquen las notas**.

### US-062 — Dejar evidencia de los casos D

**Como** equipo
**Quiero** guardar la salida de cada caso D
**Para** que el despliegue sea corregible aun si el servidor se cae

**Criterios de aceptación**:
- [ ] `despliegue/evidencia/` con la salida de D-01…D-08.

Detalle completo de la épica 7 en **`11_despliegue_y_devops.md`**.

---

## Trazabilidad rápida

| Endpoint | US | RN |
|---|---|---|
| `POST /auth/registro` | US-001 | RN-01, RN-02 |
| `POST /auth/login` | US-002, US-007, US-008 | RN-07, RN-08 |
| `POST /auth/logout` | US-003 | — |
| `GET /auth/yo` | US-004 | RN-04 |
| `POST /auth/cambiar-password` | US-005, US-006 | RN-06, RN-16 |
| `POST /usuarios` | US-010 | RN-16 |
| `GET/POST /usuarios/{id}/roles` | US-011, US-013, US-015 | RN-03 |
| `DELETE /usuarios/{id}/roles/{rol}` | US-012, US-014 | RN-04, RN-05 |
| `GET /eventos` | US-016 | RN-16 |
| `GET /libros`, `GET /libros/{id}` | US-020, US-021 | RN-13 |
| `POST /libros` | US-023 | RN-01, RN-11 |
| `PATCH /libros/{id}` | US-024 | RN-11 |
| `DELETE /libros/{id}` | US-025 | RN-13 |
| `POST /libros/{id}/reponer` | US-026 | RN-11 |
| `GET /libros/{id}/movimientos` | US-027 | RN-11 |
| `POST/GET/PATCH /clientes…` | US-030…US-033 | RN-01, RN-14 |
| `POST /ventas` | US-040 | RN-09, RN-10 |
| `GET /ventas`, `GET /ventas/{id}` | US-041, US-042 | RN-14 |
| `GET /mis-ventas` | US-043 | RN-14 |
| `GET /health/*` | US-050, US-051 | — |

## Casos mínimos de la consigna (TP cap 1-4) — trazabilidad

La consigna (p. 10-11) define ocho casos mínimos `C-01…C-08`. El parcial los **renumeró y amplió** a
`C-01…C-16`; esta tabla dice dónde queda cada uno en la numeración actual.

| Consigna (TP) | Qué demuestra | Dónde vive hoy |
|---|---|---|
| C-01 (TP) | Parámetro de ruta que no es entero → 422, sin ejecutar el handler | C-01 (parcial) · US-021 |
| C-02 (TP) | ISBN o email repetido → 409 con mensaje propio | C-02 (parcial) · US-001, US-023 |
| C-03 (TP) | Segundo perfil para el mismo cliente → 409 | US-032 (sin número propio en el parcial) |
| C-04 (TP) | Libro con editorial o autor inexistente → 409 | US-023 (FK inexistente → 409) |
| C-05 (TP) | Venta con libro o cliente inexistente → 409 | US-040 (cliente/libro inexistente → 409) |
| C-06 (TP) | Venta válida con dos renglones → 201, precios copiados, total calculado | C-10 (parcial) · US-040 |
| C-07 (TP) | Detalle de un libro y de una venta: cantidad fija de consultas | C-15 (parcial) · US-021, US-042 |
| C-08 (TP) | Búsqueda por título con `' OR '1'='1` → 200 con lista vacía | C-16 (parcial) · US-020 |
