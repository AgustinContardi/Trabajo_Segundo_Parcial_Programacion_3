# Proposal — C-09 libros-baja-reposicion-movimientos

## Why

C-08 dejó el módulo `libros` con seis capas y el punto único de escritura de stock, pero
la **baja lógica**, la **reposición** y la **consulta de movimientos** siguen sin existir.
Sin ellas no se puede cumplir `RN-13` (un libro dado de baja deja de aparecer en el catálogo
y no se puede vender ni reponer, pero sus datos se conservan y las ventas anteriores lo
siguen mostrando) ni `RN-01`/`RN-13` en su parte condicionada (el ISBN es único sólo entre
los vigentes, lo que permite reusarlo tras una baja). Además, el punto único de stock
(`RN-11`) debe usarse también en la reposición, y el detalle de una venta vieja debe seguir
mostrando el título aunque el libro esté dado de baja (precarga que **no** filtra borrados).

C-09 es el primer eslabón de Fase 4 que toca `RN-13` de punta a punta (catálogo, ventas
y stock) y el que cierra el «trap» del `UNIQUE` común en el ISBN: si alguien deja un
`UNIQUE` común, la re-alta con el ISBN de un libro dado de baja falla sin que nada parezca
roto.

## What Changes

- Agregar `DELETE /libros/{id}` → **204** con baja lógica: escribe `borrado_en = now()`;
  el libro desaparece de **todos** los listados y del detalle público; repetir la baja o
  un id inexistente → **404**.
- Agregar `POST /libros/{id}/reponer` → **200** con el libro actualizado; `cantidad > 0`
  (si no, **422**); libro dado de baja → **409**; usa el punto único de stock y deja el
  movimiento de entrada (`motivo = 'Reposición'`).
- Agregar `GET /libros/{id}/movimientos` → **200** con `cantidad` firmada, `motivo`,
  `cuando`, `usuario_id` y `venta_id` (nulo si no vino de una venta).
- Garantizar la **re-alta** con el ISBN de un libro dado de baja → **201**, y un segundo
  libro **vigente** con ese ISBN → **409**, garantizado por el **índice único parcial**
  (no por una consulta previa).
- Asegurar que la precarga de los renglones del detalle de venta **no** filtra borrados:
  una venta vieja sigue mostrando el título (consumido por C-10, pero el repositorio de
  libros ya expone `get_by_id_including_deleted` y la precarga no filtra).
- Reusar el punto único `aplicar_movimiento` (motivo `'Reposición'`) y el filtro de
  borrados por defecto del repositorio.

## Capabilities

### New Capabilities

Ninguna: C-09 no introduce un capability nuevo; extiende el existente `libros`.

### Modified Capabilities

- `libros`: se agregan los requisitos de baja lógica (`DELETE /libros/{id}` → 204,
  desaparición del catálogo y del detalle público, 404 al repetir o si no existe),
  reposición (`POST /libros/{id}/reponer` → 200, `cantidad > 0`, 409 si está dado de baja,
  movimiento de entrada), consulta de movimientos (`GET /libros/{id}/movimientos` → 200
  con `cantidad` firmada, `motivo`, `cuando`, `usuario_id`, `venta_id` nulo si no es venta),
  re-alta con ISBN de un libro dado de baja (201) y segundo vigente (409) garantizado por
  el índice único parcial, y la precarga de renglones de venta que no filtra borrados.

## Impact

- **Código modificado**: `parcial/app/modules/libros/repository.py` (agrega `soft_delete`
  reuso heredado, métodos de reposición y movimientos; `get_by_id_including_deleted` ya
  existe), `service.py` (nuevas funciones `dar_de_baja`, `reponer`, `movimientos`,
  `soft_delete`), `router.py` (nuevas rutas `DELETE`, `POST …/reponer`, `GET …/movimientos`),
  `schemas.py` (schema de reposición y de movimiento de stock).
- **Migraciones**: ninguna nueva (el esquema ya tiene `borrado_en`, el índice parcial del
  ISBN y el disparador append-only de `movimiento_stock`).
- **API**: tres rutas nuevas sobre `/libros`; reusa el punto único de stock y el filtro de
  borrados por defecto.
- **Dependencias aguas abajo**: habilita `C-10` (capas-ventas-lecturas, que precarga el
  libro incluyendo los dados de baja en el detalle de venta) y `C-16` (venta transaccional,
  que rechaza libros dados de baja con 409).
- **Riesgo principal**: que el stock se escriba por fuera del punto único en la reposición
  (rompe `stock = SUM(movimiento_stock.cantidad)`); se mitiga reusando `aplicar_movimiento`.
  Que un `UNIQUE` común en el ISBN rompa la re-alta; se mitiga verificando el índice
  parcial en el modelo y en las migraciones (ya instalado en C-03/C-04).