# Design — C-03 modelos-acceso-stock

## Context

Ver `proposal.md` — Why. El esqueleto de `C-01` adoptó el TP cap. 1-4 (catálogo, clientes, ventas,
migraciones `0001`/`0002`) y `C-02` dejó `BaseRepository`, `UnitOfWork` y `Pagina` en `app/core/`.
Los módulos de dominio existentes (`libros`, `clientes`, `ventas`, `editoriales`, `generos`, `autores`)
ya definen sus modelos con el patrón del TP: `SQLModel(table=True)`, `__tablename__`, `__table_args__`
con `CheckConstraint`/`UniqueConstraint`/`Index`, columnas vía `Field(sa_column=Column(...))` con
`BigInteger`/`Identity()`/`ForeignKey(..., ondelete=...)`/`index=True`, y `Relationship` declarado en
los dos extremos con `TYPE_CHECKING` para evitar imports circulares. `C-03` sigue ese mismo patrón y
sólo agrega lo que la KB §4 fija: las cuatro tablas de acceso, `movimiento_stock`, `Libro.borrado_en`
+ índice parcial del ISBN, y `Cliente.usuario_id` + navegación.

Restricciones que mandan sobre el diseño:
- Reglas duras 6, 7, 10, 11 de `AGENTS.md`: dinero `NUMERIC`/`Decimal`, fechas con zona, toda FK
  nueva con índice, `stock` sólo por `movimiento_stock`.
- `CV-03`: precarga (`selectinload`) sólo en `repository.py` (no aplica acá: este change sólo define
  modelos; las relaciones se declaran, no se precargan).
- KB §4 «Entidades» y «Índices y restricciones»: nombres exactos de tablas, columnas, CHECKs e índices.
- `knowledge-base/10_preguntas_abiertas.md` AB-07: `otorgada_por` es FK a `usuario` (confirmado por la
  figura 1 y por la KB §4, que lo lista como FK); se asume FK, no texto libre.
- `parcial/app/modules/usuarios/` **no existe**: este change crea sólo `models.py` (no routers/schemas/
  service, que son `C-07`/`C-11`). Consistente con `C-01` D-07 (no carpetas vacías): se crea la carpeta
  porque lleva un archivo real.

## Goals / Non-Goals

**Goals:**
- Definir los modelos SQLModel de acceso, stock y los cambios a `libro`/`cliente` con los nombres exactos
  de la KB, listos para que `C-04` autogenere las migraciones `0003`/`0004`.
- Declarar las relaciones en los dos extremos con el tipado correcto (objeto vs lista), incluyendo
  `Cliente.usuario` como objeto y `Usuario.cliente`.
- Expresar los dos índices únicos parciales (`asignacion_rol` y `libro.isbn`) de forma que Alembic los
  infiera con `postgresql_where` en `C-04`.
- Mantener `LibroAutor`, `PerfilCliente`, `RenglonVenta` sin cambios.

**Non-Goals (de diseño):**
- No se crean migraciones (`C-04`), ni seed (`C-16`), ni repositorios por módulo (`C-06`…`C-10`),
  ni rutas (`C-07`…`C-15`).
- No se toca `main.py` ni `app/core/`.
- No se agregan columnas heredadas no confirmadas (`SU-07`/`SU-08`): sólo se agregan las indicadas.
- No se resuelve AB-02 (vendedor en `venta`) ni AB-06 (nombre del precio copiado): fuera de alcance.

## Decisions

### D-01 — Patrón de modelo: seguir el del TP (SQLModel + `sa_column`)

**Decisión**: cada modelo sigue el patrón ya establecido en `parcial/app/modules/{libros,clientes}/
models.py`: `class X(SQLModel, table=True)`, `__tablename__`, `__table_args__` con las restricciones/
índices, campos con `Field(sa_column=Column(...))`, `Identity()` en el PK, y `Relationship` en los dos
extremos dentro de `TYPE_CHECKING`.

**Por qué**:
- Coherencia con el código existente y con las migraciones `0001`/`0002` ya aplicadas: Alembic compara
  contra el metadata de SQLModel; si el patrón cambia, la autogeneración de `C-04` se vuelve
  impredecible.
- La corrección mira nombres y tipos, no el estilo; seguir el patrón reduce el riesgo de divergencia.

**Alternativas descartadas**:
- *Modelos declarativos puros de SQLAlchemy*: rompe la convención del proyecto (SQLModel) y complica el
  uso posterior en schemas FastAPI.
- *Anotaciones con `Field(default=..., primary_key=True)` sin `sa_column`*: no permite expresar
  `BigInteger`/`Identity()`/`ondelete` con la precisión que la KB exige.

### D-02 — Índices únicos parciales con `postgresql_where`

**Decisión**: los dos índices parciales se declaran como `Index(..., postgresql_where=text("..."))` dentro
de `__table_args__`, siguiendo la convención de SQLAlchemy para PostgreSQL:

```python
Index(
    "uq_asignacion_rol_abierta",
    "usuario_id", "rol",
    unique=True,
    postgresql_where=text("revocada_en IS NULL"),
)
Index(
    "uq_libro_isbn_vigente",
    "isbn",
    unique=True,
    postgresql_where=text("borrado_en IS NULL"),
)
```

**Por qué**:
- Es la única forma de que Alembic autogenere un índice parcial con `postgresql_where` en `C-04`; sin
  `postgresql_where` se generaría un `UNIQUE` común.
- Mantiene el índice en el metadata de SQLModel, que es lo que Alembic compara.

**Alternativas descartadas**:
- *`UniqueConstraint(..., postgresql_where=...)`*: funciona, pero la KB y el checklist hablan de «índice
  único parcial»; usar `Index(unique=True, postgresql_where=...)` es la representación canónica y la que
  Alembic emite como `CREATE UNIQUE INDEX ... WHERE`.
- *Declararlo sólo en la migración*: deja el modelo sin el índice en metadata; `alembic check` (CV-10)
  reportaría diferencias y rompería `C-04`.

### D-03 — `Libro`: reemplazar `UniqueConstraint("isbn")` por el índice parcial

**Decisión**: se elimina `UniqueConstraint("isbn", name="uq_libro_isbn")` de `__table_args__` y se agrega
el índice parcial `uq_libro_isbn_vigente`. Se conservan los dos `CheckConstraint`. Se agrega la columna
`borrado_en: Optional[datetime]` con `DateTime(timezone=True)` (timestamptz) y default `None`.

**Por qué**:
- La KB §4 «libro» exige que el ISBN sea único sólo entre los vigentes (RN-01 + RN-13); con un
  `UNIQUE` común no se podría reusar el ISBN de un libro dado de baja.
- `DateTime(timezone=True)` en SQLAlchemy produce `timestamptz` en PostgreSQL, cumpliendo la regla dura 7.

**Alternativas descartadas**:
- *Mantener ambos (UNIQUE común + parcial)*: el `UNIQUE` común bloquearía el reuso del ISBN, violando
  RN-13/C-13.
- *`borrado_en` como `DateTime` sin zona*: viola la regla dura 7 (fechas nuevas siempre con zona).

### D-04 — `Usuario` no tiene columna `rol` y `cliente.usuario_id` es nulo + UNIQUE

**Decisión**: `Usuario` se define con las seis columnas exactas y **ninguna** `rol`. `Cliente` agrega
`usuario_id: Optional[int]` con `sa_column=Column("usuario_id", BigInteger, ForeignKey("usuario.id",
ondelete="NO ACTION"), nullable=True, unique=True, index=True)`. La navegación se declara en los dos
extremos:

```python
# en Cliente
usuario: Optional["Usuario"] = Relationship(back_populates="cliente")
# en Usuario
cliente: Optional["Cliente"] = Relationship(back_populates="usuario")
```

**Por qué**:
- «LOS ROLES VIVEN EN SU PROPIA TABLA» (consigna p. 6): una columna `rol` rompería RN-03/RN-04/RN-05.
- `usuario_id` nulo permite clientes de mostrador sin acceso web; `UNIQUE` con nulos admite múltiples
  `NULL` en PostgreSQL (exactamente lo que se quiere); `ondelete="NO ACTION"` porque borrar un usuario
  ligado a una ficha de cliente no está en el alcance y conviene que la base lo impida.
- `Optional[...]` en el tipo Python refleja la cardinalidad 0..1 y hace que `Cliente.usuario` devuelva
  un objeto (no una lista), como exige el Ejercicio 2 y la KB §4.

**Alternativas descartadas**:
- *`ondelete="CASCADE"`*: borraría la ficha de cliente al borrar el usuario, rompiendo el historial de
  ventas; no está pedido.
- *`List["Usuario"]`/`List["Cliente"]`*: viola «Cliente.usuario devuelve un objeto» y rompe el Ejercicio 2.

### D-05 — Navegación cruzada con `TYPE_CHECKING` y sin precarga

**Decisión**: las relaciones entre módulos (`Usuario.cliente`, `Cliente.usuario`, `Libro.movimientos`,
`MovimientoStock.libro/venta/usuario`) se declaran con `Relationship(back_populates=...)` y los imports
de los modelos remotos se hacen bajo `if TYPE_CHECKING:`, como ya hace `libros/models.py` con
`Editorial`/`Genero`/`RenglonVenta`. No se agrega `sa_relationship_kwargs={"lazy": ...}` ni
`selectinload` (eso es `repository.py`, CV-03).

**Por qué**:
- Evita imports circulares (`usuarios` ↔ `clientes` ↔ `ventas`).
- La precarga la decide el repositorio que la necesita (regla dura 4), no el modelo.

**Alternativas descartadas**:
- *Importar los modelos remotos al tope del módulo*: genera importación circular al arrancar.
- *Declarar `lazy="selectin"` en la relación*: viola la regla dura 4 (precarga fuera de `repository.py`).

### D-06 — `MovimientoStock`: FKs con índice y `venta_id` nulo

**Decisión**: `MovimientoStock` se define con las siete columnas de la KB §4, cada FK con `index=True`,
`venta_id` `nullable=True`, `cantidad` con `CheckConstraint("cantidad <> 0", name="ck_movimiento_stock_cantidad_no_cero")`,
y `cuando` como `DateTime(timezone=True)` con default `datetime.now(timezone.utc)` (convención, como en
`SoftDeleteRepository.soft_delete`). `motivo` es `varchar` NOT NULL.

**Por qué**:
- La KB §4 lista exactamente esas siete columnas e índices; `C-04` autogenera a partir de ellas.
- `cantidad <> 0` es la única restricción de dominio pedida para `movimiento_stock` (RN-12).

**Alternativas descartadas**:
- *`cantidad` con CHECK adicional (`> 0` o `< 0`)*: no pedido; el signo codifica entrada/salida y el
  CHECK `<> 0` ya rechaza el cero.
- *`motivo` como enum*: no pedido; la KB lo deja como `varchar` (vocabulario cosmético, AB-08).

### D-07 — `AsignacionRol`: FK `otorgada_por` nullable con índice

**Decisión**: `otorgada_por` se define como `Optional[int]` con `ForeignKey("usuario.id", ondelete="NO ACTION")`,
`nullable=True`, `index=True`. El CHECK de `rol` se declara en `__table_args__` como
`CheckConstraint("rol IN ('ADMIN','VENDEDOR','CLIENTE')", name="ck_asignacion_rol_rol")`.

**Por qué**:
- AB-07 queda resuelto como FK (decisión de la KB §4/figura 1: `otorgada_por` es FK a `usuario`);
  además permite auditar quién otorgó el rol, que es lo que RN-16 necesita.
- `nullable=True` porque el seed puede tener asignaciones otorgadas por `SISTEMA` (sin usuario) — aunque
  en el modelo el seed usa un usuario real o `NULL`; la KB lo permite.

**Alternativas descartadas**:
- *`otorgada_por` como texto libre*: no permite la FK ni el índice que la KB exige (índice propio).

### D-08 — `IntentoAcceso` y `EventoSeguridad`: sin relaciones, `actor` como Text

**Decisión**: ambos modelos se definen sin `Relationship` (la KB §4 dice que no se relacionan con ninguna
tabla). `EventoSeguridad.actor` usa `Column("actor", Text, nullable=False)` (importando `Text` de
`sqlalchemy`). `IntetoAcceso` no tiene FKs ni CHECKs.

**Por qué**:
- La KB §4 es explícita: «`intento_acceso` y `evento_seguridad` no se relacionan con ninguna otra
  tabla»; `actor` es texto para que el seed escriba `SISTEMA` sin usuario ficticio (RN-16).
- `Text` (no `String`) es lo que la KB exige para `actor`.

**Alternativas descartadas**:
- *`actor` como FK a `usuario`*: imposibilitaría escribir `SISTEMA` y rompería el seed y RN-16.

### D-09 — Módulo `usuarios`: crear sólo `models.py`

**Decisión**: se crea `parcial/app/modules/usuarios/` con únicamente `models.py` y su `__init__.py`. No se
crean `router.py`, `schemas.py`, `service.py` ni `unit_of_work.py` (esos son `C-07`/`C-11`/`C-13`).

**Por qué**:
- `C-01` D-07 prohíbe carpetas de módulo vacías, pero acá la carpeta lleva un archivo real (`models.py`),
  así que es válida.
- Mantener el scope de `C-03` acotado a modelos evita tocar código que todavía no tiene consumidores.

**Alternativas descartadas**:
- *Crear el módulo completo vacío*: viola `C-01` D-07 y agrega código muerto.

## Risks / Trade-offs

- [Alembic no infiere `postgresql_where` bien] → `C-04` lee la migración autogenerada y corrige a mano;
  por eso los índices se declaran con `postgresql_where` explícito en el modelo (D-02), que es lo que
  Alembic compara. Mitigación: no editar migraciones ya aplicadas; migración nueva si hace falta.
- [Importación circular entre `usuarios` y `clientes`] → se mitiga con `TYPE_CHECKING` (D-05). Si un
  consumidor importa los modelos al tope, fallará al arrancar; se documenta en el docstring.
- [SoftDeleteRepository asume `borrado_en`] → ya documentado en `C-02`; sólo `Libro` lo usa. Sin cambio.
- [Columnas heredadas no confirmadas (AB-02/AB-06)] → no se tocan; sólo se agregan las indicadas. Si
  `venta` no tiene `usuario_id`, la FK de `movimiento_stock.usuario_id` sigue siendo válida porque apunta
  a `usuario`, no a `venta`.
- [El índice parcial de ISBN convive con el `UNIQUE` común en bases ya creadas] → en una base nueva
  (upgrade head) no hay conflicto; en una base con el TP aplicado, `C-04` debe dropear el `UNIQUE` común
  explícitamente. Se documenta en la migración.

## Migration Plan

1. Este change sólo modifica modelos Python; no hay migración nueva ni cambio de esquema en `C-03`.
2. `C-04` ejecuta `alembic revision --autogenerate` contra una base con el esquema del TP aplicado,
   lee la migración entera y corrige a mano: `postgresql_where` de los dos índices parciales,
   `borrado_en` como `timestamptz`, índices de las FKs nuevas, drop del `UNIQUE(isbn)` común.
3. Rollback de `C-03` = revertir los archivos de modelo; no hay migración que revertir aún.

## Open Questions

Ninguna que cambie las specs, el enfoque o las tasks. AB-02 y AB-06 son preguntas del TP heredado que
no bloquean este change (no se tocan `venta` ni `renglon_venta`). AB-07 queda resuelto como FK (D-07).