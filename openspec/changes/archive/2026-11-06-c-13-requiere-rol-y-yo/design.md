# Design — C-13 requiere-rol-y-yo

## Context

Ver `proposal.md` — Why. En `parcial/`, C-11 dejó `get_usuario_actual` autenticando sólo por cookie y `UsuarioRepository.roles_vigentes()` ya consulta `asignacion_rol` con `revocada_en IS NULL` y `vence_en` contra `now()`. Todos los UoW construyen su repositorio con la sesión de `get_session`; FastAPI cachea esa dependencia por petición, pero hoy ningún router de personal la compone con autenticación. `clientes/router.py` no recibe identidad y `ventas/router.py` pasa `None` a `obtener` y `mis_ventas`, por lo que el 403 de C-07 y la decisión de propiedad de `RN-14` no se ejecutan. `main.py` monta todo como grupo abierto; el agrupamiento y el control de cambio obligatorio son C-14.

## Goals / Non-Goals

**Goals:**

- Una única puerta de autorización por rol, `requiere_rol(*roles)`, que lea la base en cada petición y use la misma sesión que el UoW.
- Separar identidad (`get_usuario_actual`, sin roles) de contexto de autorización (`get_sesion_actual`, con roles de base y de token) sin romper el contrato de C-11.
- Cerrar C-07 de punta a punta: dependencia de rol aplicada a las rutas de `clientes` y usuario actual entregado al servicio de `GET /clientes/{id}/ventas`.
- Aplicar la matriz RBAC de la KB a las rutas de personal ya existentes, sin adelantar C-14 ni C-15.
- Dejar `GET /ventas/{id}` y `GET /mis-ventas` con autenticación únicamente y propiedad decidida en el servicio.

**Non-Goals:**

- Control de `debe_cambiar_password`, dos grupos de rutas y `POST /auth/cambiar-password` (C-14).
- Alta de personal, asignación/revocación administrativa de roles, `GET /usuarios/{id}/roles` y `GET /eventos` (C-15).
- `POST /ventas` transaccional y cualquier escritura de venta (C-16).
- `POST /auth/registro` (C-12), migraciones, cambios de esquema, caché de roles, revocación de JWT o rotación de cookie.
- Reagrupar routers en `main.py` o introducir un router protegido global; C-13 sólo agrega dependencias a rutas existentes.

## Decisions

### 1. Contexto de identidad explícito, sin romper `get_usuario_actual`

Se conserva `get_usuario_actual` tal como lo define C-11: cookie → JWT → usuario activo, **sin** consultar roles ni emitir 403. Se agrega `get_sesion_actual` en `dependencies.py`, que devuelve un `IdentidadActual` inmutable con:

- `usuario: Usuario`
- `roles_db: tuple[str, ...]` — vigentes leídos con `UsuarioRepository(session).roles_vigentes(usuario.id)`
- `roles_token: tuple[str, ...]` — claim `roles` del JWT, sólo informativo

`get_sesion_actual` usa `Depends(get_session)` y responde `401` con la misma semántica que `get_usuario_actual` (sin cookie, JWT inválido/vencido, usuario inexistente o inactivo). Para no duplicar la validación, ambos comparten un helper interno de autenticación; `get_usuario_actual` no invoca la lectura de roles.

**Alternativas descartadas:** hacer que `get_usuario_actual` cargue roles (rompe el requisito de C-11 y su prueba de que autenticación no autoriza); decodificar el JWT otra vez en `/auth/yo` (dos ventanas de validación y trabajo duplicado).

### 2. `requiere_rol(*roles)` como fábrica de dependencia

`requiere_rol(*roles)` valida en construcción que haya al menos un rol, normaliza a mayúsculas y devuelve una dependencia que:

1. Recibe `sesion: IdentidadActual = Depends(get_sesion_actual)`.
2. Calcula la intersección entre los roles exigidos y `sesion.roles_db`.
3. Si la intersección está vacía, responde `403` con detalle genérico `"No autorizado"`.
4. Si hay intersección, devuelve `sesion` para que el router pueda pasarla al servicio.

No se consulta el claim `roles` para decidir. La consulta usa el reloj de PostgreSQL (`now()`) y el mismo filtro de vigencia de `RN-04`. Una lista vacía de roles exigidos falla al construir la ruta, de modo que un error de cableado no deje la ruta abierta.

**Alternativas descartadas:** comparar contra `roles_token` (viola `RN-04`); consultar roles en el servicio (mezcla autorización con negocio y duplica la puerta).

### 3. Misma sesión por petición

`get_sesion_actual`, `requiere_rol` y cada `get_*_uow` dependen del **mismo callable** `app.core.database.get_session`. FastAPI cachea la dependencia por petición, así que la identidad, la consulta de roles y el UoW comparten una sola `AsyncSession` y una sola conexión. La prueba de integración instrumenta `get_session` con un contador y comprueba una única invocación para una petición que autoriza y luego consulta datos.

**Condición de borde:** si un endpoint mezclara `get_usuario_actual` y `get_sesion_actual`, se decodificaría el token dos veces. La matriz de rutas evita esa mezcla: cada endpoint usa una sola de las dos dependencias.

### 4. `/auth/yo` con roles de base y de token separados

`GET /auth/yo` depende de `get_sesion_actual` y responde con `YoResponse`:

```json
{
  "usuario": {
    "id": 7,
    "email": "ana@example.com",
    "nombre": "Ana",
    "activo": true,
    "debe_cambiar_password": false
  },
  "roles": ["CLIENTE"],
  "roles_token": ["CLIENTE", "VENDEDOR"]
}
```

`usuario` reutiliza `UsuarioRead`, que ya excluye `password_hash`. `roles` sale de la base en la petición; `roles_token` sale del claim y puede diferir. Ambos se devuelven ordenados y sin duplicados para que la comparación sea estable. No se emite token ni se modifica la cookie. La ruta no usa UoW porque no hay operación de negocio ni escritura: es una proyección de la identidad ya resuelta.

**Alternativas descartadas:** devolver el modelo `Usuario` completo (filtraría `password_hash` si el schema cambia); calcular los roles en el router con una consulta directa (duplicaría la lógica de `roles_vigentes`).

### 5. Matriz de cobertura de endpoints existentes

| Método y ruta | Acceso | Dependencia C-13 |
|---|---|---|
| `GET /health/live`, `GET /health/ready` | público | sin cambio |
| `POST /auth/login`, `POST /auth/logout` | público | sin cambio |
| `GET /auth/yo` | sesión | `get_sesion_actual` |
| `GET /libros`, `GET /libros/{id}` | público | sin cambio |
| `GET /editoriales`, `GET /editoriales/{id}`, `GET /editoriales/{id}/libros` | público | sin cambio |
| `GET /generos`, `GET /generos/{id}/libros` | público | sin cambio |
| `GET /autores`, `GET /autores/{id}`, `GET /autores/{id}/libros` | público | sin cambio |
| `POST /editoriales`, `PATCH /editoriales/{id}` | ADMIN | `requiere_rol("ADMIN")` |
| `POST /generos` | ADMIN | `requiere_rol("ADMIN")` |
| `POST /autores`, `PATCH /autores/{id}` | ADMIN | `requiere_rol("ADMIN")` |
| `POST /libros`, `PATCH /libros/{id}`, `DELETE /libros/{id}`, `POST /libros/{id}/reponer`, `GET /libros/{id}/movimientos` | ADMIN | `requiere_rol("ADMIN")` |
| `POST /clientes`, `GET /clientes/{id}`, `PATCH /clientes/{id}`, `POST /clientes/{id}/perfil` | VENDEDOR/ADMIN | `requiere_rol("VENDEDOR","ADMIN")` |
| `GET /clientes/{id}/ventas` | VENDEDOR/ADMIN | `requiere_rol("VENDEDOR","ADMIN")` + `actual` al servicio |
| `GET /ventas` | VENDEDOR/ADMIN | `requiere_rol("VENDEDOR","ADMIN")` |
| `GET /ventas/{id}` | sesión + propiedad | `get_sesion_actual`; **sin** `requiere_rol` |
| `GET /mis-ventas` | sesión | `get_sesion_actual`; **sin** `requiere_rol` |

Rutas que todavía no existen y quedan fuera: `POST /auth/registro` (C-12), `POST /auth/cambiar-password` (C-14), `/usuarios/*` y `/eventos` (C-15), `POST /ventas` (C-16). No se crean rutas nuevas salvo `/auth/yo`.

### 6. Cierre de C-07 en `clientes`

- El router de `clientes` declara la dependencia de rol en cada ruta de negocio. Se prefiere una dependencia por endpoint (o `dependencies=` del `APIRouter`) antes que un montaje protegido global, para no invadir C-14.
- `GET /clientes/{id}/ventas` agrega `sesion: IdentidadActual = Depends(requiere_rol("VENDEDOR", "ADMIN"))` y llama `service.ventas_de(uow, cliente_id, page, size, actual=sesion)`.
- `service.ventas_de` deja de aceptar `actual=None` por defecto: el parámetro pasa a ser obligatorio. El guard `_es_cliente_solo` se conserva como defensa en profundidad, pero la primera barrera es la dependencia.
- Resultado observable: sin cookie `401`; `CLIENTE` `403` sin ejecutar la consulta de ventas; `VENDEDOR`/`ADMIN` `200` con el mismo envoltorio paginado; cliente inexistente `404` para personal autorizado.
- Los demás endpoints del módulo también exigen personal, alineados con la fila `/clientes` de la matriz RBAC. Esto completa el pendiente de C-07 sin tocar el contrato de negocio de altas, consultas, PATCH ni perfil.

### 7. Ventas: autenticación sin rol para las rutas de propiedad

- `GET /ventas` usa `requiere_rol("VENDEDOR", "ADMIN")`; el valor de retorno no se usa.
- `GET /ventas/{id}` y `GET /mis-ventas` usan `get_sesion_actual` y pasan `actual=sesion` al servicio. No llevan `requiere_rol`, porque un `CLIENTE` dueño debe poder entrar.
- `service.obtener` elimina el bypass temporal `actual is None` y exige siempre la decisión personal/dueño. `service.mis_ventas` exige la identidad actual.
- `_usuario_id` y `_es_personal` se ajustan para leer `IdentidadActual` (`usuario.id`, `roles_db`) en lugar de la introspección de diccionarios/atributos. Siguen sin recibir `AsyncSession` ni construir UoW.

### 8. Orden de errores

La dependencia de rol se ejecuta antes del handler, por lo que un `403` de rol puede preceder a un `404` de recurso inexistente. El orden `404 → 403 → 409 → 422` de `CV-08` sigue aplicando **dentro** del servicio para los recursos que ya pasaron autenticación y rol. Para `GET /clientes/{id}/ventas`, un `CLIENTE` recibe `403` sin que se consulte la existencia del cliente; las pruebas usan un cliente existente y no combinan ambos errores.

**Alternativa descartada:** mover la comprobación de rol al servicio para preservar `404` antes de `403`; eso duplicaría la puerta y dejaría rutas sin protección si un handler se agrega sin el chequeo.

### 9. Estrategia de pruebas

Contra PostgreSQL 17 real y `httpx.ASGITransport`, reutilizando `usuario_factory`, `api_client`, `token_manual` y `db_sessionmaker`:

- **Autorización por rol:** rol vigente permite; revocado con la misma cookie da `403`; `vence_en` pasado da `403`; token que declara un rol ausente en la base da `403`; base que otorga un rol ausente del token permite.
- **401 vs 403:** sin cookie, JWT inválido/vencido y `Authorization` sin cookie dan `401`; autenticado sin rol da `403`; el cuerpo de `403` no enumera roles.
- **`/auth/yo`:** usuario sin `password_hash`, `roles` de base y `roles_token` distintos tras revocar; `401` sin cookie.
- **C-07:** matriz de `GET /clientes/{id}/ventas` con las tres identidades; sin cookie `401`, `CLIENTE` `403`, `VENDEDOR`/`ADMIN` `200` con envoltorio; además `POST/GET/PATCH` de clientes y perfil rechazan `CLIENTE`.
- **Catálogo:** cada mutación ADMIN responde según contrato con `ADMIN` y `403` con `VENDEDOR`/`CLIENTE`; las lecturas públicas siguen sin cookie.
- **Ventas:** `GET /ventas` `403` a `CLIENTE`; `GET /ventas/{id}` `200` al dueño y al personal, `403` a otro cliente; `/mis-ventas` `401` sin cookie.
- **Misma sesión:** app de prueba con una ruta que use `requiere_rol` y un UoW, contando invocaciones de `get_session`; una sola sesión por petición.
- **Regresión:** la suite de C-11 sigue pasando, incluida la prueba de que `get_usuario_actual` no consulta roles. Las pruebas nuevas de `401`/`403` deben fallar antes de implementar y pasar después.

## Risks / Trade-offs

- [El `403` de rol ocurre antes del `404` del recurso y podría sorprender a quien espere el orden de `CV-08`] → Se documenta que `CV-08` rige dentro del servicio; la barrera de rol es previa y no consulta el recurso.
- [Duplicar en la especificación de `role-authorization` comportamientos ya descritos en `clientes-y-perfil` o `ventas`] → Los textos se mantienen idénticos en lo observable; la capability nueva aporta la regla transversal y el delta de `clientes` sólo agrega `401` y la lectura de rol vigente.
- [Ampliar C-13 a todas las rutas de personal puede solaparse con C-14/C-15] → Se limita a rutas ya existentes, no se crean routers nuevos ni se monta el grupo protegido; las rutas futuras quedan explícitamente fuera.
- [La caché de dependencias de FastAPI es la garantía de una sola sesión] → Todas las piezas dependen del mismo callable `get_session`; una prueba con contador lo verifica y la matriz evita mezclar `get_usuario_actual` con `get_sesion_actual`.
- [Cargar roles en `GET /ventas/{id}` agrega una consulta por petición] → Es el costo explícito de `RN-04`; se reutiliza la misma conexión y no se cachea para que la revocación tenga efecto inmediato.

## Migration Plan

No hay migración de base ni cambio de esquema. Al implementar, no se toca Alembic. El rollback consiste en retirar `/auth/yo` y las dependencias de rol de los routers, restaurando el estado de C-11/C-10; no hay datos que revertir. No se modifican variables de entorno ni secretos.

## Open Questions

Ninguna. La forma de la respuesta de `/auth/yo` (`usuario`, `roles`, `roles_token`) y el alcance de rutas quedan fijados por este diseño y por la aceptación de C-13.

## UI Mockups

- Decision: no (no UI)
