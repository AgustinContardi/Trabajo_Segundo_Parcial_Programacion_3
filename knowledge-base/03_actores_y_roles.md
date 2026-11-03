# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Visitante | Cualquiera sin sesión iniciada | `GET /libros`, `GET /libros/{id}`, `GET /editoriales`, `GET /generos`, `GET /{entidad}/{id}/libros`, `POST /auth/registro`, `POST /auth/login` |
| CLIENTE | Persona con acceso web y ficha `cliente` ligada por `usuario_id` | `GET /auth/yo`, `POST /auth/cambiar-password`, `GET /ventas/{id}` sólo de lo propio, `GET /mis-ventas` |
| VENDEDOR | Personal de mostrador | Todo lo del catálogo público + alta y edición de clientes y perfiles + alta de ventas + listado de ventas |
| ADMIN | Administrador del sistema | Todo lo del vendedor + mantenimiento del catálogo (editoriales, géneros, autores, libros), stock (alta con stock inicial, reposición, baja), administración de personal y roles, historial de seguridad |
| SISTEMA | **Actor textual** (`evento_seguridad.actor = 'SISTEMA'`), no es un usuario | Escribe líneas de auditoría en operaciones sin usuario humano (seed: «Carga de los datos iniciales») |

Notas:

- El catálogo es **público**: ver libros no requiere sesión.
- `intento_acceso` no tiene actor: es una fila por intento de login, con `email`, `ip`, `cuando` y
  `exito`; no está asociada a ninguna otra tabla.
- `evento_seguridad.actor` es **texto**, no una FK a `usuario`: por eso puede valer `SISTEMA` y por
  eso la tabla no tiene ninguna relación (`RN-16`, sección 5.8 de la consigna).

## Los roles viven en su propia tabla

`usuario` **no tiene una columna `rol`**. Los roles de una persona son las filas de `asignacion_rol`
que están **vigentes**: no revocadas (`revocada_en IS NULL`) y sin vencer (`vence_en IS NULL OR
vence_en > now()`).

```sql
-- Rol vigente de un usuario (lo que consulta requiere_rol en cada petición)
SELECT rol FROM asignacion_rol
 WHERE usuario_id = :id
   AND revocada_en IS NULL
   AND (vence_en IS NULL OR vence_en > now());
```

Consecuencias directas:

- **RN-04**: los permisos se deciden con los roles vigentes **en la base, en cada petición**. Los
  roles que trae el token son **informativos** (`GET /auth/yo` los muestra para que se vea la
  diferencia).
- Revocar un rol **no borra la fila**: escribe `revocada_en`. Queda el historial de quién tuvo qué
  rol y hasta cuándo.
- Un usuario tiene **a lo sumo una asignación abierta por rol** (índice único parcial
  `(usuario_id, rol) WHERE revocada_en IS NULL`, RN-03).
- Reasignar un rol vencido **cierra la fila anterior y abre una nueva**.
- Un usuario puede tener **varios roles vigentes a la vez** (por ejemplo ADMIN y VENDEDOR): la
  autorización es «alguno de los roles exigidos».

### Estados de una fila de `asignacion_rol`

| Estado | Condición | Efecto |
|---|---|---|
| Vigente | `revocada_en IS NULL` y (`vence_en IS NULL` o `vence_en > now()`) | Otorga el permiso |
| Vencida | `vence_en <= now()` y sin revocar | No otorga permiso; la fila se conserva |
| Revocada | `revocada_en IS NOT NULL` | No otorga permiso; la fila se conserva para siempre |
| Cerrada por reasignación | `revocada_en` escrito al abrir una nueva del mismo rol | Igual que revocada |

## RBAC — Matriz de permisos

Leyenda: **A** = ADMIN, **V** = VENDEDOR, **C** = CLIENTE, **—** = sin sesión (público),
**Auth** = cualquier usuario autenticado, **Dueño** = el cliente dueño del recurso.

| Recurso | Operación | — | C | V | A | Notas |
|---|---|---|---|---|---|---|
| `/health/live` | GET | ✅ | ✅ | ✅ | ✅ | No toca la base |
| `/health/ready` | GET | ✅ | ✅ | ✅ | ✅ | `SELECT 1`; 503 si la base no contesta |
| `/auth/registro` | POST | ✅ | — | — | — | Crea usuario + rol CLIENTE + ficha cliente (RN-02) |
| `/auth/login` | POST | ✅ | ✅ | ✅ | ✅ | Rate limit antes de verificar (RN-07/RN-08) |
| `/auth/logout` | POST | ✅ | ✅ | ✅ | ✅ | Borra la cookie |
| `/auth/yo` | GET | ❌ 401 | ✅ | ✅ | ✅ | Devuelve roles de la base **y** los del token |
| `/auth/cambiar-password` | POST | ❌ 401 | ✅ | ✅ | ✅ | No rota la cookie (ver `10_preguntas_abiertas.md`) |
| `/libros` (GET, listado y detalle) | GET | ✅ | ✅ | ✅ | ✅ | Excluye los dados de baja |
| `/editoriales`, `/generos`, `/{x}/{id}/libros` | GET | ✅ | ✅ | ✅ | ✅ | Público |
| `/usuarios` | POST | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Alta de personal con contraseña provisoria |
| `/usuarios/{id}/roles` | GET, POST | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Asignar / listar asignaciones |
| `/usuarios/{id}/roles/{rol}` | DELETE | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Revoca sin borrar; autoprotección RN-05 |
| `/eventos` | GET | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Historial de seguridad paginado |
| `/editoriales`, `/generos`, `/autores` | POST | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Alta de catálogo |
| `/editoriales/{id}`, `/autores/{id}` | PATCH | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | PATCH parcial |
| `/libros` | POST | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Con `autores` y `stock_inicial` |
| `/libros/{id}` | PATCH | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Sólo título y precio; `stock` en el cuerpo → 422 |
| `/libros/{id}` | DELETE | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Baja lógica → 204 |
| `/libros/{id}/reponer` | POST | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Deja movimiento de entrada |
| `/libros/{id}/movimientos` | GET | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | Trazabilidad del stock |
| `/clientes` | POST | ❌ 401 | ❌ 403 | ✅ | ✅ | Alta de cliente de mostrador |
| `/clientes/{id}` | GET, PATCH | ❌ 401 | ❌ 403 | ✅ | ✅ | Con su perfil |
| `/clientes/{id}/perfil` | POST | ❌ 401 | ❌ 403 | ✅ | ✅ | 201 / 404 / 409 |
| `/clientes/{id}/ventas` | GET | ❌ 401 | ❌ 403 | ✅ | ✅ | Ventas del cliente |
| `/ventas` | POST | ❌ 401 | ❌ 403 | ✅ | ✅ | Con `renglones`; precios y total los pone el servidor |
| `/ventas` | GET | ❌ 401 | ❌ 403 | ✅ | ✅ | Listado paginado |
| `/ventas/{id}` | GET | ❌ 401 | Dueño ✅ / ajeno 403 | ✅ | ✅ | **Sin `requiere_rol`**: decide el servicio |
| `/mis-ventas` | GET | ❌ 401 | ✅ | ✅ | ✅ | RN-14: sólo lo propio |

## Por qué `/ventas/{id}` no lleva `requiere_rol`

Un cliente puede ver su propia venta y **no tiene un rol de personal**. Si la ruta exigiera
`VENDEDOR` o `ADMIN`, el dueño recibiría «no tenés permiso» cuando sí lo tiene. La decisión la toma el
**servicio**: primero quién es y qué relación tiene con la venta (403 si no es ni personal ni dueño),
y recién después qué se devuelve.

## Rutas públicas (sin sesión)

```
GET  /health/live
GET  /health/ready
POST /auth/registro
POST /auth/login
POST /auth/logout
GET  /libros
GET  /libros/{id}
GET  /editoriales
GET  /generos
GET  /editoriales/{id}/libros
GET  /generos/{id}/libros
GET  /autores/{id}/libros
```

`GET /auth/yo` y `POST /auth/cambiar-password` están en el **grupo abierto de rutas** (el que no
lleva el control del cambio obligatorio) pero **sí exigen sesión**: sin cookie o con token inválido
responden 401.

## Dos grupos de rutas, un solo control

`main.py` monta **dos grupos**:

1. **Abierto**: `/health/*`, `/auth/*`, catálogo público. Sin el control del cambio obligatorio.
2. **Protegido**: todo lo demás. Lleva el control del cambio obligatorio de contraseña montado
   **una sola vez** (una dependencia a nivel de router).

La razón es que FastAPI **suma** dependencias y **no las resta**: si el control se aplicara ruta por
ruta, no habría forma de eximir `/auth/cambiar-password`, que es justamente la ruta con la que se sale
del estado pendiente (RN-06).

## 401 vs 403 — regla dura

| Situación | Código | Quién lo decide |
|---|---|---|
| Sin cookie, token inválido o vencido, usuario inexistente o inactivo | **401** | `get_usuario_actual` |
| Autenticado pero sin el rol exigido | **403** | `requiere_rol` |
| Autenticado con cambio de contraseña pendiente, en ruta protegida | **403** | control del grupo protegido (RN-06) |
| Autenticado pero el recurso no es propio (ni es personal) | **403** | el servicio (RN-14) |

Nunca se usa 403 para «no sé quién sos» ni 401 para «sé quién sos y no podés».
