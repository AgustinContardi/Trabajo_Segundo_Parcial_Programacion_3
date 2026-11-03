# Decisiones y Supuestos

> `DD` = decisión **documentada en la consigna** (no es discutible: está en el PDF).
> `SU` = **suposición** inferida por este documento. Toda `SU` tiene riesgo y forma de validarse.

---

## Decisiones documentadas

### DD-01 — Organización por módulo funcional, con seis capas en cada uno

**Decisión**: `app/modules/<módulo>/{models,schemas,repository,unit_of_work,service,router}.py`, más
`app/core/` transversal. Módulos mínimos: `health`, `usuarios`, `editoriales`, `generos`, `autores`,
`libros`, `clientes`, `ventas`.
**Contexto**: la consigna compara el proyecto contra una estructura obligatoria.
**Alternativas consideradas**: agrupar por capa técnica (`services/`, `repositories/`), habitual en
proyectos chicos.
**Justificación**: la corrección entra por módulo; `health` sólo tiene `router.py`; las entidades se
asignan a un módulo fijo (por ejemplo `MovimientoStock` vive en `libros`).
**Trade-offs**: más archivos y más `__init__.py`; imports algo más largos.

### DD-02 — Los roles viven en su propia tabla (`asignacion_rol`)

**Decisión**: `usuario` **no** tiene columna `rol`. Los permisos salen de las filas **vigentes** de
`asignacion_rol` (no revocadas y sin vencer).
**Contexto**: hacen falta tres roles, vigencia e historial de quién tuvo qué y hasta cuándo.
**Alternativas consideradas**: `usuario.rol` (simple, sin historial) y una tabla `rol` normalizada.
**Justificación**: con una columna no se puede cumplir RN-03 (una asignación abierta por rol), RN-04
(leer de la base en cada petición) ni RN-05 (nunca sin administradores). El índice único **parcial**
`(usuario_id, rol) WHERE revocada_en IS NULL` resuelve la unicidad sin impedir el historial.
**Trade-offs**: una consulta extra por petición autenticada y un JOIN más en `/auth/yo`.

### DD-03 — El ISBN es único **entre los vigentes**

**Decisión**: se reemplaza el `UNIQUE(isbn)` por un índice único parcial `(isbn) WHERE borrado_en IS
NULL`.
**Contexto**: la baja es lógica; un `UNIQUE` común impediría volver a cargar un ISBN dado de baja y la
base respondería «ya existe» de un libro que no aparece en ningún listado.
**Alternativas consideradas**: borrar físicamente (rompe las ventas viejas); `UNIQUE(isbn,
borrado_en)` (permite un solo borrado por ISBN, y `NULL` no colisiona como se espera).
**Justificación**: misma herramienta que `asignacion_rol`; es lo que la consigna pide explícitamente.
**Trade-offs**: la unicidad deja de ser una propiedad global del ISBN: hay que recordar que sólo
aplica a los vigentes.

### DD-04 — El sólo agregado se impone con un disparador en la cuarta migración

**Decisión**: función + `TRIGGER` que rechaza `UPDATE` y `DELETE` sobre `movimiento_stock`, escrito **a
mano** en la cuarta migración.
**Contexto**: Alembic no ve funciones ni disparadores en la comparación automática.
**Alternativas consideradas**: un rol de base sin permiso de escritura sobre la tabla (mecanismo
alternativo de la sección 6.9).
**Justificación**: la consigna dice que «cualquiera de los dos alcanza» y que el parcial usa un solo
rol de base, así que el disparador es el camino pedido. Tener los dos sería defensa en profundidad.
**Trade-offs**: un `UPDATE` legítimo de mantenimiento también se rechaza; corregir exige compensar.

### DD-05 — `intento_acceso` se escribe en su propia transacción

**Decisión**: cada intento de login se anota desde **una sesión y una transacción propias, que se
confirman siempre**.
**Contexto**: el fallo que se quiere contar es el mismo que revierte la transacción de la petición.
**Alternativas consideradas**: escribir el intento dentro del UoW del login (se perdería en el
rollback del 401).
**Justificación**: es la única escritura del sistema que no comparte la transacción de su petición, y
eso es deliberado. El código lleva un comentario con qué hace distinto, por qué no puede compartir la
transacción y su costo (**deja filas aunque la petición falle**).
**Trade-offs**: filas huérfanas cuando la petición falla después; se acepta porque son el insumo de
RN-07.

### DD-06 — Dos grupos de rutas para el cambio obligatorio de contraseña

**Decisión**: `main.py` monta un grupo **abierto** (`/health`, `/auth`, catálogo) y un grupo
**protegido** con el control de RN-06 montado **una sola vez**.
**Contexto**: con `debe_cambiar_password = true`, el usuario sólo puede usar `/auth` y las rutas que
no piden sesión — y `/auth/cambiar-password` es la salida.
**Alternativas consideradas**: aplicar el control ruta por ruta; un middleware que inspeccione el
path.
**Justificación**: **FastAPI suma dependencias y no las resta**. Un control global obligaría a
exceptuar paths a mano, que es exactamente lo que la consigna evita.
**Trade-offs**: hay que mantener la lista de rutas en el grupo correcto; una ruta nueva mal ubicada
queda sin control.

### DD-07 — El token viaja sólo en una cookie y el cambio de contraseña no la rota

**Decisión**: JWT en cookie `access_token` (`HttpOnly`, `SameSite=Lax`, `Max-Age`, `Secure`
configurable). Cambiar la contraseña **no invalida las sesiones abiertas ni emite un token nuevo**.
**Contexto**: «Es un login tradicional con cookie: la sesión dura hasta que el token vence o se cierra
la sesión».
**Alternativas consideradas**: rotar el token al cambiar la contraseña (lo que decía el checklist
heredado).
**Justificación**: el PDF lo dice de forma explícita y el caso C-09 exige que **la misma cookie** sirva
para las rutas protegidas después del cambio.
**Trade-offs**: una contraseña comprometida no expulsa a quien ya tenga sesión; se compensa con el
vencimiento del token.

### DD-08 — El stock entra por `stock_inicial`, no por `stock`

**Decisión**: `POST /libros` recibe `stock_inicial` y deja el movimiento «Stock inicial»;
`PATCH /libros/{id}` acepta **sólo** título y precio.
**Contexto**: RN-11: el stock sólo cambia por movimientos.
**Alternativas consideradas**: aceptar `stock` en el alta sin movimiento (rompe la igualdad
`stock = SUM(movimiento_stock.cantidad)`).
**Justificación**: así la igualdad se cumple desde la primera fila, y `stock` en un `PATCH` da 422.
**Trade-offs**: dos nombres parecidos (`stock` de lectura, `stock_inicial` de escritura) que hay que
no confundir en los DTO.

### DD-09 — Cuatro migraciones en total, la última a mano

**Decisión**: a las migraciones del TP se suman dos: la **tercera autogenerada** (tablas de acceso,
`movimiento_stock`, cambios en `cliente` y `libro`) y la **cuarta escrita a mano** (disparador).
**Contexto**: el esquema se crea exclusivamente con Alembic, y `autogenerate` no ve funciones ni
disparadores.
**Justificación**: cada migración nueva se lee antes de aplicarla y lleva un comentario que lo diga;
`upgrade head` / `downgrade base` / `upgrade head` tienen que funcionar.
**Trade-offs**: `downgrade` de la cuarta tiene que borrar el disparador **y** la función, o el
`downgrade base` falla.

### DD-10 — Repositorios + Unit of Work; el router construye y el servicio abre

**Decisión**: `BaseRepository[T]` y `SoftDeleteRepository[T]`; un UoW por módulo; el router construye
el UoW con una dependencia y lo pasa sin abrirlo; el servicio lo abre con `async with`.
**Contexto**: los servicios dejan de recibir la sesión.
**Justificación**: un solo lugar decide commit/rollback (`__aexit__`); ningún repositorio confirma;
ningún servicio construye su UoW.
**Trade-offs**: más indirección para operaciones triviales de una sola escritura.

### DD-11 — Las ventas no se modifican

**Decisión**: no existe `PATCH /ventas/{id}` y el precio/total nunca viajan en el cuerpo.
**Contexto**: RN-09.
**Justificación**: una venta es un documento; corregirla obligaría a compensaciones contables que el
parcial no pide.
**Trade-offs**: un error de carga sólo se corrige con una venta nueva.

### DD-12 — `/health/live` y `/health/ready` separados

**Decisión**: dos endpoints; el segundo hace `SELECT 1` y responde 503 si la base no contesta.
**Contexto**: el proceso puede estar vivo y no estar listo; reiniciarlo no arregla una base caída.
**Trade-offs**: dos rutas que mantener y un `HEALTHCHECK` que debe apuntar a la correcta.

### DD-13 — `BackgroundTasks` en lugar de una cola

**Decisión**: el aviso del comprobante se agenda con `BackgroundTasks`, `await asyncio.sleep(0.5)` y
una línea de registro.
**Contexto**: no se evalúan colas con Redis (capítulo 8).
**Trade-offs**: si el proceso se reinicia, el aviso se pierde y nadie lo reintenta. Aceptado porque el
aviso es simulado.

### DD-14 — La concurrencia queda fuera de alcance

**Decisión**: no se implementa bloqueo. Dos ventas simultáneas del último ejemplar pueden leer las dos
`stock = 1` y escribir las dos `0` (actualización perdida).
**Contexto**: capítulo 7, explícitamente fuera de la evaluación; el `CHECK (stock >= 0)` impide el
stock negativo pero no la pérdida.
**Trade-offs**: se puede vender un ejemplar inexistente bajo concurrencia real. Documentado, no
parcheado.

### DD-15 — El despliegue es un proyecto aparte

**Decisión**: `despliegue/` contiene el TP de los capítulos 1 a 4 **tal como se entregó**, con
`Dockerfile` y `.dockerignore` como únicos agregados. Sin Compose, sin base de datos adentro.
**Contexto**: la consigna separa «esta consigna es lo que se entrega en el repositorio; la siguiente,
lo que tiene que estar en línea».
**Justificación**: el despliegue demuestra el capítulo de contenedores sobre un proyecto que ya
funcionaba; mezclarlo con el parcial haría imposible atribuir errores.
**Trade-offs**: el `Dockerfile` **no** sirve para el código nuevo (`parcial/`), porque ese código tiene
otras rutas y otras migraciones.

### DD-16 — `evento_seguridad.actor` es texto, no una FK

**Decisión**: `actor` guarda un email o `'SISTEMA'`; la tabla no tiene relaciones.
**Contexto**: el seed y las operaciones automáticas no tienen un usuario humano.
**Trade-offs**: se pierde integridad referencial en la auditoría; se gana poder registrar `SISTEMA`.

### DD-17 — Contratos separados, `extra="forbid"`

**Decisión**: un schema por operación, separado del modelo de tabla; los campos no declarados se
rechazan con 422.
**Contexto**: «de modo que nadie se registra con un rol ni edita el stock por PATCH».
**Trade-offs**: cada campo nuevo exige tocar el schema, no sólo el modelo.

### DD-18 — Listados con envoltorio

**Decisión**: `{items, total, page, size, pages}` en lugar de `limit`/`offset`; `page` desde 1, `size`
1..100 (default 20), página fuera de rango → 422, cero resultados → una página vacía.
**Trade-offs**: una consulta extra de `count` por listado.

---

## Supuestos inferidos

### SU-01 — Tipo de las claves primarias

**Supuesto**: `id` es entero autoincremental (`bigint identity`), como en el TP.
**Origen**: la consigna fija **nombres** de columnas, no tipos.
**Riesgo si es falso**: bajo; afecta migraciones y FKs, no los casos funcionales.
**Cómo validar**: mirar las migraciones existentes del TP cap 1-4 en el repo del grupo.

### SU-02 — `POST /usuarios` recibe el rol inicial

**Supuesto**: el alta de personal acepta un campo de rol (`ADMIN` o `VENDEDOR`) además de email,
nombre y contraseña provisoria.
**Origen**: el endpoint está descripto como «alta de personal» y `GET/POST /usuarios/{id}/roles`
existe aparte; sin rol inicial el usuario no podría hacer nada hasta una segunda llamada.
**Riesgo si es falso**: el caso de alta de personal necesitaría dos llamadas (alta + asignación).
**Cómo validar**: preguntar a la cátedra o revisar si la corrección asigna el rol por separado.
**Mitigación**: si el cuerpo no llevara rol, el servicio puede crear el usuario **sin** asignación y
el ADMIN asigna en el paso siguiente; ninguna regla se rompe.

### SU-03 — `otorgada_por` es FK a `usuario.id`

**Supuesto**: `asignacion_rol.otorgada_por` referencia al administrador que otorgó el rol, y por eso
lleva índice.
**Origen**: la consigna marca explícitamente «`actor` (texto)» para `evento_seguridad` y **no** lo hace
para `otorgada_por`; el contraste sugiere que el segundo es una FK. Además «cada clave foránea nueva
lleva un índice».
**Riesgo si es falso**: si fuera texto libre, sobra una FK y un índice.
**Cómo validar**: figura 1 del PDF (modelo completo), que no se pudo leer como texto.

### SU-04 — Vocabulario de `movimiento_stock.motivo`

**Supuesto**: se usa `'Stock inicial'`, `'Reposición'` y `'Venta'`.
**Origen**: la consigna nombra «Stock inicial» textualmente y describe los otros dos caminos.
**Riesgo si es falso**: sólo cosmético; ningún caso compara el literal salvo, quizá, el del alta.
**Cómo validar**: revisar si el TP cap 1-4 ya tenía una convención de motivos.

### SU-05 — `/mis-ventas` de un usuario sin ficha de cliente

**Supuesto**: devuelve una página vacía (200) en lugar de 404 o 403.
**Origen**: RN-14 dice que «lo propio sólo pide estar autenticado»; un VENDEDOR autenticado no tiene
`cliente.usuario_id`.
**Riesgo si es falso**: un caso podría esperar 403.
**Cómo validar**: no está en los casos C; consultar a la cátedra si se quiere cerrar.

### SU-06 — `Secure` de la cookie según entorno

**Supuesto**: `COOKIE_SECURE` vale `true` en producción/VPS y `false` en `http://localhost`, porque con
`Secure=true` el navegador no manda la cookie por HTTP plano y los casos locales fallarían.
**Origen**: la consigna dice «`Secure` configurable» sin fijar el default.
**Riesgo si es falso**: los `.http` locales dejan de autenticar.
**Cómo validar**: probar el login local con `Secure=true` y ver si la cookie viaja.

### SU-07 — `venta` guarda quién la registró

**Supuesto**: existe una columna en `venta` (probablemente `usuario_id`) que identifica al vendedor,
heredada del TP o agregada acá.
**Origen**: el seed dice «la venta 1, de Lucía, **registrada por `vendedor@example.com`**» y
`movimiento_stock` sí tiene `usuario_id`, pero el modelo de dominio **no** lista `venta` como tabla que
cambia.
**Riesgo si es falso**: el seed no puede expresar «registrada por» en `venta`; el dato quedaría sólo
en `movimiento_stock.usuario_id`.
**Cómo validar**: ver las migraciones del TP cap 1-4 en el repo.
**Ver también**: `AB-02` en `10_preguntas_abiertas.md`.

### SU-08 — Nombre de la columna del precio copiado

**Supuesto**: `renglon_venta.precio_unitario`.
**Origen**: RN-09 exige «el precio de cada renglón copiado del libro», pero el PDF no imprime el
nombre de esa columna.
**Riesgo si es falso**: los casos que comparan el JSON podrían no coincidir en la clave.
**Cómo validar**: migraciones del TP cap 1-4.

### SU-09 — Nombres de archivo de las migraciones 1 y 2

**Supuesto**: las dos migraciones del TP ya existen con sus revisiones; las nuevas se encadenan a
`head`.
**Origen**: la consigna dice «a las migraciones del TP se suman dos nuevas».
**Riesgo si es falso**: encadenar mal rompe `upgrade head`.
**Cómo validar**: `alembic history` en el repo del TP.

### SU-10 — FK inexistente en un alta de catálogo → 409

**Supuesto**: `POST /libros` con `editorial_id` o `genero_id` inexistente responde **409** («choca con
lo guardado»), no 404 (el 404 es «el recurso **de la ruta** no existe»).
**Origen**: los códigos declarados para ese endpoint son 201/409/422, sin 404.
**Riesgo si es falso**: un caso esperaría 404.
**Cómo validar**: C-12 dice «cliente o libro inexistente → 409», lo que respalda la lectura.

### SU-11 — El conteo de RN-07 mira los fallos posteriores al último éxito

**Supuesto**: además de la ventana de 60 s, sólo cuentan los fallos del mismo `email` + `ip` que
ocurrieron **después** del último login exitoso de ese par.
**Origen**: «Un login correcto reinicia la cuenta: los fallos anteriores siguen en la tabla, pero
dejan de contar».
**Riesgo si es falso**: un login exitoso seguido de 4 fallos podría bloquear antes de tiempo.
**Cómo validar**: C-05 sólo prueba el camino de 6 fallos seguidos; el reinicio no se prueba
explícitamente.

### SU-12 — `DELETE /usuarios/{id}/roles/{rol}` responde 200 con cuerpo

**Supuesto**: 200 (no 204) con la asignación ya revocada, porque la tabla de endpoints no ofrece 204
para esa ruta.
**Riesgo si es falso**: sólo el código de estado.
**Cómo validar**: tabla de endpoints, p. 17.

### SU-13 — Defaults de configuración no fijados por la consigna

**Supuesto**: `ACCESS_TOKEN_TTL_MIN=30`, `BCRYPT_ROUNDS=12`, `BCRYPT_MAX_CONCURRENCY=4`,
`POOL_SIZE=5`, `SQL_ECHO=false`.
**Origen**: la consigna exige que existan y salgan de la configuración, pero fija sólo los valores de
RN-07 (5 y 60) y el ejemplo de `expira_en_segundos = 1800`.
**Riesgo si es falso**: ninguno funcional; sí de coherencia con `expira_en_segundos`.
**Cómo validar**: el ejemplo de login de la p. 19 implica **1800 s**.

### SU-14 — Un libro dado de baja no se puede ver por el detalle público

**Supuesto**: `GET /libros/{id}` de un libro con `borrado_en` no nulo responde **404**.
**Origen**: RN-13 dice «deja de aparecer en el catálogo»; el detalle público es parte del catálogo.
**Riesgo si es falso**: un caso esperaría 200 con el libro marcado como inactivo.
**Cómo validar**: C-13 sólo verifica el listado.

### SU-15 — `POST /auth/login` con un usuario `activo = false`

**Supuesto**: responde **401**, igual que un usuario inexistente, y **no** 403.
**Origen**: `get_usuario_actual` responde 401 «si el usuario no existe o está inactivo».
**Riesgo si es falso**: mínimo.
**Cómo validar**: Ejercicio 5 de la consigna.
