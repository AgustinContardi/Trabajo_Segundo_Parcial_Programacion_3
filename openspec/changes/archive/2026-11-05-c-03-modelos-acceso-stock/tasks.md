# Tasks — C-03 modelos-acceso-stock

> Todo path de la aplicación es relativo a `parcial/`. Este change **sólo define modelos** en
> `app/modules/{usuarios,libros,clientes}`; no crea migraciones, routers, schemas ni servicios. La
> verificación se hace por importación y por inspección del metadata de SQLModel (sin base real
> alcanza para importar y hacer `grep`; las comprobaciones contra PostgreSQL quedan para `C-04`).

## 1. Módulo `usuarios` — modelos de acceso (`app/modules/usuarios/models.py`)

- [x] 1.1 Crear `parcial/app/modules/usuarios/__init__.py` y `parcial/app/modules/usuarios/models.py` con
  `Usuario` (6 columnas: `id`, `email` UNIQUE, `nombre`, `password_hash`, `activo`, `debe_cambiar_password`),
  **sin** columna `rol`. Verificar: `python -c "from app.modules.usuarios.models import Usuario; print('ok')"`.
- [x] 1.2 Agregar `AsignacionRol` (7 columnas: `id`, `usuario_id` FK+índice, `rol` CHECK, `desde`, `vence_en`,
  `revocada_en`, `otorgada_por` FK+índice) con el índice único parcial `(usuario_id, rol) WHERE revocada_en IS NULL`
  usando `postgresql_where`. Verificar: import OK y `grep -n "postgresql_where" app/modules/usuarios/models.py`.
- [x] 1.3 Agregar `IntentoAcceso` (5 columnas: `id`, `cuando`, `email`, `ip`, `exito`) con índice
  `(email, ip, cuando)`, sin FKs ni CHECKs. Verificar: import OK + inspección de `__table_args__`.
- [x] 1.4 Agregar `EventoSeguridad` (4 columnas: `id`, `cuando`, `actor` **Text**, `accion`), sin FKs ni CHECKs.
  Verificar: import OK + `grep -n "Text" app/modules/usuarios/models.py`.
- [x] 1.5 Declarar la navegación en los dos extremos: `Usuario.cliente` (objeto, no lista) y, en `clientes`,
  `Cliente.usuario` (objeto). Verificar: `grep -n "back_populates=\"cliente\"\|back_populates=\"usuario\""
  app/modules/usuarios/models.py app/modules/clientes/models.py` muestra ambas declaraciones.
- [x] 1.6 Verificar la ausencia de `rol` en `Usuario` y de relaciones en `IntentoAcceso`/`EventoSeguridad`:
  `grep -n "rol" app/modules/usuarios/models.py` no debe mostrar columna `rol` en `Usuario`; los dos modelos
  de auditoría no contienen `Relationship`.

## 2. Módulo `libros` — `MovimientoStock` y borrado lógico (`app/modules/libros/models.py`)

- [x] 2.1 Agregar `MovimientoStock` (7 columnas: `id`, `libro_id` FK+índice, `venta_id` FK+índice nulo,
  `usuario_id` FK+índice, `cantidad` CHECK `<> 0`, `motivo`, `cuando` timestamptz). Verificar:
  `python -c "from app.modules.libros.models import MovimientoStock; print('ok')"`.
- [x] 2.2 Agregar `Libro.borrado_en` (`timestamptz`, nulo, default `None`). Verificar: el campo existe y su
  columna es `DateTime(timezone=True)`.
- [x] 2.3 Reemplazar `UniqueConstraint("isbn", ...)` por el índice único parcial
  `(isbn) WHERE borrado_en IS NULL` con `postgresql_where`. Verificar:
  `grep -n "postgresql_where\|UniqueConstraint(\"isbn\"" app/modules/libros/models.py` muestra el índice
  parcial y **no** muestra el `UniqueConstraint` común.
- [x] 2.4 Conservar `CheckConstraint("precio > 0", ...)` y `CheckConstraint("stock >= 0", ...)`. Verificar:
  `grep -n "precio > 0\|stock >= 0" app/modules/libros/models.py`.
- [x] 2.5 Dejar `LibroAutor` sin cambios. Verificar: `git diff --stat` no muestra cambios en la clase
  `LibroAutor` (sólo adiciones en `Libro` y `MovimientoStock`).
- [x] 2.6 Declarar la relación `Libro.movimientos` ↔ `MovimientoStock.libro` (objeto/lista según cardinalidad)
  con `TYPE_CHECKING`. Verificar: import OK sin errores de importación circular.

## 3. Módulo `clientes` — `usuario_id` y navegación (`app/modules/clientes/models.py`)

- [x] 3.1 Agregar `Cliente.usuario_id` (bigint, nulo, UNIQUE, FK a `usuario.id`, con índice). Verificar:
  `python -c "from app.modules.clientes.models import Cliente; print('ok')"`.
- [x] 3.2 Declarar `Cliente.usuario` como objeto (no lista) con `back_populates="cliente"`. Verificar:
  `grep -n "usuario:" app/modules/clientes/models.py`.
- [x] 3.3 Declarar `Usuario.cliente` como objeto en `usuarios/models.py` (ya en 1.5). Verificar: import conjunto
  `python -c "from app.modules.usuarios.models import Usuario; from app.modules.clientes.models import Cliente; print('ok')"`.
- [x] 3.4 Dejar `PerfilCliente` 1—1 intacto (`cliente_id` NOT NULL, UNIQUE, FK, índice). Verificar:
  `grep -n "cliente_id" app/modules/clientes/models.py` muestra `nullable=False, unique=True, index=True`.

## 4. Tipos, convenciones y verificación integral

- [x] 4.1 Verificar que todas las fechas nuevas son `timestamptz` (`DateTime(timezone=True)`): `grep -n
  "DateTime" app/modules/usuarios/models.py app/modules/libros/models.py app/modules/clientes/models.py`.
- [x] 4.2 Verificar que no aparece `float` en los modelos nuevos/modificados:
  `grep -n "float" app/modules/usuarios/models.py app/modules/libros/models.py app/modules/clientes/models.py`
  no devuelve líneas.
- [x] 4.3 Verificar que toda FK nueva tiene `index=True`: inspección de `sa_column=Column(..., index=True)` en
  `usuario_id`, `otorgada_por`, `libro_id`, `venta_id`, `usuario_id` (movimiento), `cliente.usuario_id`.
- [x] 4.4 Verificar la importación conjunta de todos los modelos:
  `python -c "import app.modules.usuarios.models, app.modules.libros.models, app.modules.clientes.models, app.modules.ventas.models; print('ok')"`.
- [x] 4.5 Verificar la asignación a módulos: `grep -rn "class AsignacionRol\|class IntentoAcceso\|class EventoSeguridad\|class MovimientoStock\|class PerfilCliente\|class RenglonVenta" app/modules`
  muestra cada clase en su módulo asignado.
- [x] 4.6 Verificar que no se creó ninguna migración ni se tocó `main.py`/`app/core/`:
  `git status --short` muestra sólo cambios en `app/modules/{usuarios,libros,clientes}/models.py` (y los
  artefactos de `openspec/`).

## Workflow follow-up

- Archivar el change con `/opsx:archive` una vez verificada la implementación y marcar `C-03` como `[x]` en
  `CHANGES.md`.
- `C-04` autogenera las migraciones `0003`/`0004` a partir de estos modelos.