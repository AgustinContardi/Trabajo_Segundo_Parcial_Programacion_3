# Proposal — C-03 modelos-acceso-stock

## Why

`C-01` (fundación) ya dejó el esqueleto `parcial/` con el TP cap. 1-4 adoptado (catálogo, clientes,
ventas, migraciones `0001`/`0002`) y `C-02` dejó la capa compartida de repositorios, Unit of Work y
paginación. Lo que falta —y es el **10 % de la nota en «Modelos, relaciones y migraciones»**— es el
modelo de datos propio del parcial: las cuatro tablas de acceso (`usuario`, `asignacion_rol`,
`intento_acceso`, `evento_seguridad`), la nueva `movimiento_stock`, el borrado lógico + ISBN parcial en
`libro` y el enlace opcional `cliente.usuario_id`. Hoy no existe ninguna de esas definiciones en
`parcial/`, y todo lo demás (auth `C-11`, repositorios por módulo `C-06`…`C-10`, stock `C-08`/`C-15`,
migraciones `C-04`) las referencia por nombre exacto. Un nombre de columna cambiado aquí invalida los
casos de prueba y la corrección, por eso el change es de **governance ALTO** y se hace antes que
cualquier consumidor.

## What Changes

- `parcial/app/modules/usuarios/models.py` (**nuevo**): `Usuario` (6 columnas, `email` UNIQUE, **sin**
  columna `rol`), `AsignacionRol` (7 columnas, `CHECK (rol IN ('ADMIN','VENDEDOR','CLIENTE'))`, índice
  único parcial `(usuario_id, rol) WHERE revocada_en IS NULL` con `postgresql_where`, índices en
  `usuario_id` y `otorgada_por`), `IntentoAcceso` (5 columnas + índice `(email, ip, cuando)`),
  `EventoSeguridad` (4 columnas, `actor` **Text**, sin FK ni CHECK).
- `parcial/app/modules/libros/models.py`: agregar `MovimientoStock` (7 columnas, `venta_id` nulo,
  `CHECK (cantidad <> 0)`, índice en cada FK); agregar `Libro.borrado_en` (`timestamptz`, nulo) y
  **reemplazar** el `UNIQUE(isbn)` por el índice único parcial `(isbn) WHERE borrado_en IS NULL`;
  conservar `CHECK (precio > 0)` y `CHECK (stock >= 0)`; `LibroAutor` sin cambios.
- `parcial/app/modules/clientes/models.py`: agregar `Cliente.usuario_id` (nulo permitido, `UNIQUE`, FK a
  `usuario.id`) y declarar la navegación en **los dos extremos** (`Cliente.usuario` devuelve un objeto,
  no una lista; `Usuario.cliente`); `PerfilCliente` 1—1 intacto.
- Convenciones de tipo respetadas en todo lo nuevo: fechas `timestamptz`, dinero `Numeric`/`Decimal`
  (nunca `float`), cada FK nueva con su índice.
- Asignación obligatoria de entidades a módulos respetada: `AsignacionRol`/`IntentoAcceso`/
  `EventoSeguridad` en `usuarios`; `MovimientoStock` y `LibroAutor` en `libros`; `PerfilCliente` en
  `clientes`; `RenglonVenta` en `ventas` (sin cambios).
- No se tocan migraciones ni routers ni servicios: este change define los modelos; las migraciones
  (`0003`/`0004`) y la adopción quedan para `C-04` y los changes de capas.

## Capabilities

### New Capabilities
- `data-model`: modelo de datos del parcial — tablas de acceso (`usuario`, `asignacion_rol`,
  `intento_acceso`, `evento_seguridad`), `movimiento_stock`, borrado lógico + ISBN parcial en `libro`,
  enlace opcional `cliente.usuario_id` y convenciones de tipo (fechas con zona, dinero `Numeric`,
  índice en cada FK nueva). Es el contrato que consumen `C-04` (migraciones) y los changes de capas.

### Modified Capabilities
Ninguna: las capacidades existentes (`app-foundation`, `core-repositories`, `legacy-baseline`) no
cambian sus requisitos; este change agrega un nuevo contrato de modelo de datos. (Las tablas heredadas
de `legacy-baseline` se **conservan** intactas; sólo se agregan columnas/relaciones compatibles.)

## Impact
- **Código nuevo**: `parcial/app/modules/usuarios/models.py` (módulo nuevo, sólo `models.py`; los demás
  archivos del módulo quedan para `C-07`/`C-11`).
- **Código modificado**: `parcial/app/modules/libros/models.py` (`Libro` + `MovimientoStock` nuevo),
  `parcial/app/modules/clientes/models.py` (`Cliente` + navegación en `Usuario`).
- **API**: ninguna ruta nueva ni modificada; los endpoints existentes siguen funcionando.
- **Dependencias**: sólo lo ya instalado (`SQLModel 0.0.24`, `SQLAlchemy 2.0`, `asyncpg`). No se
  agregan paquetes.
- **Changes aguas abajo**: `C-04` (migraciones `0003`/`0004`) autogenera a partir de estos modelos;
  `C-06`…`C-10`, `C-11`, `C-13`, `C-15` consumen los nombres exactos de columnas y relaciones.
- **Riesgo principal**: un nombre de columna o relación distinto al de la KB invalida tests y migraciones;
  se mitiga fijando los nombres exactos (KB §4, sección «Entidades») y marcando el change como ALTO.