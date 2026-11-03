# Flujos Principales

Cada flujo se documenta de extremo a extremo, con **los límites de transacción explícitos**. La regla
de oro del parcial: *una operación de negocio = un `async with uow`*. Todo lo que se escribe adentro
se confirma junto o se revierte junto.

Leyenda de los diagramas:

```
Router      construye el UoW y lo pasa sin abrirlo
Service     lo abre con `async with` (nunca lo construye)
UoW         __aexit__: commit si salió bien, rollback si hubo excepción
Repo        flush(), nunca commit()
[TX]        frontera de transacción
```

---

## Flujo 1 — Auto-registro de un cliente (RN-02)

**Disparador**: `POST /auth/registro`
**Actor**: visitante
**Regla**: las tres filas o ninguna.

```
Visitante ──► Router /auth/registro
                 │  valida el contrato (extra="forbid", password ≤ 72 bytes → 422)
                 │  hashea la contraseña  ── to_thread + semáforo, FUERA de la transacción
                 ▼
              Service.registrar(uow)
                 │
                 ├── [TX abre]
                 │   repo_usuarios.add(usuario)                 ── flush()
                 │   repo_roles.add(asignacion_rol CLIENTE)     ── flush()
                 │   repo_clientes.add(cliente(usuario_id=…))   ── flush()
                 │      └── si el email choca → IntegrityError → 409
                 │          el __aexit__ REVIERTE: no queda ni el usuario ni el rol
                 ├── [TX commit]
                 ▼
              201
```

**Pasos**

1. El router valida el cuerpo: `email`, `nombre`, `password`. `rol` **no** es un campo: mandarlo da
   **422**.
2. El **hash bcrypt se calcula antes de abrir la transacción** (300 ms de CPU sin tener tomada una
   conexión del pool).
3. El servicio abre **un solo** Unit of Work y escribe, en orden: `usuario`, `asignacion_rol`
   (`rol = 'CLIENTE'`, `desde = now()`, `vence_en = null`, `revocada_en = null`), `cliente` con
   `usuario_id` apuntando al usuario nuevo.
4. Si el correo ya existe como **usuario** → `IntegrityError` de `usuario.email` → **409**.
5. Si el correo ya existe como **cliente** → `IntegrityError` de `cliente.email` → **409**, y la ficha
   existente **queda intacta**: no se le escribe `usuario_id`.
6. `__aexit__` confirma las tres o revierte las tres.

**Por qué un solo UoW**: un usuario sin rol no puede hacer nada; un cliente con `usuario_id` colgando
de un usuario inexistente rompe la FK y deja una ficha inutilizable. La consigna pide que un fallo en
la tercera escritura no deje las dos primeras.

**Casos de error**

| Caso | Manejo |
|---|---|
| Correo repetido en `usuario` o en `cliente` | 409 con mensaje propio (RN-15) |
| `rol` en el cuerpo, campo desconocido, email malformado | 422 |
| Contraseña de más de 72 **bytes** | 422 (nunca 500) |
| Falla la tercera escritura | rollback: no queda nada |

---

## Flujo 2 — Login con límite de intentos (RN-07, RN-08)

**Disparador**: `POST /auth/login`
**Actor**: cualquiera
**Particularidad**: la fila de `intento_acceso` **no comparte** la transacción de la petición.

```
POST /auth/login
   │
   ├─(1) contar intentos ────────────────────────────── 1 consulta, sin hash
   │      SELECT count(*) FROM intento_acceso
   │       WHERE email=:e AND ip=:ip AND exito=false
   │         AND cuando > now() - 60s
   │      (ventana posterior al último login exitoso de ese email+ip)
   │
   ├─ si count >= 5 ──► 429 + Retry-After  ── SIN verificar contraseña, SIN hash
   │
   ├─(2) buscar usuario por email
   │      ├── existe  → hash = usuario.password_hash
   │      └── no existe → hash = HASH_FICTICIO (calculado una vez en el lifespan)
   │
   ├─(3) bcrypt.checkpw en to_thread + semáforo   ── mismo costo en los dos casos
   │
   ├─(4) [TX PROPIA, SIEMPRE COMMIT]
   │      INSERT intento_acceso(cuando, email, ip, exito)
   │      └── sesión y transacción separadas, con `async with` propio
   │
   ├─ si credenciales malas ──► 401 (mismo cuerpo que el correo inexistente)
   │
   └─ si credenciales buenas:
         roles vigentes = SELECT rol FROM asignacion_rol
                           WHERE usuario_id=:id AND revocada_en IS NULL
                             AND (vence_en IS NULL OR vence_en > now())
         token = JWT(sub, exp, roles)            ── roles informativos
         Set-Cookie: access_token=…; HttpOnly; SameSite=Lax; Max-Age=ttl; Secure=cfg
         200 {mensaje, debe_cambiar_password, expira_en_segundos}
```

**Pasos y decisiones**

1. **Primero el límite, después la verificación.** El conteo cuesta una consulta; si ya está
   bloqueado, se responde 429 **sin calcular ningún hash** (C-05 exige milisegundos).
2. La verificación corre **fuera del bucle** (`to_thread`) y bajo un **semáforo** que limita cuántas
   corren a la vez: bcrypt no puede frenar el servidor.
3. **El correo inexistente se verifica igual**, contra un hash ficticio del mismo costo. Eso iguala
   cuerpo y tiempo (RN-08).
4. **La fila del intento se escribe en su propia sesión, con su propia transacción, y se confirma
   siempre**, incluso si el login termina en 401. Es **la única escritura del sistema que no comparte
   la transacción de su petición**: el fallo que se quiere contar es el mismo que la revierte. El
   código lo declara en un comentario que dice **tres cosas**: qué hace distinto, por qué no puede
   compartir la transacción y **cuál es su costo** (deja filas aunque la petición falle).
5. **El login correcto reinicia la cuenta**: los fallos anteriores siguen en la tabla, pero el conteo
   del paso 1 sólo mira los posteriores al último `exito = true` de ese `email` + `ip`.
6. La cookie se arma con `Max-Age` igual a la duración del token; el cuerpo **no** trae el token.

**Casos de error**

| Caso | Manejo |
|---|---|
| Sexto intento en 60 s | 429 + `Retry-After` |
| Contraseña mala | 401, mismo cuerpo |
| Correo inexistente | 401, mismo cuerpo, tiempo parecido |
| Usuario `activo = false` | 401 |
| Contraseña de más de 72 bytes | 422 antes de tocar bcrypt |

> **Nota sobre el intento bloqueado.** El 429 también es un «intento de login» y se anota; como la
> cuenta ya está bloqueada, registrarlo no cambia la decisión siguiente. Ver `AB-03` en
> `10_preguntas_abiertas.md`.

---

## Flujo 3 — Autorización de una petición autenticada (RN-04, RN-06)

**Disparador**: cualquier ruta del grupo protegido.
**Regla**: los roles se leen de la base **en cada petición**; el token sólo dice quién es.

```
Cookie access_token
   │
   ▼
get_usuario_actual
   ├─ sin cookie ──────────────────────────────► 401
   ├─ JWT inválido / vencido ──────────────────► 401
   ├─ usuario inexistente o activo=false ──────► 401
   └─ usuario OK
        │
        ├─ control del cambio obligatorio (grupo protegido, montado UNA vez)
        │     debe_cambiar_password = true ─────► 403
        │
        ▼
   requiere_rol("ADMIN")  ── 1 consulta a asignacion_rol con la MISMA sesión del UoW
        ├─ rol vigente ────────────────────────► sigue
        └─ no vigente (revocado o vencido) ────► 403
```

Puntos finos:

- **La misma sesión**: las dependencias de usuario actual y de rol reciben la sesión del Unit of Work.
  Sin esa unificación, cada petición autenticada tomaría **dos conexiones** del pool.
- **Los roles del token no se usan para decidir**: se devuelven en `/auth/yo` sólo para que la
  diferencia se vea.
- **`/ventas/{id}` no lleva `requiere_rol`**: pasa el `get_usuario_actual` y el **servicio** decide
  (personal → 200; dueño → 200; otro → 403).

---

## Flujo 4 — Cambio de contraseña (RN-06, RN-16)

**Disparador**: `POST /auth/cambiar-password`
**Actor**: usuario autenticado (típicamente con `debe_cambiar_password = true`)

```
POST /auth/cambiar-password   (grupo ABIERTO: no lleva el control de RN-06)
   │
   ├─ get_usuario_actual ── sin cookie/ inválido ──► 401
   ├─ valida contrato: actual + nueva, ≤ 72 bytes cada una ──► 422
   │
   ├─ bcrypt.checkpw(actual, usuario.password_hash)  ── to_thread + semáforo
   │     └─ no coincide ──► 401   (no escribe intento_acceso: no es un login)
   │
   ├─ hash_nuevo = bcrypt(nueva)  ── FUERA de la transacción
   │
   ├─ [TX abre]
   │    usuario.password_hash      = hash_nuevo
   │    usuario.debe_cambiar_password = false
   │    evento_seguridad.add(actor=usuario.email,
   │                        accion="Cambio de contraseña")   ← misma transacción (RN-16)
   ├─ [TX commit]
   ▼
200
```

**Lo que NO pasa** (y es la trampa de este parcial):

- **No se emite un token nuevo** y **no se rota la cookie**. La sesión abierta sigue valiendo: la
  misma cookie entra a las rutas protegidas con **200** sin volver a iniciar sesión (C-09).
- **No se invalidan las otras sesiones** del usuario: es un login tradicional con cookie, la sesión
  dura hasta que el token vence o se cierra la sesión.
- El bloqueo de RN-06 se libera porque el **estado vive en la base** (`debe_cambiar_password`), no en
  el token: la petición siguiente ya lo lee en `false`.

> El checklist heredado decía «entrega cookie nueva; la anterior da 401». **La consigna dice lo
> contrario** y gana el PDF. Ver `IN-03` en `10_preguntas_abiertas.md`.

---

## Flujo 5 — Registrar una venta (RN-09, RN-10, RN-11)

**Disparador**: `POST /ventas`
**Actor**: VENDEDOR o ADMIN
**Regla**: cuatro clases de escritura, una sola transacción.

```
POST /ventas {cliente_id, renglones:[{libro_id, cantidad}]}
   │
   ├─ requiere_rol(VENDEDOR, ADMIN) ── si no ──► 403 ; sin sesión ──► 401
   ├─ contrato: al menos 1 renglón, sin libro_id repetido,
   │            cantidad > 0, sin precio/total/fecha (extra="forbid") ──► 422
   ▼
Service.registrar_venta(uow, dto, usuario_actual)
   │
   ├── [TX ABRE]
   │   1. cliente = repo_clientes.get_by_id(cliente_id)      ── None → 409
   │   2. libros  = repo_libros.get_by_ids(libro_ids)        ── faltante → 409
   │      (precarga declarada acá: libro_autor / editorial / genero según la respuesta)
   │   3. por cada libro: borrado_en IS NOT NULL             ── → 409
   │   4. por cada renglón: stock < cantidad                ── → 409
   │   5. venta = repo_ventas.add(cliente_id, total=Σ(cant×precio))   flush()
   │   6. por cada renglón: renglon_venta.add(venta_id, libro_id,
   │                          cantidad, precio_unitario=libro.precio)  flush()
   │   7. por cada renglón: PUNTO ÚNICO DE ESCRITURA DE STOCK (RN-11)
   │         libro.stock -= cantidad
   │         movimiento_stock.add(libro_id, venta_id=venta.id,
   │                              usuario_id=actual.id, cantidad=-cantidad,
   │                              motivo='Venta', cuando=now())        flush()
   ├── [TX COMMIT]  ◄── sólo si TODO salió bien
   │
   └─ background_tasks.add_task(avisar_comprobante, venta.id)
   ▼
201 {precios copiados, total calculado}
```

**Por qué todo o nada**: si el cuarto renglón no alcanza, tienen que desaparecer la venta, los tres
renglones anteriores, los descuentos y los movimientos. El chequeo de stock es una cortesía para dar
un 409 legible; **la garantía es el rollback**.

**El punto único de escritura (RN-11)** es un solo método que hace las dos cosas juntas —mover
`libro.stock` y agregar el `movimiento_stock`— y lo usan los tres caminos: alta con stock inicial,
reposición y venta. Si existiera un camino que toque `stock` sin dejar movimiento, la igualdad
`stock = SUM(cantidad)` se rompería y todos los casos de venta fallarían.

**El aviso del comprobante** se agenda con `BackgroundTasks` **después** del commit: corre una vez
enviada la respuesta, y sólo si la operación se confirmó. `await asyncio.sleep(0.5)` + una línea en el
registro visible con el logging por defecto de uvicorn (C-10, D-08).

**Casos de error**

| Caso | Respuesta | Estado de la base |
|---|---|---|
| Cliente inexistente | 409 | sin cambios |
| Libro inexistente | 409 | sin cambios |
| Libro dado de baja | 409 | sin cambios |
| Stock insuficiente en cualquier renglón | 409 | sin cambios (**ni descuentos parciales**) |
| Libro repetido en `renglones` | 422 | sin cambios |
| `precio` o `total` en el cuerpo | 422 | sin cambios |
| Un CLIENTE lo intenta | 403 | sin cambios |

---

## Flujo 6 — Alta de un libro con stock inicial (RN-01, RN-11)

**Disparador**: `POST /libros`
**Actor**: ADMIN

```
POST /libros {isbn, titulo, precio, stock_inicial, editorial_id, genero_id,
              autores:[{autor_id, rol, orden}]}
   │
   ├─ requiere_rol(ADMIN) ──► 401 / 403
   ├─ contrato: stock NO es un campo; precio > 0; stock_inicial >= 0 ──► 422
   ▼
   ├── [TX ABRE]
   │   libro = repo_libros.add(..., stock = stock_inicial)          flush()
   │   libro_autor.add(...) por cada autor                          flush()
   │   PUNTO ÚNICO: movimiento_stock.add(libro_id, cantidad=stock_inicial,
   │                                    motivo='Stock inicial', venta_id=NULL)
   │      └─ ISBN duplicado entre vigentes → IntegrityError → 409
   ├── [TX COMMIT]
   ▼
201
```

El `stock` nace igual al `stock_inicial` **y** con su movimiento: desde el primer instante se cumple
`stock = SUM(movimiento_stock.cantidad)`. Un ISBN que pertenece a un libro dado de baja **no** choca:
el índice único es parcial.

---

## Flujo 7 — Reponer stock (RN-11, RN-13)

**Disparador**: `POST /libros/{id}/reponer`
**Actor**: ADMIN

```
   ├─ requiere_rol(ADMIN)
   ├─ [TX ABRE]
   │   libro = repo_libros.get_by_id(id)          ── None → 404
   │   si libro.borrado_en IS NOT NULL            ── → 409
   │   PUNTO ÚNICO: libro.stock += cantidad
   │                movimiento_stock.add(cantidad=+cantidad,
   │                                   motivo='Reposición', venta_id=NULL,
   │                                   usuario_id=admin.id)
   ├─ [TX COMMIT]
   ▼
200 libro actualizado
```

`cantidad <= 0` → **422**. La reposición de un libro dado de baja se rechaza (RN-13) aunque el libro
exista: por eso el 409 y no el 404.

---

## Flujo 8 — Baja lógica de un libro (RN-13)

**Disparador**: `DELETE /libros/{id}`
**Actor**: ADMIN

```
   ├─ requiere_rol(ADMIN)
   ├─ [TX ABRE]
   │   libro = repo_libros.get_by_id(id)        ── None → 404  (ya filtra borrados)
   │   repo_libros.soft_delete(libro)           ── escribe borrado_en = now()
   ├─ [TX COMMIT]
   ▼
204
```

**Efectos, en el mismo instante:**

- `SoftDeleteRepository` filtra `borrado_en IS NULL` ⇒ el libro desaparece de `GET /libros`, de
  `GET /libros/{id}` y de los listados por editorial/género/autor.
- Venderlo o reponerlo ⇒ **409**.
- `GET /ventas/{id}` de una venta vieja **sigue mostrando el título**: el renglón apunta a la fila,
  que sigue existiendo (se lee con `get_by_id_including_deleted` / precarga que no filtra).
- El ISBN queda libre: un alta nueva con el mismo ISBN da **201**; un segundo libro **vigente** con
  ese ISBN da **409**.

---

## Flujo 9 — Revocar un rol con la sesión abierta (RN-04, RN-05)

**Disparador**: `DELETE /usuarios/{id}/roles/{rol}`
**Actor**: ADMIN
**Lo que demuestra**: la autorización se decide en la base, no en el token.

```
t0  vendedor@ inicia sesión        → token con roles=["VENDEDOR"], cookie C
t1  admin revoca VENDEDOR          → revocada_en = now()   (la fila NO se borra)
t2  vendedor@ llama POST /libros con LA MISMA cookie C
        get_usuario_actual  → 200 (la identidad no cambió)
        requiere_rol(ADMIN) → consulta asignacion_rol → sin rol vigente → 403
t3  GET /auth/yo con C             → roles de la base: []   ·   roles del token: ["VENDEDOR"]
```

**Detalle de la transacción (t1):**

```
[TX ABRE]
  asignacion = repo_roles.get_vigente(usuario_id, rol)   ── None → 404
  si usuario_id == actual.id y rol == 'ADMIN'            ── → 409 (RN-05)
  si es el último ADMIN vigente                          ── → 409 (RN-05)
  asignacion.revocada_en = now()
  evento_seguridad.add(actor=admin.email, accion="Revocación de rol …")   ← misma TX (RN-16)
[TX COMMIT]
```

**Reasignar un rol vencido** sigue el mismo camino pero cierra y abre:

```
[TX ABRE]
  anterior.revocada_en = now()          ← cierra la fila vieja
  asignacion_rol.add(rol, desde=now(), vence_en=nuevo)   ← abre la nueva
  evento_seguridad.add(...)
[TX COMMIT]
```

Así el índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` nunca se viola.

---

## Flujo 10 — Asignar un rol con vigencia (RN-03)

**Disparador**: `POST /usuarios/{id}/roles`
**Actor**: ADMIN

```
   ├─ requiere_rol(ADMIN)
   ├─ contrato: rol ∈ {ADMIN, VENDEDOR, CLIENTE}
   │            vence_en opcional, CON zona horaria y en el FUTURO
   │            └─ sin zona  → 422   (¿la hora de quién?)
   │            └─ en el pasado → 422  (no choca con nada guardado, pero no tiene sentido)
   ├─ [TX ABRE]
   │   usuario existe?                                   ── None → 404
   │   ¿hay asignación abierta de ese rol?                ── sí → 409 (índice parcial)
   │   asignacion_rol.add(usuario_id, rol, desde=now(), vence_en, otorgada_por=admin.id)
   │   evento_seguridad.add(...)
   ├─ [TX COMMIT]
   ▼
201
```

**Por qué 422 y no 409** para un vencimiento inválido: el 409 es «choca con lo guardado»; una fecha
sin zona o pasada es un **contrato mal formado**, no un conflicto con la base.

---

## Resumen de fronteras transaccionales

| Operación | Transacciones | Regla |
|---|---|---|
| Auto-registro | **1** (usuario + rol + cliente) | RN-02 |
| Alta de personal | **1** (usuario + rol + evento) | RN-16 |
| Login | **1 propia** para `intento_acceso` (siempre commit) + lectura | RN-07 |
| Cambio de contraseña | **1** (usuario + evento) | RN-16 |
| Asignar / revocar rol | **1** (asignación + evento) | RN-03/16 |
| Alta de libro | **1** (libro + libro_autor + movimiento) | RN-11 |
| Reponer | **1** (stock + movimiento) | RN-11 |
| Venta | **1** (venta + renglones + stock + movimientos) | RN-10 |
| Baja de libro | **1** (`borrado_en`) | RN-13 |
| Lecturas (listados, detalle) | 1 sesión, sin escrituras | — |

**La única escritura que no comparte la transacción de su petición es `intento_acceso`**, y es
deliberado.
