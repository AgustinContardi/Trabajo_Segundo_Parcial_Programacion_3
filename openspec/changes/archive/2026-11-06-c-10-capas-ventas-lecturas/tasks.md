# Tasks — C-10 capas-ventas-lecturas

## 1. Verificación del modelo (sin cambios de esquema)

- [x] 1.1 Verificar que `parcial/app/modules/ventas/models.py` declara las relaciones
  `Venta.cliente`, `Venta.renglones` y `RenglonVenta.libro`, con las FKs indexadas
  (`cliente_id`, `venta_id`, `libro_id`), y confirmar con
  `python -c "import app.modules.ventas.models"` que los mappers configuran sin error.
- [x] 1.2 Verificar que no se alteran los modelos ni se agregan migraciones; `alembic check`
  sigue limpio y no hay nueva versión en `migrations/versions/`.

## 2. Repositorio y Unit of Work del módulo

- [x] 2.1 Crear `parcial/app/modules/ventas/repository.py` con `VentaRepository(BaseRepository[Venta])`:
  constructor `(session, Venta)`; método `get_by_id` con precarga de `cliente`,
  `renglones` y el `libro` de cada renglón (incluidos los dados de baja) declarada
  adentro (`selectinload` anidado); método `listar(page, size)` con
  `selectinload(Venta.cliente)` y orden estable delegando a `paginar()`; método
  `ventas_de_cliente(cliente_id, page, size)` filtrando por `cliente_id` con
  `selectinload(Venta.cliente)` y delegando a `paginar()`.
- [x] 2.2 Crear `parcial/app/modules/ventas/unit_of_work.py` con `VentasUnitOfWork(UnitOfWork)`
  que componga `VentaRepository` y `ClienteRepository` (para resolver `usuario_id →
  cliente`) con la misma sesión, y la dependencia `get_ventas_uow(session) -> VentasUnitOfWork`.
- [x] 2.3 Verificar `grep -rn "selectinload\|joinedload" parcial/app/modules/ventas/repository.py`
  encuentra las precargas y
  `grep -rn "selectinload\|joinedload" parcial/app/modules/ventas/service.py parcial/app/modules/ventas/router.py`
  está vacío.

## 3. Schemas

- [x] 3.1 Verificar que `parcial/app/modules/ventas/schemas.py` mantiene `VentaRead`,
  `VentaDetailRead`, `ClienteRef`, `RenglonRead` con `from_attributes=True` y
  `extra="forbid"`, y que `RenglonRead.titulo` se completa a partir del libro precargado
  (incluidos los dados de baja). Confirmar que **no** existe `VentaUpdate`.
- [x] 3.2 Verificar que `VentaCreate`/`RenglonCreate` mantienen `extra="forbid"` y que ningún
  schema expone `password_hash`.

## 4. Servicio

- [x] 4.1 Reescribir `parcial/app/modules/ventas/service.py` para que cada función reciba
  `VentasUnitOfWork` y lo abra con `async with`: `listar`, `obtener`, `mis_ventas`, sin
  parámetro `AsyncSession` ni construcción de UoW.
- [x] 4.2 Implementar `listar(page, size)`: delegación a `VentaRepository.listar` y mapeo a
  `VentaRead` con `ClienteRef` a partir del cliente cargado.
- [x] 4.3 Implementar `obtener(venta_id, actual=None)`: carga con precarga (404 si no existe);
  devuelve la venta si quien pide es personal o el dueño; lanza `403` en caso contrario.
  Punto de decisión documentado para el cableado de `get_usuario_actual`/`requiere_rol`
  (C-11/C-13).
- [x] 4.4 Implementar `mis_ventas(usuario, page, size)`: resuelve el cliente ligado al usuario
  (`cliente.usuario_id = usuario.id`); si no hay ficha → página vacía (`SU-05`); si la hay →
  `VentaRepository.ventas_de_cliente(cliente_id, page, size)` mapeado a `VentaRead`.
- [x] 4.5 Verificar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/ventas/service.py`
  vacío.

## 5. Router

- [x] 5.1 Reescribir `parcial/app/modules/ventas/router.py` para construir el UoW con
  `Depends(get_ventas_uow)` y pasarlo al servicio, sin `session.commit()`/`session.rollback()`
  en el router.
- [x] 5.2 `GET /ventas` → `200` con envoltorio, con `requiere_rol('VENDEDOR','ADMIN')` cuando
  esté disponible (cableado en C-13); mapeo a `VentaRead`.
- [x] 5.3 `GET /ventas/{venta_id}` → `200` con `VentaDetailRead` (precarga incluye libros dados
  de baja), sin `requiere_rol`; mapeo de renglones con `titulo` y `subtotal`.
- [x] 5.4 `GET /mis-ventas` → `200` con envoltorio, sólo sesión (cableado en C-13), mapeo a
  `VentaRead`.
- [x] 5.5 Verificar que el router no contiene `selectinload` ni `AsyncSession`, y que no registra
  `PATCH /ventas/{id}`.

## 6. Integración y verificación

- [x] 6.1 Registrar el router (ya está en `main.py`) y confirmar import sin errores:
  `python -c "import main"` (con `PYTHONPATH=parcial`).
- [x] 6.2 Correr pruebas manuales/equivalentes: `GET /ventas` paginado (200, envoltorio, orden
  estable), `GET /ventas/{id}` existente (200 con renglones y título de libro dado de baja),
  inexistente (404), ajeno (403), `GET /mis-ventas` con/sin ficha de cliente (200, página
  vacía si no hay ficha), sin sesión (401), y contar `SELECT` con `SQL_ECHO=true` con 2 y 4
  renglones (mismo número).
- [x] 6.3 Ejecutar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/ventas/service.py` y
  `grep -rn "selectinload" parcial/app/modules/ventas/service.py parcial/app/modules/ventas/router.py`
  y confirmar ambos vacíos.
- [x] 6.4 Ejecutar `alembic check` (sin cambios) y confirmar que el import de la app no abre
  conexiones.

## Workflow follow-up

- Archivar el change con `/opsx:archive` y marcar `[x]` en `CHANGES.md` cuando la aceptación
  de C-10 esté verificada.
- Completar el cableado de autorización (`403` para quien no es personal ni dueño en
  `GET /ventas/{id}`, sesión en `/mis-ventas`) en C-13 cuando
  `get_usuario_actual`/`requiere_rol` estén disponibles.