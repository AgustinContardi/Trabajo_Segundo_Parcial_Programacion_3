# Tasks — C-07 capas-clientes-y-perfil

## 1. Verificación del modelo (sin cambios de esquema)

- [x] 1.1 Verificar que `parcial/app/modules/clientes/models.py` declara `Cliente.usuario_id` nulo permitido y `UNIQUE` con índice, y que `Cliente.usuario`/`Usuario.cliente` están declarados en los dos extremos; verificar `PerfilCliente.cliente_id` FK `UNIQUE` 1—1; confirmar con `python -c "import app.modules.clientes.models"` que los mappers configuran sin error.
- [x] 1.2 Verificar que no se alteran los modelos ni se agregan migraciones; `alembic check` sigue limpio y no hay nueva versión en `migrations/versions/`.

## 2. Repositorio y Unit of Work del módulo

- [x] 2.1 Crear `parcial/app/modules/clientes/repository.py` con `ClienteRepository(BaseRepository[Cliente])`: constructor `(session, Cliente)`, método `get_by_id` con precarga de `perfil` y `usuario` declarada adentro (`selectinload`), y método `ventas_de(cliente_id, page, size)` que consulta `Venta` por `cliente_id` y delega a `paginar()`.
- [x] 2.2 Crear `parcial/app/modules/clientes/unit_of_work.py` con `ClientesUnitOfWork(UnitOfWork)` que componga `ClienteRepository` con la misma sesión, y la dependencia `get_clientes_uow(session) -> ClientesUnitOfWork`.
- [x] 2.3 Verificar `grep -rn "selectinload\|joinedload" parcial/app/modules/clientes/repository.py` encuentra las precargas y `grep -rn "selectinload" parcial/app/modules/clientes/service.py parcial/app/modules/clientes/router.py` está vacío.

## 3. Schemas

- [x] 3.1 Extender `parcial/app/modules/clientes/schemas.py`: agregar `usuario_id: Optional[int] = None` a `ClienteRead` (heredado por `ClienteDetailRead`), mantener `extra="forbid"` y `exclude_unset` en `ClienteUpdate`, y `PerfilCreate`/`PerfilRead` con los campos existentes.
- [x] 3.2 Verificar que `ClienteCreate`, `ClienteUpdate`, `PerfilCreate` rechazan campos extra (`extra="forbid"`) y que ningún schema expone `password_hash`.

## 4. Servicio

- [x] 4.1 Reescribir `parcial/app/modules/clientes/service.py` para que cada función reciba `ClientesUnitOfWork` y lo abra con `async with`: `crear`, `obtener`, `actualizar`, `crear_perfil`, `ventas_de`, sin parámetro `AsyncSession` ni construcción de UoW.
- [x] 4.2 Implementar `crear`: alta con `usuario_id` nulo, captura de `IntegrityError` y traducción a `409`/`422` sin `session.rollback()` manual.
- [x] 4.3 Implementar `obtener`: carga con precarga de `perfil`, `404` si no existe.
- [x] 4.4 Implementar `actualizar`: carga, aplica `exclude_unset`, `update` con `flush`, traducción de `IntegrityError` (correo que choca → `409`).
- [x] 4.5 Implementar `crear_perfil`: `404` si el cliente no existe, `409` si ya tiene perfil, alta con `flush` y traducción de `IntegrityError`.
- [x] 4.6 Implementar `ventas_de(cliente_id, page, size, actual=None)`: `404` si el cliente no existe, punto de decisión para `403` si `actual` tiene sólo rol `CLIENTE` (cableado completo en C-13), delegación a `ClienteRepository.ventas_de` con paginación.
- [x] 4.7 Verificar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/clientes/service.py` vacío.

## 5. Router

- [x] 5.1 Reescribir `parcial/app/modules/clientes/router.py` para construir el UoW con `Depends(get_clientes_uow)` y pasarlo al servicio, sin `session.commit()`/`session.rollback()` en el router.
- [x] 5.2 `POST /clientes` → `201` con `usuario_id` nulo; `GET /clientes/{id}` → `200` con perfil opcional; `PATCH /clientes/{id}` → `200` sólo con lo enviado.
- [x] 5.3 `POST /clientes/{id}/perfil` → `201`/`404`/`409`.
- [x] 5.4 `GET /clientes/{id}/ventas` → `200` paginado con envoltorio, mapeando cada `Venta` a `VentaRead` con `ClienteRef` a partir del cliente cargado.
- [x] 5.5 Verificar que el router no contiene `selectinload` ni `AsyncSession`.

## 6. Integración y verificación

- [x] 6.1 Registrar el router (ya está en `main.py`) y confirmar import sin errores: `python -c "import main"` (o equivalente con `PYTHONPATH=parcial`).
- [x] 6.2 Correr pruebas manuales/equivalentes: alta de cliente de mostrador (`201`, `usuario_id` nulo), correo duplicado (`409`), campos extra (`422`), consulta con/sin perfil (`200`), PATCH parcial (`200`), perfil duplicado (`409`), ventas paginadas (`200` con envoltorio), cliente inexistente (`404`).
- [x] 6.3 Ejecutar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/clientes/service.py` y `grep -rn "selectinload" parcial/app/modules/clientes/service.py parcial/app/modules/clientes/router.py` y confirmar ambos vacíos.
- [x] 6.4 Ejecutar `alembic check` (sin cambios) y confirmar que el import de la app no abre conexiones.

## Workflow follow-up

- Archivar el change con `/opsx:archive` y marcar `[x]` en `CHANGES.md` cuando la aceptación de C-07 esté verificada.
- Completar el cableado de autorización (`403` para `CLIENTE` en `GET /clientes/{id}/ventas`) en C-13 cuando `get_usuario_actual`/`requiere_rol` estén disponibles.