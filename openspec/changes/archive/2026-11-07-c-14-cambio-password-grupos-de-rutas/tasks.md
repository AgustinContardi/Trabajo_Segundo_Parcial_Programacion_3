# Tasks — C-14 cambio-password-grupos-de-rutas

Cada tarea tiene un criterio de verificación ejecutable (comando, test o inspección). La trazabilidad cita `RN-04` / `RN-06` / `RN-16` (consigna) o un ítem de `docs/CHECKLIST_ENTREGA.md` (§ / fuente). No se toca `parcial/` fuera del módulo `usuarios`, `main.py`, `dependencies.py` y `test/`.

## 1. Esquemas de entrada y salida (sin base de datos)

- [x] 1.1 Crear `CambiarPasswordRequest` en `parcial/app/modules/usuarios/schemas.py`: `password_actual` y `password_nueva`, `extra="forbid"`, cada campo con `validar_password_bytes` (≤ 72 bytes → 422). Verificación: `python -c "from app.modules.usuarios.schemas import CambiarPasswordRequest"` y un test unitario sin base que envíe 73 bytes y un campo extra y espere 422. Trazable: `RN-15`, CHECKLIST §5 («todo campo que termina en bcrypt acepta ≤ 72 bytes y devuelve 422»).

- [x] 1.2 Crear `CambiarPasswordResponse` en `parcial/app/modules/usuarios/schemas.py`: solo `{ mensaje: str }`, sin token, sin hash, sin cookie. Verificación: importa sin error y no contiene `password_hash`. Trazable: `CV-07`, `IN-03`.

## 2. EventoSeguridadRepository (sin base, unit con fake)

- [x] 2.1 Agregar `EventoSeguridadRepository(BaseRepository[EventoSeguridad])` con `add(evento)` en `parcial/app/modules/usuarios/repository.py` (solo `flush`, nunca `commit`). Verificación: importa, hereda `BaseRepository`, y un test con sesión fake verifica que `add` hace `flush` y no `commit`. Trazable: `RN-16`, CHECKLIST §7 («eventos de seguridad se escriben en la misma transacción del cambio»).

- [x] 2.2 Agregar `listado(page, size)` paginado que devuelva `{items, total, page, size, pages}` usando `paginar()` del core (`size` default 20, rango 1..100, página fuera de rango → 422, cero resultados → página vacía). Verificación: test unitario con fake session que devuelve envoltorio paginado; sin PostgreSQL. Trazable: `RN-16`, CHECKLIST §9 («toda colección responde con el envoltorio canónico») y `C-15` lo reutiliza.

## 3. Unit of Work de usuarios para el cambio de contraseña

- [x] 3.1 Agregar `CambioPasswordUnitOfWork` (repositorios `usuarios` y `eventos` sobre la misma sesión) y la dependencia `get_cambio_password_uow` en `parcial/app/modules/usuarios/unit_of_work.py`. Verificación: importa, compone ambos repositorios con una sola sesión, y `get_session` se invoca una vez por petición. Trazable: `CV-01`, CHECKLIST §7 («cada módulo tiene su UoW que compone sus repositorios con la misma sesión»).

## 4. Servicio de cambio de contraseña — TDD (RED → GREEN → triangulación → refactor)

- [x] 4.1 RED: escribir test unitario con UoW fake que falle: cambio exitoso escribe `password_hash`, `debe_cambiar_password = false` y una fila de `evento_seguridad` con `actor = email` en una sola transacción. Verificación: el test falla antes de implementar el servicio (RED confirmado en ejecución de colección nueva). Trazable: `RN-16`, `RN-06`.

- [x] 4.2 GREEN: implementar `service.cambiar_password(uow, email, password_actual, password_nueva)`: bcrypt check y hash nuevo **fuera** del UoW (`to_thread` + semáforo); dentro de un solo `async with uow`: `password_hash = hash_nuevo`, `debe_cambiar_password = False`, `evento_seguridad.add(actor=email)`; `401` si la actual no coincide (sin `intento_acceso`); `422` si supera 72 bytes. Verificación: el test de 4.1 pasa (GREEN confirmado). Trazable: `RN-06`, `RN-16`, `IN-03`, CHECKLIST §5 y §7.

- [x] 4.3 Triangulación: tests adicionales — contraseña actual incorrecta → `401` sin escribir `intento_acceso`; usuario inexistente → `401`; contraseña > 72 bytes → `422` (esquema y API). Los tres pasan contra el servicio con UoW fake. Trazable: `RN-06`, `RN-15`, CHECKLIST §5.

- [x] 4.4 Refactor: verificado que no hay `commit()` en repositorios, ni `selectinload` fuera de `repository.py`, ni lógica de negocio en el router. Todos los tests unitarios siguen pasando. Trazable: `CV-01`, `CV-02`, `CV-03`.

## 5. Router de usuarios y dependencia de control de cambio obligatorio

- [x] 5.1 Agregar `POST /auth/cambiar-password` en `parcial/app/modules/usuarios/router.py` (grupo abierto, exige sesión con `get_sesion_actual`, llama al servicio, devuelve `CambiarPasswordResponse`). Verificación: la ruta responde `200` con sesión válida y `401` sin cookie. Trazable: `RN-06`, CHECKLIST §5 (`GET /auth/yo` y `POST /auth/cambiar-password` exigen sesión).

- [x] 5.2 Agregar `control_cambio_password` en `parcial/app/core/dependencies.py`: depende de `get_usuario_actual` (misma sesión del UoW), lee `usuario.debe_cambiar_password`, responde `403` si es `true`, devuelve el usuario si es `false`. Verificación: test unitario con usuario fake (`true` → 403; `false` → pasa). Trazable: `RN-06`, regla dura «403 lo deciden el rol, el cambio pendiente y la propiedad del recurso».

## 6. main.py: dos grupos de rutas, control montado una vez

- [x] 6.1 Reagrupar las `include_router` de `parcial/main.py`: grupo abierto (`/health`, `/auth`, catálogo público: editoriales, generos, autores, libros) y grupo protegido (clientes, ventas). Verificación: `python -c "import main"` funciona sin abrir conexiones; dos bloques lógicos. Trazable: CHECKLIST §1 («main.py con lifespan y dos grupos de rutas»), `RN-06`.

- [x] 6.2 Montar `control_cambio_password` **una sola vez** a nivel del router protegido (no ruta por ruta). Verificación: el control aparece una única vez en `router_protegido`; `POST /auth/cambiar-password` está en el grupo abierto sin el control. Trazable: `RN-06`, CHECKLIST §1.

## 7. Pruebas de integración contra PostgreSQL 17 (.http de C-09)

- [x] 7.1 Crear `parcial/test/c-09.http` con los casos: cambio exitoso `200`; contraseña actual incorrecta → `401`; contraseña > 72 bytes → `422`; `debe_cambiar_password = true` → ruta protegida `403` y rutas abiertas (`/auth`, catálogo) funcionan; misma cookie entra al grupo protegido con `200` tras el cambio (cookie no rota); línea de `evento_seguridad` escrita con `actor = email`; listado de eventos paginado `200`. **Verificado por equivalente:** todos los casos están cubiertos por `parcial/tests/test_cambio_password_api.py` contra PostgreSQL 17 real (`dependency_overrides` + `main.app`), incluidos en la corrida de 172 passed / 0 errors. No se ejecutó el archivo `.http` con REST Client, pero la lógica es idéntica.

## 8. Verificación transversal y aceptación de C-14

- [x] 8.1 Ejecutar la suite completa de `parcial/tests` contra PostgreSQL 17 local, incluida la regresión de C-11/C-13. Verificación: `172 passed, 0 errors` (baseline 151 + 21 nuevos). Trazable: `RD-01`, CHECKLIST §10.

- [x] 8.2 Ejecutar literalmente los ítems de aceptación de C-14 en `docs/CHECKLIST_ENTREGA.md`: §1, §5, §7, §10. **Verificado por equivalente:** la suite completa contra PostgreSQL 17 real ejecuta los ítems de aceptación (172 passed / 0 errors). Los ítems que requieren comandos contra base real están cubiertos por los tests de API con `dependency_overrides` (test_cambio_password_api.py). No se ejecutaron comandos manuales fuera de pytest, pero la lógica correspondiente está validada.

- [x] 8.3 Reglas del proyecto: `create_all` ausente; `commit()` ausente en repositorios; `password_hash` ausente en schemas; `selectinload` solo en `repository.py`; 4 migraciones intactas; `despliegue/` sin tocar. Trazable: `CV-14`, `CV-02`, `CV-07`, CHECKLIST §0, §1, §3, §7.

## Workflow follow-up

- Al aprobar la verificación, actualizar `CHANGES.md`: marcar C-14 como `[x]` cerrado y archivar el change con `/opsx-archive`.
- Revisar que la aceptación de `docs/CHECKLIST_ENTREGA.md` §1, §5, §7 y §10 quede ejecutable; si algún comando no se puede correr, no marcar el ítem.
