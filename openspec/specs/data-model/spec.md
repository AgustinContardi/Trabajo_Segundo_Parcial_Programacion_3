# data-model Specification

## Purpose
Defines the parcial's domain data model: the access tables (usuario, asignacion_rol, intento_acceso,
evento_seguridad), movimiento_stock, soft-delete plus partial ISBN uniqueness on libro, the optional
cliente.usuario_id link, entity-to-module placement, and the type conventions that every later
migration and module relies on.

## Requirements

### Requirement: usuario table shape

The system SHALL define a `usuario` table with exactly six columns: `id` (bigint identity PK), `email`
(varchar, NOT NULL, UNIQUE), `nombre` (varchar, NOT NULL), `password_hash` (varchar, NOT NULL),
`activo` (boolean, NOT NULL, default true), and `debe_cambiar_password` (boolean, NOT NULL).

#### Scenario: six columns present

- **WHEN** the `usuario` table definition is inspected
- **THEN** it contains exactly the six columns `id`, `email`, `nombre`, `password_hash`, `activo`, and
  `debe_cambiar_password`

#### Scenario: email unique

- **WHEN** two rows with the same `email` are inserted
- **THEN** the second insert fails with a uniqueness violation

### Requirement: usuario has no rol column

The system SHALL NOT define a `rol` column on `usuario`; roles SHALL live exclusively in
`asignacion_rol`.

#### Scenario: no rol column

- **WHEN** the `usuario` table definition is inspected
- **THEN** no column named `rol` exists

### Requirement: asignacion_rol table shape

The system SHALL define an `asignacion_rol` table with seven columns: `id` (bigint identity PK),
`usuario_id` (bigint NOT NULL, FK to usuario.id, indexed), `rol` (varchar NOT NULL, CHECK IN
('ADMIN','VENDEDOR','CLIENTE')), `desde` (timestamptz NOT NULL, default now()), `vence_en`
(timestamptz NULL), `revocada_en` (timestamptz NULL), and `otorgada_por` (bigint NULL, FK to
usuario.id, indexed).

#### Scenario: seven columns present

- **WHEN** the `asignacion_rol` table definition is inspected
- **THEN** it contains exactly the seven columns listed

#### Scenario: rol check

- **WHEN** a row with `rol` outside ('ADMIN','VENDEDOR','CLIENTE') is inserted
- **THEN** the insert fails with a CHECK violation

#### Scenario: partial unique index

- **WHEN** two rows with the same (usuario_id, rol) and `revocada_en IS NULL` are inserted
- **THEN** the second insert fails with a uniqueness violation

#### Scenario: revoked rows coexist

- **WHEN** two rows share (usuario_id, rol) but at least one has `revocada_en` set
- **THEN** both rows coexist without violation

### Requirement: intento_acceso table shape

The system SHALL define an `intento_acceso` table with five columns: `id` (bigint identity PK),
`cuando` (timestamptz NOT NULL, default now()), `email` (varchar NOT NULL), `ip` (varchar NOT NULL),
and `exito` (boolean NOT NULL). It SHALL have an index on (email, ip, cuando). It SHALL have no
foreign keys and no extra CHECK constraints.

#### Scenario: five columns present

- **WHEN** the `intento_acceso` table definition is inspected
- **THEN** it contains exactly the five columns listed

#### Scenario: composite index present

- **WHEN** the indexes of `intento_acceso` are inspected
- **THEN** an index on (email, ip, cuando) exists

### Requirement: evento_seguridad table shape

The system SHALL define an `evento_seguridad` table with four columns: `id` (bigint identity PK),
`cuando` (timestamptz NOT NULL, default now()), `actor` (text NOT NULL), and `accion` (varchar NOT
NULL). The `actor` column SHALL be text (not a foreign key). The table SHALL have no foreign keys
and no CHECK constraints.

#### Scenario: four columns present

- **WHEN** the `evento_seguridad` table definition is inspected
- **THEN** it contains exactly the four columns listed

#### Scenario: actor is text

- **WHEN** the type of `evento_seguridad.actor` is inspected
- **THEN** it is `text`

### Requirement: movimiento_stock table shape

The system SHALL define a `movimiento_stock` table with seven columns: `id` (bigint identity PK),
`libro_id` (bigint NOT NULL, FK to libro.id, indexed), `venta_id` (bigint NULL, FK to venta.id,
indexed), `usuario_id` (bigint NOT NULL, FK to usuario.id, indexed), `cantidad` (integer NOT NULL,
CHECK cantidad <> 0), `motivo` (varchar NOT NULL), and `cuando` (timestamptz NOT NULL, default
now()).

#### Scenario: seven columns present

- **WHEN** the `movimiento_stock` table definition is inspected
- **THEN** it contains exactly the seven columns listed

#### Scenario: venta_id nullable

- **WHEN** a row with `venta_id` NULL is inserted
- **THEN** the insert succeeds

#### Scenario: cantidad non-zero

- **WHEN** a row with `cantidad = 0` is inserted
- **THEN** the insert fails with a CHECK violation

#### Scenario: index on each foreign key

- **WHEN** the indexes of `movimiento_stock` are inspected
- **THEN** indexes exist on `libro_id`, `venta_id`, and `usuario_id`

### Requirement: libro soft delete and partial ISBN

The system SHALL add a nullable `borrado_en` column of type timestamptz to `libro`, default NULL
meaning vigente. The common `UNIQUE(isbn)` constraint SHALL be replaced by a partial unique index on
(isbn) WHERE borrado_en IS NULL. The existing CHECK (precio > 0) and CHECK (stock >= 0) SHALL
remain. LibroAutor SHALL remain unchanged.

#### Scenario: borrado_en present and nullable

- **WHEN** the `libro` table definition is inspected
- **THEN** it has a nullable `borrado_en` column of type timestamptz

#### Scenario: partial unique index on isbn

- **WHEN** the indexes of `libro` are inspected
- **THEN** a unique index on (isbn) WHERE borrado_en IS NULL exists and the common UNIQUE(isbn) is
  absent

#### Scenario: reuse isbn after soft delete

- **WHEN** a libro is soft-deleted (borrado_en set) and a new libro with the same isbn is inserted
- **THEN** the insert succeeds

#### Scenario: duplicate vigente isbn rejected

- **WHEN** two vigente libros share the same isbn
- **THEN** the second insert fails with a uniqueness violation

#### Scenario: checks retained

- **WHEN** the constraints of `libro` are inspected
- **THEN** CHECK (precio > 0) and CHECK (stock >= 0) are present

### Requirement: cliente optional usuario link

The system SHALL add a nullable `usuario_id` column to `cliente` of type bigint, UNIQUE, with a
foreign key to `usuario.id`. The navigation SHALL be declared on both ends: `Cliente.usuario` returns
a single object (not a list) and `Usuario.cliente` returns a single object. PerfilCliente SHALL
remain a 1-1 relationship with `cliente_id` UNIQUE and NOT NULL.

#### Scenario: usuario_id nullable and unique

- **WHEN** two cliente rows with NULL usuario_id are inserted
- **THEN** both succeed (multiple NULL allowed)

#### Scenario: one usuario per cliente

- **WHEN** two cliente rows reference the same usuario_id
- **THEN** the second insert fails with a uniqueness violation

#### Scenario: navigation is single object

- **WHEN** the relationship declarations are inspected
- **THEN** `Cliente.usuario` is typed as a single object (not a list) and `Usuario.cliente` is
  typed as a single object

#### Scenario: perfil_cliente one-to-one intact

- **WHEN** the `perfil_cliente` table definition is inspected
- **THEN** `cliente_id` is NOT NULL, UNIQUE, and a FK to `cliente.id`

### Requirement: entity to module placement

The system SHALL place `Usuario`, `AsignacionRol`, `IntentoAcceso`, and `EventoSeguridad` in
`app/modules/usuarios/models.py`; `MovimientoStock` and `LibroAutor` in
`app/modules/libros/models.py`; `PerfilCliente` in `app/modules/clientes/models.py`; and
`RenglonVenta` in `app/modules/ventas/models.py`. No entity SHALL be moved out of its assigned
module.

#### Scenario: placement verified

- **WHEN** the model files are inspected
- **THEN** each entity is defined in its assigned module file

### Requirement: type conventions

All new date columns SHALL be of type timestamptz. All money columns SHALL be NUMERIC in the
database and Decimal in Python, never float. Every new foreign key column SHALL have its own index.

#### Scenario: new dates with zone

- **WHEN** the columns `asignacion_rol.desde`, `vence_en`, `revocada_en`, `intento_acceso.cuando`,
  `evento_seguridad.cuando`, `movimiento_stock.cuando`, and `libro.borrado_en` are inspected
- **THEN** all are timestamptz

#### Scenario: money as numeric

- **WHEN** the money columns are inspected
- **THEN** they are NUMERIC in the DB and Decimal in Python, never float

#### Scenario: fk indexes

- **WHEN** each new foreign key column is inspected
- **THEN** it has an index
