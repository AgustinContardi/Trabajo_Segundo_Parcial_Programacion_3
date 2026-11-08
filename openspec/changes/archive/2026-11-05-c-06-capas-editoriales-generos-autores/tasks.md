# Tasks — C-06 capas-editoriales-generos-autores

## 1. Repositorios por entidad

- [x] 1.1 Crear `parcial/app/modules/editoriales/repository.py` con
      `EditorialRepository(BaseRepository[Editorial])` y el método `libros_de(editorial_id)`
      que filtra `Libro.borrado_en IS NULL`; verificar que `python -c "import app.modules.editoriales.repository"` no falla.
- [x] 1.2 Crear `parcial/app/modules/generos/repository.py` con
      `GeneroRepository(BaseRepository[Genero])` y `libros_de(genero_id)` filtrando
      borrados; verificar import OK.
- [x] 1.3 Crear `parcial/app/modules/autores/repository.py` con
      `AutorRepository(BaseRepository[Autor])` y `libros_de(autor_id)` filtrando borrados;
      verificar import OK.

## 2. Unit of Work por módulo

- [x] 2.1 Crear `parcial/app/modules/editoriales/unit_of_work.py` con
      `EditorialesUnitOfWork(UnitOfWork)` que compone `EditorialRepository` con la misma
      sesión y la dependencia `get_editoriales_uow`; verificar import OK.
- [x] 2.2 Crear `parcial/app/modules/generos/unit_of_work.py` con `GenerosUnitOfWork`
      y `get_generos_uow`; verificar import OK.
- [x] 2.3 Crear `parcial/app/modules/autores/unit_of_work.py` con `AutoresUnitOfWork`
      y `get_autores_uow`; verificar import OK.

## 3. Servicios sin `AsyncSession`

- [x] 3.1 Reescribir `parcial/app/modules/editoriales/service.py` para recibir
      `EditorialesUnitOfWork` (no `AsyncSession`), con `crear`, `obtener`, `listar`,
      `actualizar` y `libros_de`, abriendo el UoW con `async with` y traduciendo
      `IntegrityError` a `409`/`422`; verificar `grep -n "AsyncSession" service.py` vacío.
- [x] 3.2 Reescribir `parcial/app/modules/generos/service.py` con `crear`, `obtener`,
      `listar` y `libros_de` bajo el mismo patrón; verificar `grep -n "AsyncSession"`
      vacío.
- [x] 3.3 Reescribir `parcial/app/modules/autores/service.py` con `crear`, `obtener`,
      `actualizar` y `libros_de` bajo el mismo patrón; verificar `grep -n "AsyncSession"`
      vacío.

## 4. Routers que construyen el UoW

- [x] 4.1 Reescribir `parcial/app/modules/editoriales/router.py` para depender de
      `get_editoriales_uow`, sin `session.commit()` ni precarga; verificar
      `grep -n "commit\|selectinload\|AsyncSession" router.py` vacío.
- [x] 4.2 Reescribir `parcial/app/modules/generos/router.py` bajo el mismo patrón;
      verificar `grep -n "commit\|selectinload\|AsyncSession" router.py` vacío.
- [x] 4.3 Reescribir `parcial/app/modules/autores/router.py` bajo el mismo patrón;
      verificar `grep -n "commit\|selectinload\|AsyncSession" router.py` vacío.

## 5. Verificación de la capa

- [x] 5.1 Ejecutar `grep -rn "AsyncSession\|UnitOfWork(" parcial/app/modules/*/service.py`
      y confirmar que no devuelve resultados.
- [x] 5.2 Ejecutar `python -m py_compile` sobre los archivos nuevos/modificados de los
      tres módulos y `python -c "import app.main"` para verificar el arranque.
- [x] 5.3 Ejecutar `grep -rn "selectinload" parcial/app/modules/*/service.py
      parcial/app/modules/*/router.py` y confirmar que no devuelve resultados.

## Workflow follow-up

- Archivar el change con `/opsx:archive` y marcar `[x]` en `CHANGES.md` una vez
  verificada la aceptación (§1, §7 y §9 del checklist).
- Actualizar el estado del change en `CHANGES.md` a `[x]`.
## Errata (2026-11-08)

Corrección del change `fix-auditoria-final` (C-06, tarea 6.5). La tarea 5.2
original dice `python -c "import app.main"`; esa cita es incorrecta porque el
paquete de la aplicación se llama `app` pero el entrypoint se importa como
`main` con `PYTHONPATH=parcial`. La evidencia reproducible es:

    cd parcial
    $env:PYTHONPATH='parcial'
    python -c "import main"

No se modifican tareas, estados ni checkboxes originales: la errata sólo deja
la cita correcta para quien reproduzca la evidencia.
