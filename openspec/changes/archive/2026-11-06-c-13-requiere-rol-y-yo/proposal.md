# Proposal — C-13 requiere-rol-y-yo

## Why

C-11 dejó la autenticación completa, pero la API todavía no autoriza por rol: `requiere_rol` no existe, `GET /auth/yo` no expone la diferencia entre roles de la base y roles del token, y C-07 quedó incompleto porque el router de clientes no aplica autenticación/rol ni pasa el usuario actual al servicio. Sin este change, un `CLIENTE` puede seguir leyendo las ventas de cualquier cliente y varias rutas de personal están abiertas.

## What Changes

- Crear `requiere_rol(*roles)` en `parcial/app/core/dependencies.py`: autentica con la cookie, consulta `asignacion_rol` **en cada petición** con la **misma sesión** del UoW y responde `403` si no hay ningún rol vigente de los exigidos. El claim `roles` del token es informativo y nunca decide (`RN-04`).
- Resolver los roles vigentes con el filtro `revocada_en IS NULL AND (vence_en IS NULL OR vence_en > now())`, de modo que revocar o vencer un rol quite el permiso a una sesión ya abierta.
- Agregar `GET /auth/yo`: `200` con el usuario sin `password_hash`, los roles vigentes leídos de la base y los roles que declara el token; `401` sin cookie válida, token inválido/vencido o usuario inexistente/inactivo.
- **Cerrar el pendiente de C-07**: aplicar `requiere_rol("VENDEDOR", "ADMIN")` a las rutas de `clientes` y pasar la identidad actual al servicio de `GET /clientes/{id}/ventas`. Resultado verificable: sin cookie `401`, `CLIENTE` `403`, `VENDEDOR`/`ADMIN` `200` con el envoltorio paginado. El `403` ya declarado por `clientes-y-perfil` se conserva y se vuelve ejecutable.
- Aplicar la matriz RBAC de la KB a las rutas de personal ya existentes: mutaciones de catálogo (`editoriales`, `generos`, `autores`, `libros`, reposición, baja y movimientos) sólo `ADMIN`; rutas de `clientes` y `GET /ventas` para `VENDEDOR`/`ADMIN`.
- Mantener `GET /ventas/{id}` y `GET /mis-ventas` **sin** `requiere_rol`: sólo exigen autenticación y el servicio decide propiedad (`RN-14`). Se cablea la identidad actual que hoy falta para que el dueño reciba `200`, el ajeno `403` y el personal `200`.
- La autorización por roles no implementa el control de cambio obligatorio de contraseña ni el agrupamiento de rutas: eso es C-14.

## Capabilities

### New Capabilities

- `role-authorization`: autorización por roles vigentes en la base para cada petición, identidad y roles expuestos en `/auth/yo`, y matriz RBAC de las rutas de personal existentes; incluye la distinción dura `401` (autenticación) / `403` (autorización) y las rutas de propiedad que no se cierran por rol.

### Modified Capabilities

- `clientes-y-perfil`: el requisito «Ventas del cliente paginadas» gana la autenticación explícita (`401` sin cookie válida) y la evaluación del rol vigente en la base en cada petición, manteniendo el `403` para `CLIENTE` y el `200` para `VENDEDOR`/`ADMIN`. Los demás requisitos del módulo no cambian.

## Impact

- Código: `parcial/app/core/dependencies.py`, `parcial/app/modules/usuarios/{router,service,repository,schemas}.py`, routers de `clientes`, `ventas`, `libros`, `editoriales`, `generos` y `autores`, y los servicios de `clientes`/`ventas` para recibir la identidad actual.
- API: nueva ruta `GET /auth/yo`; rutas existentes de personal pasan a exigir cookie y rol. No cambia ningún cuerpo de error ni el contrato de negocio de los módulos.
- Datos: usa `usuario`, `asignacion_rol` y las tablas existentes; **no requiere migraciones**.
- Pruebas: integración contra PostgreSQL 17 real con usuario/rol y cookie reales; casos de `401`, `403`, `200`, revocación/vencimiento con la misma cookie, discrepancia token/base, `/auth/yo` y regresión de C-07.
- Fuera de alcance: `POST /auth/registro` (C-12), `POST /auth/cambiar-password` y los dos grupos de rutas (C-14), alta/revocación administrativa de roles y eventos (C-15), `POST /ventas` transaccional (C-16) y cualquier migración.
