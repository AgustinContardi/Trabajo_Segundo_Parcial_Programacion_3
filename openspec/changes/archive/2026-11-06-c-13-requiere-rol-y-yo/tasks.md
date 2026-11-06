# Tasks — C-13 requiere-rol-y-yo

## 1. Contexto de identidad y dependencia de rol

- [x] 1.1 En `parcial/app/core/dependencies.py`, extraer el helper interno de autenticación y agregar `IdentidadActual` (`usuario`, `roles_db`, `roles_token`) con `get_sesion_actual`, leyendo la cookie sólo de `request.cookies` y los roles con `UsuarioRepository.roles_vigentes`; verificar con pruebas de integración que `get_usuario_actual` sigue sin consultar roles y que `get_sesion_actual` devuelve los dos conjuntos y responde `401` en los mismos casos que C-11.
- [x] 1.2 Implementar la fábrica `requiere_rol(*roles)` en `dependencies.py`: validar que haya roles, normalizar a mayúsculas, comparar sólo contra `roles_db`, responder `403` genérico sin roles y devolver `IdentidadActual`; verificar con una ruta de prueba que rol vigente permite, rol revocado/vencido y token que miente dan `403`, y que la base puede otorgar un rol ausente del token.
- [x] 1.3 Agregar `YoResponse` en `parcial/app/modules/usuarios/schemas.py` y `GET /auth/yo` en el router de `usuarios`, usando `get_sesion_actual`; verificar `200` con `usuario`, `roles` y `roles_token` distintos tras revocar un rol, ausencia de `password_hash`/token en el cuerpo y `401` sin cookie válida.

## 2. Cierre del pendiente de C-07 en clientes

- [x] 2.1 Aplicar `requiere_rol("VENDEDOR", "ADMIN")` a `POST /clientes`, `GET /clientes/{id}`, `PATCH /clientes/{id}`, `POST /clientes/{id}/perfil` y `GET /clientes/{id}/ventas`; verificar `401` sin cookie y `403` para `CLIENTE` en cada ruta, con el cuerpo genérico.
- [x] 2.2 Pasar `IdentidadActual` a `service.ventas_de` desde `GET /clientes/{id}/ventas` y volver obligatorio el parámetro `actual` en el servicio, conservando el guard de defensa en profundidad; verificar que `VENDEDOR` y `ADMIN` reciben `200` con `{items, total, page, size, pages}` y que un cliente inexistente da `404` sólo para personal autorizado.
- [x] 2.3 Escribir la prueba de regresión de C-07 que hoy falla con la ruta abierta (sin cookie `401`, `CLIENTE` `403`, `VENDEDOR`/`ADMIN` `200`) y verificar que después de 2.1/2.2 pasa contra PostgreSQL 17 real; comprobar además que el `403` no ejecuta la consulta de ventas.

## 3. Matriz RBAC de catálogo

- [x] 3.1 Aplicar `requiere_rol("ADMIN")` a `POST /editoriales`, `PATCH /editoriales/{id}`, `POST /generos`, `POST /autores` y `PATCH /autores/{id}`; verificar `201`/`200` con `ADMIN`, `403` con `VENDEDOR`/`CLIENTE` y `401` sin cookie.
- [x] 3.2 Aplicar `requiere_rol("ADMIN")` a `POST /libros`, `PATCH /libros/{id}`, `DELETE /libros/{id}`, `POST /libros/{id}/reponer` y `GET /libros/{id}/movimientos`; verificar los códigos de contrato con `ADMIN` y `403` con `VENDEDOR`/`CLIENTE`.
- [x] 3.3 Verificar que las lecturas públicas (`GET /libros`, `GET /libros/{id}`, `GET /editoriales`, `GET /generos`, `GET /autores` y los listados por entidad) siguen respondiendo sin cookie y no incorporan dependencias de rol.

## 4. Ventas: autorización de personal y propiedad

- [x] 4.1 Agregar `requiere_rol("VENDEDOR", "ADMIN")` sólo a `GET /ventas`; verificar `200` para ambos roles, `403` para `CLIENTE` y `401` sin cookie.
- [x] 4.2 Cablear `get_sesion_actual` en `GET /ventas/{id}` y `GET /mis-ventas`, pasar `actual=sesion` al servicio y eliminar el bypass `actual is None` de `service.obtener`; verificar dueño `200`, otro `CLIENTE` `403`, personal `200`, venta inexistente `404` y `/mis-ventas` `401` sin cookie.
- [x] 4.3 Ajustar los helpers del servicio de ventas para leer `IdentidadActual` (`usuario.id` y `roles_db`) sin recibir `AsyncSession` ni construir UoW; verificar que `GET /ventas/{id}` y `/mis-ventas` no contienen `requiere_rol` en su definición y que el servicio sigue concentrando la decisión de propiedad (`RN-14`).

## 5. Verificación transversal y aceptación

- [x] 5.1 Agregar una prueba con contador sobre `get_session` para una petición que use `requiere_rol` y un UoW; verificar una sola invocación y la misma instancia de sesión para identidad, roles y repositorio.
- [x] 5.2 Ejecutar la suite completa de `parcial/tests` contra PostgreSQL 17 local, incluida la regresión de C-11; verificar que las pruebas nuevas de `401`/`403` fallan antes de la implementación y pasan después, y que `python -c "import main"` con `PYTHONPATH=parcial` sigue funcionando sin abrir conexiones.
- [x] 5.3 Crear o ampliar `parcial/test/roles.http` con los casos C-06 y C-07 (dos sesiones cuando corresponda: revocación con cookie abierta, `/auth/yo` mostrando la diferencia, `GET /clientes/{id}/ventas` con `401`/`403`/`200`, `GET /ventas/{id}` dueño/ajeno, mutaciones de catálogo con `VENDEDOR` `403`); verificar con REST Client que cada caso documenta código y cuerpo esperados.
- [x] 5.4 Ejecutar `alembic check` y revisar el diff para confirmar que no hay migraciones ni cambios de esquema, que no se filtraron secretos y que no se adelantaron C-14 (grupos de rutas, cambio obligatorio, cambiar-password), C-15 (usuarios/roles/eventos) ni C-16 (POST /ventas).

## Workflow follow-up

- Al terminar y aprobar la verificación, actualizar `CHANGES.md`: marcar C-07 como `[x]` cerrado por el cierre de su 403 y C-13 como `[x]`, y archivar el change con `/opsx-archive`.
- Revisar que la aceptación de `docs/CHECKLIST_ENTREGA.md` §5, §6, §7 y los casos C-06/C-07 queden ejecutables; si algún comando no se puede correr, no marcar el ítem.
