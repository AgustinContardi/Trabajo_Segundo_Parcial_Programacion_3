# Design — C-09 libros-baja-reposicion-movimientos

## Context

Ver `proposal.md` — Why. El estado actual (C-08 cerrado) deja `libros` con seis capas,
`LibroRepository(SoftDeleteRepository[Libro])` con filtro de borrados por defecto y
precarga de editorial/género/autores, el punto único `aplicar_movimiento` (motivos
`'Stock inicial'`, `'Reposición'`, `'Venta'`) y `get_by_id_including_deleted` heredado.
Las migraciones 0001–0004 ya están aplicadas; no hay cambios de esquema. El modelo `Libro`
ya tiene `borrado_en` + índice parcial del ISBN, `CHECK (precio > 0)` y
`CHECK (stock >= 0)`; `MovimientoStock` ya tiene `CHECK (cantidad <> 0)` y el disparador
append-only (C-04). La autorización (`requiere_rol`) llega con C-11/C-13; hasta entonces
los puntos de decisión se dejan documentados y se cablean sin cambiar la firma, como en C-08.

## Goals / Non-Goals

**Goals:**

- Agregar `DELETE /libros/{id}` → **204** con baja lógica (`borrado_en = now()`),
  reusando `SoftDeleteRepository.soft_delete`.
- Agregar `POST /libros/{id}/reponer` → **200**, reusando el punto único
  `aplicar_movimiento` con motivo `'Reposición'` y validando `cantidad > 0`,
  libro vigente (409 si está dado de baja) y existencia (404).
- Agregar `GET /libros/{id}/movimientos` → **200** con `cantidad` firmada, `motivo`,
  `cuando`, `usuario_id`, `venta_id` (nulo si no es venta), con precarga de libro
  incluyendo los dados de baja para el título de ventas viejas.
- Garantizar la re-alta con ISBN de un libro dado de baja → **201** y un segundo libro
  vigente con ese ISBN → **409**, por el índice único parcial (ya instalado).
- Asegurar que la precarga de renglones de venta no filtra borrados (consumido por C-10).

**Non-Goals:**

- No se tocan `models.py` ni se agregan migraciones.
- No se implementa autenticación/autorización (C-11/C-13); los endpoints quedan
  preparados para recibir `requiere_rol('ADMIN')` cuando esté disponible.
- No se tocan los módulos `editoriales`, `generos`, `autores`, `clientes`, `ventas`,
  `usuarios`.
- No se implementa la venta transaccional (C-16); sólo se deja el punto de decisión
  para que rechace libros dados de baja (409).

## Decisions

### D-1: Reuso de `SoftDeleteRepository` para la baja

- **Decisión**: `dar_de_baja(uow, libro_id)` carga la entidad con `uow.libros.get_by_id`
  (que ya filtra borrados → `None` si no existe o está dado de baja → **404**),
  llama `await uow.libros.soft_delete(libro)` (escribe `borrado_en = now()` + `flush()`)
  dentro del `async with`.
- **Rationale**: reusa el filtro por defecto y la escritura de `borrado_en`; no hace
  falta un método nuevo. El 404 cubre «ya dado de baja o inexistente» con una sola
  consulta (`RN-13`).

### D-2: Reposición reusa el punto único de stock

- **Decisión**: `reponer(uow, libro_id, cantidad, usuario_actual)`:
  1. Valida `cantidad > 0` por schema (`Field(gt=0)`) → 422 antes de entrar; además
     validación defensiva en el servicio.
  2. `async with uow`:
     - `libro = await uow.libros.get_by_id(libro_id)` → `None` → **404**.
     - si `libro.borrado_en is not None` → **409** (libro dado de baja).
     - `await uow.libros.aplicar_movimiento(libro, cantidad, 'Reposición', usuario_id)`.
  3. Tras el `async with`, devolver el libro recargado con precarga.
- **Rationale**: un solo método escribe `stock` + movimiento (`RN-11`); la validación
  de `cantidad` se hace en el contrato (`extra="forbid"` + `gt=0`) y en el servicio.

### D-3: Consulta de movimientos

- **Decisión**: `movimientos(uow, libro_id)`:
  - `async with uow`:
    - `libro = await uow.libros.get_by_id(libro_id)` → `None` → **404**.
    - consultar `MovimientoStock` por `libro_id` ordenado por `cuando` (y `id`).
  - Devolver lista de dicts/schemas con `cantidad`, `motivo`, `cuando`, `usuario_id`,
    `venta_id`.
- **Precarga**: la consulta de movimientos no necesita precarga de libro; el título
  para ventas viejas lo resuelve C-10 con `get_by_id_including_deleted`.
- **Rationale**: el movimiento ya guarda `venta_id` y `usuario_id`; no hay que
  reconstruir nada. Orden estable por `cuando`.

### D-4: Re-alta con ISBN de un libro dado de baja

- **Decisión**: no requiere código nuevo: el alta (`crear`) ya inserta el libro y el
  índice único parcial `uq_libro_isbn_vigente` (`WHERE borrado_en IS NULL`) permite
  el ISBN de un libro dado de baja y rechaza un segundo vigente con ese ISBN (409).
  Se verifica en tests.
- **Rationale**: la garantía es de la base, no de una consulta previa (`RN-01`).

### D-5: Precarga de renglones de venta que no filtra borrados

- **Decisión**: el repositorio de libros expone `get_by_id_including_deleted` (heredado
  de `SoftDeleteRepository`) para que C-10 precargue el libro de cada renglón sin
  filtrar borrados. No se modifica el filtro por defecto de `get_by_id`.
- **Rationale**: `CV-02` (precarga sólo en `repository.py`); el filtro por defecto
  se preserva para el catálogo.

### D-6: Schemas

- **Decisión**:
  - `ReponerCreate` (o `ReponerStock`): `cantidad: int = Field(gt=0)`.
  - `MovimientoStockRead`: `id`, `libro_id`, `venta_id: Optional[int]`, `usuario_id`,
    `cantidad: int`, `motivo: str`, `cuando: datetime`.
  - No se agrega schema de baja (204 sin cuerpo).
- **Rationale**: el contrato fija `cantidad > 0` → 422 (`extra="forbid"`).

### D-7: Autorización (punto de decisión)

- **Decisión**: `DELETE /libros/{id}`, `POST /libros/{id}/reponer` y
  `GET /libros/{id}/movimientos` son de `ADMIN` (`requiere_rol('ADMIN')`). Hasta que
  `requiere_rol` esté disponible (C-11/C-13), el servicio deja el parámetro
  `usuario_actual` opcional y el punto de decisión documentado; el cableado se completa
  en C-13 sin cambiar la firma. `GET /libros/{id}/movimientos` puede quedar para ADMIN
  (consistente con US-027: «Como ADMIN»).
- **Rationale**: coincide con el patrón de C-08 (D-9).

## Risks / Trade-offs

- [Stock escrito por fuera del punto único en la reposición] → Se mitiga reusando
  `aplicar_movimiento`; además el `grep` de la capa busca `stock =` / `stock +=` fuera
  de `repository.py`.
- [Doble rollback/commit] → El servicio captura `IntegrityError` sin llamar a
  `session.rollback()`; el rollback lo hace el `__aexit__` del UoW.
- [Filtro de borrados en movimientos] → `get_by_id` filtra borrados, por lo que un
  libro dado de baja responde 404 en movimientos (consistente con el detalle público).
- [Re-alta con UNIQUE común] → Se verifica el índice parcial en el modelo y en las
  migraciones (ya instalado en C-03/C-04); no se agrega código nuevo.
- [Autorización de los endpoints] → El 401/403 depende de C-11/C-13. Se deja el punto
  de decisión en el servicio y se cablea cuando estén disponibles, sin cambiar la firma.

## Migration Plan

No hay cambios de esquema ni de datos. El change es aditivo/refactor sobre
`app/modules/libros/`. Rollback: revertir los archivos modificados (los `models.py` no
cambian, por lo que no hay riesgo de esquema). No se requiere
`alembic upgrade/downgrade`.

## Open Questions

Ninguna que afecte specs, enfoque ni desglose de tareas. La serialización de
`MovimientoStock` se mantiene en el servicio (`to_movimiento_read`); si C-10/C-16
necesitan más campos, extienden el schema sin romper el de C-09.