# Design — C-02 core-repositorios-uow-paginacion

## Context

Ver `proposal.md` — Why. El esqueleto de `C-01` ya dejó `get_session` (una sesión por petición que se
cierra en `finally`) y el motor en `app.state`. La capa de repositorios se apoya en esa sesión: no la
crea ni la cierra. Los módulos de dominio siguen con el patrón del TP cap. 1-4 (servicio recibe
`AsyncSession`, router hace `commit()`); `C-02` no los migra, sólo crea la infraestructura que
`C-06`…`C-10` y `C-15` adoptarán.

Restricciones que mandan sobre el diseño:
- Reglas duras 1-4 de `AGENTS.md`: el router construye el UoW, el servicio lo abre, los repositorios
  sólo `flush()`, `selectinload` sólo en `repository.py`.
- `CV-01`: quién construye / abre / confirma / cierra queda documentado en cada archivo.
- `CV-03`: paths exactos `app/core/{repository,unit_of_work,paginacion}.py`.
- `knowledge-base/08_arquitectura_propuesta.md` §El Unit of Work, §Los dos repositorios, §Qué puede y
  qué no puede cada capa.
- Dinero en `NUMERIC`/`Decimal`, fechas nuevas en `timestamptz` (no aplica directamente acá, pero los
  modelos que consumen esta capa sí lo cumplen).

## Goals / Non-Goals

**Goals:**
- Dejar `BaseRepository[T]` y `SoftDeleteRepository[T]` con la firma y los métodos del roadmap, sin
  `commit()` en ningún método.
- Dejar `UnitOfWork` con `commit`/`rollback` en `__aexit__` y sin cierre de sesión.
- Dejar `Pagina[T]` y `paginar(...)` con validación y el envoltorio `{items, total, page, size, pages}`.
- Dejar la plantilla de `<módulo>/unit_of_work.py` documentada y un ejemplo en el docstring del base.
- Dejar el comentario de contrato (`CV-01`) en cada archivo.

**Non-Goals (de diseño):**
- No se migra ningún módulo existente a la nueva capa (eso es `C-06`…`C-10`); los routers siguen
  haciendo `commit()`.
- No se crea ninguna carpeta de módulo vacía (`C-01` D-07): la plantilla se documenta, no se instancia
  en un módulo ficticio.
- No se conecta `paginar()` a los listados existentes (eso es `C-05`).
- No se define el manejo de `IntegrityError` ni los schemas por módulo (eso es `C-05`).

## Decisions

### D-01 — `BaseRepository` usa `AsyncSession` directamente y el modelo como atributo

**Decisión**: `BaseRepository[T]` guarda `session` y `model_class` como atributos privados; los métodos
usan `session.get(...)`, `session.execute(select(model_class)...)`, `session.add(...)`, `session.flush()`,
`session.delete(...)`. El genérico `T` es sólo para tipado estático; en runtime se borra (el roadmap lo
dice explícitamente).

**Por qué**:
- `session.get(Model, id)` es el camino canónico y eficiente de SQLAlchemy 2.0 para PK.
- Pasar `model_class` al constructor (en vez de fijarlo en la subclase) permite reutilizar la misma
  clase base para todas las entidades sin duplicar código.
- `flush()` (no `commit()`) deja el `commit` al `__aexit__` del UoW, cumpliendo `CV-02`.

**Alternativas descartadas**:
- *Un repositorio por entidad con métodos hardcodeados*: duplica la lógica y es lo que se quiere evitar.
- *`session.execute(select(...))` para `get_by_id`*: funciona, pero `session.get` es más directo y usa la
  identidad del ORM.

### D-02 — `SoftDeleteRepository` sobrescribe los métodos de lectura y cuenta

**Decisión**: hereda de `BaseRepository` y sobrescribe `get_by_id`, `get_all` y `count` para agregar el
filtro `borrado_en IS NULL` (vía `model.borrado_en.is_(None)`). Agrega `get_by_id_including_deleted`
(reusa `session.get`, sin filtro) y `soft_delete` (setea `borrado_en = now()` + `flush()`).

**Por qué**:
- El filtro vive en el repositorio, no en el modelo ni en el servicio (`CV-03` y `RN-13`).
- `get_by_id_including_deleted` es necesario para que `GET /ventas/{id}` siga mostrando el título de un
  libro dado de baja (precarga que no filtra).
- `soft_delete` no existe en la base: la regla dura 2 y `RN-13` lo exigen sólo donde hay borrado lógico.

**Alternativas descartadas**:
- *Filtrar en el modelo con un `default_scope`*: SQLAlchemy no tiene scopes automáticos como Eloquent;
  forzarlo en el modelo oculta la precarga y viola `CV-03`.
- *Un parámetro `include_deleted=False` en los métodos base*: contamina la clase base con un concepto que
  sólo aplica a `Libro`.

**Limitación conocida**: `SoftDeleteRepository` asume que el modelo tiene la columna `borrado_en`. Se usa
sólo para `Libro` (y documentado así). Si se aplica a un modelo sin esa columna, falla al importar/​usar;
es responsabilidad del módulo usar la clase correcta.

### D-03 — `UnitOfWork` no posee ni cierra la sesión

**Decisión**: `__init__(session)` guarda la sesión; `__aenter__` devuelve `self`; `__aexit__` hace
`commit()` si `exc_type is None` y `rollback()` en caso contrario, y devuelve `False` (no suprime la
excepción). No llama a `close()`.

**Por qué**:
- La sesión la crea `get_session` (una por petición, se cierra en `finally`); el UoW no la creó y no debe
  cerrarla (`CV-01`, regla dura 3).
- Devolver `False` deja propagar la excepción para que FastAPI la traduzca (409/422/etc.).
- El `commit`/`rollback` en `__aexit__` es la única frontera de transacción (`RN-10`, `RN-16`).

**Alternativas descartadas**:
- *Cerrar la sesión en `__aexit__`*: rompe `get_session` (doble close) y oculta el ciclo de vida.
- *`__aexit__` que suprime excepciones*: enmascara errores y rompe la traducción a HTTP.

### D-04 — `Pagina[T]` como modelo Pydantic genérico

**Decisión**: `Pagina(BaseModel, Generic[T])` con campos `items: list[T]`, `total`, `page`, `size`,
`pages`, y `model_config = {"from_attributes": True}` para que los módulos puedan construirla a partir
de objetos ORM si hace falta.

**Por qué**:
- FastAPI serializa Pydantic de forma nativa y permite `response_model=Pagina[LibroRead]`.
- `from_attributes=True` facilita la construcción desde ORM en los módulos siguientes.
- El genérico mantiene el tipado estático.

**Alternativas descartadas**:
- *`dataclass` genérico*: FastAPI lo soporta, pero Pydantic es el estándar del proyecto (schemas con
  `extra="forbid"`).
- *Un dict suelto*: pierde tipado y validación; el roadmap pide un tipo `Pagina[T]`.

### D-05 — `paginar` valida, cuenta con los mismos filtros y pagina

**Decisión**: firma `paginar(session, stmt, page=1, size=20)`. Valida `page ≥ 1` y `size` 1..100 (422
con mensaje propio). Calcula `total` con `select(func.count()).select_from(stmt.subquery())` (mismos
filtros). Calcula `pages = max(1, ceil(total/size))`. Si `page > pages`, responde 422 con
`"La página {page} no existe: hay {pages}"`. Ejecuta `stmt.offset((page-1)*size).limit(size)` y devuelve
`Pagina(items=..., total=..., page=..., size=..., pages=...)`. Con cero resultados devuelve
`items=[]`, `total=0`, `pages=1`.

**Por qué**:
- El conteo usa el mismo `stmt` (con sus `WHERE`), garantizando `total` con los mismos filtros
  (checklist §9).
- La validación de rango ocurre antes de consultar la página, con mensaje legible.
- `ceil(total/size)` con `max(1, …)` cubre el caso de cero resultados (`pages=1`).

**Alternativas descartadas**:
- *Pasar `page`/`size` ya validados por el router*: duplica la validación y rompe el contrato «paginar
  valida».
- *Contar en Python (`len(items)`)*: no sirve porque `items` ya está paginado.

### D-06 — La plantilla de UoW por módulo se documenta, no se instancia

**Decisión**: no se crea ninguna carpeta de módulo en `C-02`. La plantilla vive como docstring/comentario
en `app/core/unit_of_work.py`, con el ejemplo de `VentasUnitOfWork` del KB. Los changes `C-06`…`C-10` y
`C-15` la replican creando su propio `<módulo>/unit_of_work.py`.

**Por qué**:
- `C-01` D-07 prohíbe carpetas de módulo vacías; crear un `_template/` violaría la estructura obligatoria
  (`CV-03`).
- La plantilla es un patrón, no un artefacto ejecutable; documentarla es suficiente y evita código muerto.

**Alternativas descartadas**:
- *Crear `app/modules/_template/unit_of_work.py`*: código muerto que el corrector podría confundir con un
  módulo real.

### D-07 — Comentario de contrato en cada archivo

**Decisión**: cada uno de los tres archivos abre con un docstring que enumera los cuatro roles de
`CV-01`: quién construye, quién abre, quién confirma, quién cierra.

**Por qué**: el checklist §7 y la rúbrica miran exactamente esa separación; el comentario evita que el
primer módulo (`C-06`) copie un patrón incorrecto.

## Risks / Trade-offs

- [La clase base asume PK entera] → `get_by_id` tipa `int`; si un modelo usa otro tipo de PK (no es el
  caso acá, todos son `bigint`), se ajusta en la subclase. Mitigación: tipar como `Any` para no bloquear.
- [SoftDeleteRepository asume `borrado_en`] → documentado en el docstring; sólo se usa para `Libro`.
  Mitigación: usarlo únicamente donde el modelo tenga esa columna.
- [paginar cuenta con `stmt.subquery()`] → requiere que el `stmt` sea un `Select` válido con FROM.
  Mitigación: los módulos siempre pasan un `select(Model)` con sus filtros; se documenta en el docstring.
- [Pydantic genérico `Pagina[T]`] → la validación de items depende de `T`; si `T` es un SQLModel sin
  `from_attributes`, la construcción puede fallar. Mitigación: `from_attributes=True` en la config base y
  responsabilidad del módulo de pasar el tipo correcto.
- [No se migra ningún módulo en este change] → los endpoints existentes siguen con el patrón viejo hasta
  `C-06`. Mitigación: es intencional; `C-06`…`C-10` adoptan la capa.

## Migration Plan

1. Crear los tres archivos en `parcial/app/core/` (`repository.py`, `unit_of_work.py`, `paginacion.py`).
   No hay migraciones nuevas ni cambios de esquema: rollback = borrar los tres archivos.
2. No se toca `main.py`, routers ni modelos: la aplicación sigue arrancando igual.
3. `C-05` conectará `paginar()` a los listados existentes; `C-06`…`C-10` replicarán la plantilla de UoW.

## Open Questions

Ninguna que cambie las specs, el enfoque o las tasks. La firma exacta de `paginar` (si recibe el `stmt`
o los filtros por separado) se podría refinar en `C-05`, pero la decisión de este change (recibir un
`Select` con filtros aplicados) ya permite contar con los mismos filtros y no bloquea a nadie.