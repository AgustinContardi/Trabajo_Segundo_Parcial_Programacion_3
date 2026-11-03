# Preguntas Abiertas

Este documento tiene tres bloques:

1. **Conflictos resueltos** entre la consigna (`docs/Parcial_Cap1a6_Consigna.pdf`, autoritativa) y el
   checklist heredado (`docs/CHECKLIST_ANTES_DE_ENTREGAR.md`, **no autoritativo**).
2. **Columnas heredadas** del TP cap 1-4 que este PDF no restate.
3. **Preguntas realmente abiertas**, priorizadas.

> Regla de desempate aplicada en todo el documento: **gana el PDF**. El checklist se declara a sí
> mismo como plantilla de otro TP («Copiar al repo del próximo TP») y su §0 dice «Ninguna regla de
> negocio que no esté en la consigna».

---

## 1. Conflictos resueltos (checklist ≠ PDF → gana el PDF)

### IN-01 — El dominio: librería, no mantenimiento automotor

**El checklist dice**: un dominio completamente distinto (mantenimiento automotor): sus módulos
(`{health, usuarios, clientes, …}` con dos módulos que no existen acá), su seed (herramientas y
consumibles; «Laura y Jorge» con sus automóviles) y sus reglas (asignación a un responsable técnico,
dueño del automóvil, historial de precio 8000 → 8500).
**El PDF dice**: librería; módulos `health, usuarios, editoriales, generos, autores, libros, clientes,
ventas`; libros Rayuela / Antología / Ficciones / Respiración artificial / Bestiario; ventas con
renglones; `movimiento_stock`.
**Impacto**: el checklist entero de §8 y §9 es inaplicable. Aplicarlo contamina el modelo, el seed y
los casos de prueba — exactamente lo que pasó con la KB anterior.
**Resolución**: **el PDF**. Este documento y los otros diez no usan el vocabulario del dominio
automotor. El checklist sólo aporta convenciones de ingeniería (`CV-01`…`CV-14` en
`05_reglas_de_negocio.md`).

### IN-02 — El sólo agregado: una tabla, no tres

**El checklist dice**: «Solo-agregado: triggers bloquean `UPDATE` y `DELETE` en **las tres** tablas»
(historial de precios, movimientos de stock y otra del dominio automotor).
**El PDF dice**: RN-12, **sólo** `movimiento_stock`; y la cuarta migración instala **un** disparador.
**Impacto**: crear disparadores de más rompe migraciones y confunde la corrección de RN-12.
**Resolución**: **un solo disparador, sobre `movimiento_stock`**. C-14 prueba exactamente eso.

### IN-03 — Cambiar la contraseña **no** rota la cookie

**El checklist dice**: «`/auth/cambiar-password` **entrega cookie nueva**; la anterior da 401».
**El PDF dice**: «cambiar la contraseña **no invalida las sesiones abiertas ni emite un token
nuevo**»; y C-09 exige: «después del cambio, `debe_cambiar_password` queda en falso y **la misma
cookie** sirve para las rutas protegidas (200), sin iniciar sesión de nuevo».
**Impacto**: implementar la rotación **hace fallar C-09** y contradice el Ejercicio 4.
**Resolución**: **el PDF**. La cookie se mantiene; el estado que cambia (`debe_cambiar_password`) vive
en la base y se relee en cada petición. Ver flujo 4 en `07_flujos_principales.md`.

### IN-04 — El `.zip` tiene dos carpetas, no una

**El checklist dice**: un solo proyecto empaquetado, con `requirements.txt`, `alembic.ini`,
`migrations/`, `test/`, `tests/`, `seed.py`, `main.py`.
**El PDF dice**: el `.zip` contiene **dos carpetas** porque son dos proyectos distintos: `parcial/` y
`despliegue/`.
**Impacto**: entregar una sola carpeta deja el criterio de despliegue (18 %) sin material.
**Resolución**: **el PDF**. `parcial/` lleva el proyecto ampliado (sin el despliegue); `despliegue/`
lleva el TP cap 1-4 + `Dockerfile` + `.dockerignore` + `env.example` + `DEPLOY.md` + `evidencia/`.
Ver `11_despliegue_y_devops.md`.

### IN-05 — No existe `GET /health`; existen `/health/live` y `/health/ready`

**El checklist dice**: «`GET /health`» como ruta de salud.
**El PDF dice**: `GET /health/live` (no toca la base) y `GET /health/ready` (`SELECT 1`; 503 si la
base no contesta).
**Impacto**: el `HEALTHCHECK` de la imagen del despliegue apunta a `/health/ready`; con `/health`
daría 404 y el contenedor quedaría `unhealthy`.
**Resolución**: **el PDF**. `/health/live` para vida, `/health/ready` para disponibilidad.

### IN-06 — No hay `password_cambiada_en` ni comparación de `iat`

**El checklist dice**: «`iat` y `exp` numéricos (NumericDate); comparar con `password_cambiada_en` sin
truncar».
**El PDF dice**: el token lleva `sub`, `exp` y los roles; **no** hay columna `password_cambiada_en` en
el modelo de dominio, y el cambio de contraseña no invalida sesiones (IN-03).
**Impacto**: una columna inventada rompe el modelo obligatorio y agrega una regla que no existe
(«cambiar la contraseña expulsa sesiones»).
**Resolución**: **el PDF**. Sin `password_cambiada_en`, sin comparación de `iat`. `exp` se valida con
PyJWT y nada más.

### IN-07 — El seed es el de la librería

**El checklist dice**: «carga el catálogo de estados primero», un segundo usuario del área técnica,
«Laura (con usuario y dos automóviles) y Jorge», cuatro consumibles con sus cantidades, «orden 1
PENDIENTE y 2 EN_PROCESO», «historial de precio 8000 → 8500».
**El PDF dice**: 5 usuarios (`admin`, `admin2`, `vendedor`, `ana`, `nuevo`), 3 editoriales, 3 géneros,
6 autores, 5 libros con sus stocks, 3 clientes (Lucía con perfil, Tomás sin usuario, Ana con usuario),
la venta 1 (1 Rayuela + 2 Ficciones = 69000.00) y un «Stock inicial» por libro.
**Impacto**: cualquier dato del checklist hace fallar C-01…C-16, que asumen los ids y los totales del
PDF.
**Resolución**: **el PDF**, al pie de la letra. Ver `04_modelo_de_datos.md` § Seed.

### IN-08 — `CHECK` de dominio: cuáles y con qué valores

**El checklist dice**: «`CHECK` de dominio (año, precios, stock, cantidades, **total**)».
**El PDF dice**: `precio > 0`, `stock >= 0`, `cantidad <> 0`. **No** pide `CHECK` sobre `venta.total`
ni sobre un «año» (ese campo puede ni existir en el TP de la librería).
**Impacto**: un `CHECK` de más puede rechazar datos válidos o complicar el `downgrade`.
**Resolución**: **el PDF**. Los tres `CHECK` nombrados; los del TP que ya existan se conservan.
`venta.total` no lleva `CHECK` porque el total se calcula en el servicio y siempre es ≥ 0 por
construcción (`Suposición`, sin impacto en los casos).

### IN-09 — `tests/` con pytest no está en la consigna (pero se conserva)

**El checklist dice**: «`tests/` solo pytest» y «un test por cada caso C-NN».
**El PDF dice**: `test/` con archivos `.http` y `solo_agregado.sql`; el formato de entrega menciona
`test/` y no `tests/`.
**Impacto**: ninguno si conviven: los `.http` son la evidencia exigida, pytest es una red de
seguridad del grupo.
**Resolución**: **el PDF manda sobre lo exigido** (`test/*.http` es lo que se corrige); `tests/` se
conserva como práctica interna, registrado como `RD-01` («no está en la consigna»). No se presenta
como requisito.

### IN-10 — Orden de errores 404 → 403 → 409 → 422

**El checklist dice**: «Códigos: 404 → 403 → 409 → 422, en ese orden» y «permiso antes que estado».
**El PDF dice**: los códigos permitidos por endpoint (201/204/404/409/422/401/403/429), sin fijar un
orden de evaluación.
**Impacto**: bajo; es una convención de implementación compatible con el PDF.
**Resolución**: se conserva como **`CV-08`**, no como regla de negocio. Donde el PDF es explícito
(por ejemplo `/ventas/{id}`: «primero quién es y qué relación tiene con la venta (403), y recién
después qué se devuelve»), manda el PDF.

### IN-11 — Nombres de variables de entorno

**El checklist dice**: `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `BCRYPT_ROUNDS`,
`BCRYPT_MAX_CONCURRENCY`, `LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`, `POOL_SIZE`.
**El PDF dice**: los conceptos (clave de firma, costo bcrypt, tamaño del pool, umbral y ventana) y los
nombres `POSTGRES_*` y `SQL_ECHO`; **no** fija los nombres de los demás.
**Impacto**: ninguno funcional; sí de coherencia entre `env.example`, `Settings` y `DEPLOY.md`.
**Resolución**: se usan los nombres del checklist como **`CV-09`**, porque no contradicen el PDF y ya
están en el ecosistema del grupo. Los valores 5 y 60 son de la consigna.

### IN-12 — `env.example` sin punto y `.env` fuera del repo y del zip

**El checklist dice**: «`env.example` (sin punto inicial)». **El PDF dice**: «un `env.example` con
todas las variables y ningún secreto», y el `.zip` «no lleva el archivo `.env`».
**Resolución**: coinciden. Se registra acá sólo para dejar constancia de que `env.example` **no** se
renombra a `.env.example`.

---

## 2. Columnas heredadas del TP cap 1-4: qué falta confirmar

La consigna dice: «Las tablas que no aparecen en esta sección (`editorial`, `genero`, `autor`,
`libro_autor` y `perfil_cliente`) **no cambian respecto del TP**», y el modelo de dominio sólo imprime
las columnas **nuevas o cambiadas**. Todo lo demás hay que leerlo del repositorio del TP.

| Tabla | Lo que el PDF confirma | Lo que queda `(heredado TP cap 1-4 — confirmar contra el repo)` |
|---|---|---|
| `editorial` | `id`, `nombre` UNIQUE | Cualquier otra columna (país, sitio, etc.) |
| `genero` | `id`, `nombre` UNIQUE | Cualquier otra columna |
| `autor` | `id` | `nombre`, `apellido`, nacionalidad, cualquiera |
| `libro` | `id`, `isbn`, `titulo`, `precio`, `stock`, `editorial_id`, `genero_id`, `borrado_en` | año, páginas, sinopsis, tapa, `created_at`, etc. **y el tipo de `id`** |
| `libro_autor` | `libro_id`, `autor_id`, `rol`, `orden` | La PK/UNIQUE compuesta y si hay columnas extra |
| `cliente` | `id`, `email` UNIQUE, `usuario_id` | `nombre`, `apellido`, `telefono`, `created_at` |
| `perfil_cliente` | `id`, `cliente_id` (1—1) | `direccion`, `fecha_nacimiento`, `cuit`, cualquiera |
| `venta` | `id`, `cliente_id`, `fecha`, `total` | **si existe `usuario_id` (vendedor)** y `numero`/comprobante |
| `renglon_venta` | `id`, `venta_id`, `libro_id`, `cantidad` | **el nombre exacto de la columna del precio copiado** (`precio_unitario` es SU-08) y si hay `subtotal` |

**Cómo cerrarlo**: `git log`/`alembic history` del repo del TP cap 1-4, o el `.sql` de las migraciones
1 y 2. Mientras no se cierre, las migraciones nuevas **no deben** redefinir esas columnas: sólo
agregar las indicadas.

---

## 3. Preguntas realmente abiertas

| ID | Prioridad | Pregunta | Bloquea | Decisor |
|---|---|---|---|---|
| **AB-01** | Alta | ¿`POST /usuarios` recibe el rol inicial en el cuerpo o se asigna con un `POST /usuarios/{id}/roles` inmediatamente después? (SU-02) | Implementación de US-010 y el `.http` de alta de personal | Cátedra / grupo |
| **AB-02** | Alta | ¿`venta` tiene columna de vendedor (`usuario_id`) o el dato «registrada por» vive sólo en `movimiento_stock.usuario_id`? (SU-07) | El seed y el detalle de venta | Repo del TP cap 1-4 |
| **AB-03** | Media | El intento que recibe **429**, ¿se anota en `intento_acceso` como fallo? La consigna dice «cada intento, correcto o fallido, se anota», pero RN-07 cuenta fallos de verificación | El `.http` de C-05 (¿5 o 6 filas?) | Cátedra |
| **AB-04** | Media | ¿`GET /libros/{id}` de un libro dado de baja devuelve 404 o 200 con marca? (SU-14) | Un caso de C-13 | Cátedra |
| **AB-05** | Media | ¿Qué devuelve `/mis-ventas` para un usuario autenticado **sin** ficha de cliente (un VENDEDOR)? (SU-05) | Un borde de RN-14 | Cátedra |
| **AB-06** | Media | Nombre exacto de la columna del precio copiado en `renglon_venta` (SU-08) | Contratos de salida y casos que comparan JSON | Repo del TP |
| **AB-07** | Baja | ¿`otorgada_por` es FK a `usuario` o texto libre? (SU-03) | Índices de la tercera migración | Repo del TP / figura 1 |
| **AB-08** | Baja | Vocabulario exacto de `movimiento_stock.motivo` (SU-04) | Cosmético, salvo el literal «Stock inicial» | Cátedra |
| **AB-09** | Baja | ¿`PATCH /libros/{id}` puede modificar también `editorial_id`, `genero_id` o autores, o sólo título y precio? La tabla dice «(título y precio; el stock no)» | Alcance de US-024 | Cátedra |
| **AB-10** | Baja | ¿`vence_en` igual a «ahora» cuenta como vencido? (`>` vs `>=`) | Un borde de RN-04 | Equipo |
| **AB-11** | Baja | ¿El vencimiento de un rol genera una línea en `evento_seguridad`? RN-16 nombra altas, cambios de rol y cambios de contraseña | Cosmético | Equipo |

### Notas sobre las respuestas provisionales

- **AB-01**: mientras no haya respuesta, la implementación más segura es aceptar el rol en el cuerpo
  (una sola llamada, un solo UoW, una sola línea de auditoría) y **documentarlo en el README del
  parcial**. Si la cátedra espera dos llamadas, el endpoint de asignación ya existe y el flujo se
  puede partir sin cambiar el modelo.
- **AB-03**: se recomienda **anotar** el 429 (la consigna dice «cada intento») y dejar que el conteo
  de RN-07 siga mirando los fallos de verificación. C-05 sigue pasando: los cinco fallos están en la
  tabla.
- **AB-10**: se adopta `vence_en > now()` como «vigente», que es la lectura literal de «sin vencer».

---

## 4. Campos de discovery inferidos (no hubo fase de investigación)

No se ejecutó `discovery-research`; los seis campos de `kb.discovery` se infirieron de este mismo
corpus. Se deja constancia para que nadie los lea como un dato de mercado:

| Campo | Valor inferido | Confianza | Base |
|---|---|---|---|
| `problem` | Digitalizar la operación de una librería con acceso por roles, ventas transaccionales y despliegue | Alta | Objetivos, p. 1-3 |
| `system_type` | `api` (monolito modular API-first, FastAPI async) | Alta | Estructura obligatoria, p. 8-9 |
| `domain` | librería (ventas de libros) con acceso, transacciones y despliegue | Alta | Contexto, p. 3 |
| `scale` | `team` — single-tenant, un grupo, decenas de usuarios, sin multi-tenant | Media | Roles y seed; el PDF no habla de escala |
| `stack` | Python 3.12, FastAPI, SQLModel, SQLAlchemy async, asyncpg, PostgreSQL 16, Alembic, pydantic-settings, bcrypt, PyJWT, uvicorn, Docker | Alta | Requisitos técnicos, p. 3-4 |
| `needs_infra` | `true` | Alta | PostgreSQL + Docker + VPS |

`scale = team` es el único campo con confianza media: el PDF no describe volumen ni concurrencia
(la concurrencia está **fuera de alcance**).
