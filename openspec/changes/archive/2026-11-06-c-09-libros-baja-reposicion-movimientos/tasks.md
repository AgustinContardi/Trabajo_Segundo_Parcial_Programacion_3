# Tasks

## 1. Schemas de reposición y movimientos

- [x] 1.1 Agregar en `parcial/app/modules/libros/schemas.py` el schema `ReponerCreate` (o `ReponerStock`) con `cantidad: int = Field(gt=0)` y `extra="forbid"`; verificar que `cantidad <= 0` da 422.
- [x] 1.2 Agregar en `parcial/app/modules/libros/schemas.py` el schema `MovimientoStockRead` con `id`, `libro_id`, `venta_id: Optional[int]`, `usuario_id`, `cantidad: int`, `motivo: str`, `cuando: datetime` (from_attributes); verificar que importa sin error.

## 2. Repositorio: baja, reposición y movimientos

- [x] 2.1 Verificar que `LibroRepository` (hereda `SoftDeleteRepository`) ya expone `soft_delete` y `get_by_id_including_deleted`; si falta, agregarlos. Verificar `python -c "import app.modules.libros.repository"` OK.
- [x] 2.2 Implementar en `LibroRepository` un método `movimientos(libro_id)` que devuelva `list[MovimientoStock]` filtrado por `libro_id` ordenado por `cuando` (y `id`); verificar que no hace `commit()`.
- [x] 2.3 Verificar que `aplicar_movimiento` se reusa para la reposición (motivo `'Reposición'`) y que no existe otro lugar que escriba `libro.stock` (`grep -rn "stock =" parcial/app/modules/libros` sólo en repository.py).

## 3. Servicio: baja, reposición y movimientos

- [x] 3.1 Implementar `service.dar_de_baja(uow, libro_id)` que carga con `get_by_id` (404 si `None`) y llama `soft_delete` dentro del `async with`; verificar que un libro dado de baja desaparece de `GET /libros/{id}`.
- [x] 3.2 Implementar `service.reponer(uow, libro_id, cantidad, usuario_actual=None)` que valida `cantidad > 0`, carga el libro (404 si `None`), responde 409 si `borrado_en is not None` y llama `aplicar_movimiento(..., 'Reposición', usuario_id)`; verificar que deja el movimiento de entrada.
- [x] 3.3 Implementar `service.movimientos(uow, libro_id)` que carga el libro (404 si `None` o dado de baja) y devuelve la lista mapeada a `MovimientoStockRead`; verificar que cada elemento trae `cantidad`, `motivo`, `cuando`, `usuario_id`, `venta_id`.
- [x] 3.4 Implementar helpers `to_movimiento_read` (y reusar `to_read`/`to_detail_read`) para serializar; verificar imports OK.
- [x] 3.5 Mantener `service.crear` sin cambios de firma: verificar que la re-alta con ISBN de un libro dado de baja da 201 y un segundo vigente da 409 (índice parcial).

## 4. Router: nuevas rutas

- [x] 4.1 Cablear `DELETE /libros/{libro_id}` → 204 en `router.py` con `uow: LibrosUnitOfWork = Depends(get_libros_uow)`; verificar respuesta 204.
- [x] 4.2 Cablear `POST /libros/{libro_id}/reponer` → 200 con body `ReponerCreate` y respuesta `LibroDetailRead`; verificar que carga el libro actualizado.
- [x] 4.3 Cablear `GET /libros/{libro_id}/movimientos` → 200 con `list[MovimientoStockRead]`; verificar que devuelve la lista.
- [x] 4.4 Verificar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/libros/service.py` vacío y `grep -rn "selectinload\|joinedload" parcial/app/modules/libros/service.py parcial/app/modules/libros/router.py` vacío.

## 5. Invariantes y verificación de capa

- [x] 5.1 Verificar `grep -rn "session.commit\|session.rollback" parcial/app/modules/libros/router.py` vacío.
- [x] 5.2 Verificar `py_compile` de todos los archivos del módulo y `import app.main` OK.
- [x] 5.3 Verificar el invariante `libro.stock = SUM(movimiento_stock.cantidad)` tras una baja + reposición manual.
- [x] 5.4 Verificar que un libro dado de baja no aparece en `GET /libros` ni en `GET /libros/{id}` y que su ISBN se puede reusar (201) y un segundo vigente da 409.

## Workflow follow-up

- Archivar el change con `/opsx:archive` tras la revisión y marcar `[x]` en `CHANGES.md`.
- Verificar el resultado archivado.