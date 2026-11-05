# Tasks — C-02 core-repositorios-uow-paginacion

> Todo path de la aplicación es relativo a `parcial/`. Este change **no** migra ningún módulo: sólo crea la
> infraestructura compartida en `app/core/` y documenta la plantilla de UoW por módulo. Las tareas de
> verificación se corren contra `parcial/` con el entorno del TP cap. 1-4 adoptado (sin base real alcanza
> para importar y hacer `grep`; los tests contra PostgreSQL quedan para `C-19`).

## 1. Repositorio base (`app/core/repository.py`)

- [x] 1.1 Crear `parcial/app/core/repository.py` con la clase genérica `BaseRepository[T]` y el constructor
  `(session: AsyncSession, model_class: type[T])`, guardando ambos como atributos privados. Verificar:
  `python -c "from app.core.repository import BaseRepository; print('ok')"`.
- [x] 1.2 Implementar `get_by_id(id)` con `session.get(model_class, id)` y devolución `T | None`.
  Verificar: lectura del archivo + `python -c "import app.core.repository"` sin error.
- [x] 1.3 Implementar `get_all()` con `select(model_class)` y `result.scalars().all()`. Verificar: el método
  existe y no contiene `commit()` ni `rollback()`.
- [x] 1.4 Implementar `count()` con `select(func.count()).select_from(model_class)`. Verificar: el método
  existe y devuelve `int`.
- [x] 1.5 Implementar `add(entity)` con `session.add(entity)` + `await session.flush()` + devolución de la
  entidad. Verificar: no hay `commit()` en el método.
- [x] 1.6 Implementar `update(entity)` con `await session.flush()` y devolución de la entidad. Verificar: no
  hay `commit()` en el método.
- [x] 1.7 Implementar `delete(entity)` con `await session.delete(entity)` + `await session.flush()`.
  Verificar: no hay `commit()` en el método.
- [x] 1.8 Verificar la ausencia global de `commit`/`rollback` en el archivo: `grep -n "commit\|rollback"
  app/core/repository.py` no devuelve líneas. Verificación: el comando no devuelve coincidencias.

## 2. Repositorio con borrado lógico (`SoftDeleteRepository`)

- [x] 2.1 Agregar `SoftDeleteRepository[T]` que herede de `BaseRepository[T]` y documente en el docstring
  que asume el modelo con columna `borrado_en`. Verificar: `python -c "from app.core.repository import
  SoftDeleteRepository; print('ok')"`.
- [x] 2.2 Sobrescribir `get_by_id`, `get_all` y `count` para filtrar `borrado_en IS NULL` (vía
  `model.borrado_en.is_(None)`). Verificar: `grep -n "is_(None)\|borrado_en" app/core/repository.py`
  muestra el filtro en los tres métodos.
- [x] 2.3 Implementar `get_by_id_including_deleted(id)` con `session.get(model_class, id)` sin filtro.
  Verificar: el método existe y no filtra `borrado_en`.
- [x] 2.4 Implementar `soft_delete(entity)` que setee `entity.borrado_en = datetime.now(timezone.utc)` y
  haga `flush()`. Verificar: el método existe y no hay `commit()`.
- [x] 2.5 Verificar que `get_by_id_including_deleted` y `soft_delete` **no** existen en `BaseRepository`:
  inspeccionar la clase base y confirmar su ausencia. Verificación: `grep -n "get_by_id_including_deleted\|
  soft_delete" app/core/repository.py` muestra sólo las definiciones dentro de `SoftDeleteRepository`.

## 3. Unit of Work base (`app/core/unit_of_work.py`)

- [x] 3.1 Crear `app/core/unit_of_work.py` con la clase `UnitOfWork` y el constructor `(session:
  AsyncSession)` que guarda la sesión como atributo privado. Verificar: `python -c "from
  app.core.unit_of_work import UnitOfWork; print('ok')"`.
- [x] 3.2 Implementar `__aenter__` devolviendo `self`. Verificar: lectura del archivo.
- [x] 3.3 Implementar `__aexit__(exc_type, exc, tb)` con `commit()` si `exc_type is None`, `rollback()` en
  caso contrario, y devolución `False` (no suprime la excepción). Verificar: lectura del archivo + el
  método no llama a `close()`.
- [x] 3.4 Verificar la ausencia de `close()` en el archivo: `grep -n "close()" app/core/unit_of_work.py`
  no devuelve líneas. Verificación: el comando no devuelve coincidencias.
- [x] 3.5 Dejar en el docstring el comentario de contrato `CV-01` (quién construye / abre / confirma /
  cierra) y el ejemplo de plantilla de `<módulo>/unit_of_work.py` (con `VentasUnitOfWork` del KB).
  Verificar: lectura del archivo muestra el comentario y el ejemplo.

## 4. Paginación (`app/core/paginacion.py`)

- [x] 4.1 Crear `app/core/paginacion.py` con la clase genérica `Pagina(BaseModel, Generic[T])` y los campos
  `items: list[T]`, `total: int`, `page: int`, `size: int`, `pages: int`, con
  `model_config = {"from_attributes": True}`. Verificar: `python -c "from app.core.paginacion import
  Pagina; print('ok')"`.
- [x] 4.2 Implementar `paginar(session, stmt, page=1, size=20)` con validación de `page ≥ 1` (422 con
  mensaje propio) y `size` 1..100 (422 con mensaje propio). Verificar: lectura del archivo.
- [x] 4.3 Implementar el conteo `total` con `select(func.count()).select_from(stmt.subquery())`. Verificar:
  `grep -n "subquery\|func.count" app/core/paginacion.py` muestra ambas.
- [x] 4.4 Implementar el cálculo `pages = max(1, ceil(total / size))` y la comprobación de página fuera de
  rango con el mensaje `"La página {page} no existe: hay {pages}"` (422). Verificar: lectura del archivo.
- [x] 4.5 Implementar la consulta paginada `stmt.offset((page - 1) * size).limit(size)` y la devolución de
  `Pagina(items=..., total=..., page=..., size=..., pages=...)`. Verificar: lectura del archivo.
- [x] 4.6 Verificar el caso de cero resultados: con `total = 0`, `pages = 1` e `items = []`. Verificación:
  revisión del código + (con base real) una consulta vacía devuelve el envoltorio con `pages: 1`.
- [x] 4.7 Verificar los imports y la ausencia de `commit`/`close` en el archivo: `grep -n "commit\|close"
  app/core/paginacion.py` no devuelve líneas. Verificación: el comando no devuelve coincidencias.

## 5. Contrato y verificación integral

- [x] 5.1 Verificar que los tres archivos existen en `app/core/`: `ls app/core` muestra `repository.py`,
  `unit_of_work.py`, `paginacion.py`. Verificación: `Get-ChildItem app/core` (sin alias).
- [x] 5.2 Verificar que los tres archivos abren con el comentario de contrato `CV-01` (quién construye /
  abre / confirma / cierra). Verificación: lectura del primer bloque de cada archivo.
- [x] 5.3 Verificar que `main.py` no se modificó y no importa los nuevos módulos (la adopción es posterior).
  Verificación: `git diff --stat` no muestra cambios en `main.py` ni en routers.
- [x] 5.4 Verificar que no se creó ninguna carpeta de módulo nueva: `Get-ChildItem app/modules` muestra las
  mismas que antes (`health` y los del TP). Verificación: comparación con el estado previo.
- [x] 5.5 Verificar que no hay `create_all` nuevo ni credenciales versionadas: `grep -rn "create_all"
  parcial --include=*.py` vacío. Verificación: el comando no devuelve líneas.
- [x] 5.6 Verificar la importación conjunta: `python -c "from app.core.repository import BaseRepository,
  SoftDeleteRepository; from app.core.unit_of_work import UnitOfWork; from app.core.paginacion import Pagina,
  paginar; print('ok')"`. Verificación: imprime `ok` sin traceback.

## Workflow follow-up

- Archivar el change con `/opsx:archive` una vez verificada la implementación y marcar `C-02` como `[x]` en
  `CHANGES.md`.
- `C-05` conectará `paginar()` a los listados existentes y refinará los mensajes de error.
- `C-06`…`C-10` y `C-15` replicarán la plantilla de `<módulo>/unit_of_work.py`.