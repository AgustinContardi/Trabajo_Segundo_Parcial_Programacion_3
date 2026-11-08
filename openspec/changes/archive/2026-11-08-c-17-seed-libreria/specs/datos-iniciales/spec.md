# Spec Delta — datos-iniciales

## Purpose

Define los datos de arranque que el proyecto carga en PostgreSQL para que la aplicación, los casos de
prueba y la corrección partan del mismo estado: usuarios con sus roles, catálogo, clientes, la venta 1,
sus movimientos de stock y el registro de seguridad del sistema.

## ADDED Requirements

### Requirement: El seed carga los cinco usuarios del PDF con sus roles vigentes

El seed SHALL dejar cinco usuarios —`admin@example.com`, `admin2@example.com`, `vendedor@example.com`,
`ana@example.com` y `nuevo@example.com`— con `password_hash` bcrypt válido, `activo = true` y sus filas de
`asignacion_rol` abiertas (`revocada_en` y `vence_en` nulos): `admin` y `admin2` con `ADMIN`, `vendedor` y
`nuevo` con `VENDEDOR`, y `ana` con `CLIENTE` (IN-07, consigna p. 19-20).

#### Scenario: Roles de los cinco usuarios

- **WHEN** se ejecuta el seed sobre un esquema migrado y se consulta
  `SELECT u.email, a.rol FROM usuario u JOIN asignacion_rol a ON a.usuario_id = u.id`
- **THEN** aparecen exactamente cinco usuarios, con `admin` y `admin2` en `ADMIN`, `vendedor` y `nuevo` en
  `VENDEDOR`, y `ana` en `CLIENTE`, cada uno con una sola asignación abierta

#### Scenario: Usuario con cambio de contraseña pendiente

- **WHEN** se lee la fila de `nuevo@example.com`
- **THEN** `debe_cambiar_password` es verdadero, de modo que el caso C-09 del bloqueo del grupo protegido
  tenga con qué empezar

#### Scenario: Login con las credenciales del seed

- **WHEN** se envía `POST /auth/login` con el correo de cualquiera de los cinco usuarios y la contraseña de
  mentira definida en `seed.py`
- **THEN** la respuesta es `200` con cookie `access_token` y los roles vigentes leídos de la base

### Requirement: El seed carga el catálogo del TP con los stocks del PDF

El seed SHALL dejar tres editoriales, tres géneros, seis autores y cinco libros vigentes (`borrado_en`
nulo): Rayuela, Antología de la literatura fantástica, Ficciones, Respiración artificial y Bestiario, con
`stock` final **10, 5, 8, 3 y 1** respectivamente y con los precios del PDF donde el PDF los fija
(`25000.00`, `30000.00`, `22000.00`) más los heredados del TP para los otros dos (IN-07, `docs/CHECKLIST_ENTREGA.md` §8).

#### Scenario: Stocks finales del catálogo

- **WHEN** se ejecuta `SELECT titulo, stock FROM libro ORDER BY id` tras el seed
- **THEN** los cinco libros aparecen con stock `10`, `5`, `8`, `3` y `1`, en ese orden, y ninguno tiene
  `borrado_en` distinto de nulo

#### Scenario: Precios del PDF

- **WHEN** se consulta `precio` de Rayuela, Antología de la literatura fantástica y Ficciones
- **THEN** los valores son `25000.00`, `30000.00` y `22000.00`, los que la consigna usa en el listado y en
  la venta 1

#### Scenario: Autorías cargadas

- **WHEN** se consulta `libro_autor` para los cinco libros
- **THEN** cada libro tiene al menos una autoría con un `rol` permitido y `orden` mayor o igual a uno

### Requirement: El seed carga los tres clientes con su relación de acceso

El seed SHALL dejar a Lucía Fernández (con `perfil_cliente`, sin `usuario_id`), Tomás Ríos (sin `usuario_id`
y sin perfil) y Ana Paz (con `usuario_id` apuntando a `ana@example.com`), y el `usuario_id` SHALL ser nulo en
las dos primeras fichas (consigna p. 20, `RN-02`).

#### Scenario: Fichas de cliente

- **WHEN** se ejecuta `SELECT nombre, usuario_id FROM cliente ORDER BY id`
- **THEN** aparecen las tres fichas, con `usuario_id` nulo en Lucía y en Tomás, y con el id del usuario
  `ana@example.com` en Ana Paz

#### Scenario: Perfil sólo de Lucía

- **WHEN** se consulta `perfil_cliente` tras el seed
- **THEN** existe exactamente un perfil y pertenece a la ficha de Lucía Fernández

### Requirement: El seed carga la venta 1 con sus renglones y sus movimientos de salida

El seed SHALL dejar la venta con `id = 1`, de Lucía, con `total = 69000.00` y dos renglones —1 Rayuela y 2
Ficciones— con el `precio_unitario` copiado del libro, y SHALL dejar dos movimientos de stock negativos
(`−1` y `−2`) con `motivo = 'Venta'`, `venta_id = 1` y `usuario_id` del usuario `vendedor@example.com`
(consigna p. 20, `RN-09`, `RN-11`).

#### Scenario: Total y renglones de la venta 1

- **WHEN** se ejecuta `SELECT total FROM venta WHERE id = 1` y se cuentan sus renglones
- **THEN** el total es `69000.00` y hay dos renglones con `precio_unitario` `25000.00` y `22000.00` y
  cantidades `1` y `2`

#### Scenario: Movimientos de la venta

- **WHEN** se consultan los movimientos asociados a `venta_id = 1`
- **THEN** hay uno por renglón, con cantidades `−1` y `−2`, `motivo = 'Venta'` y el `usuario_id` de
  `vendedor@example.com`

### Requirement: Todo el stock nace de movimientos «Stock inicial»

El seed SHALL cargar el stock únicamente a través del punto único de escritura de stock, de modo que cada
uno de los cinco libros —Rayuela, Antología de la literatura fantástica, Ficciones, Respiración artificial
y Bestiario— tenga un movimiento `'Stock inicial'` con cantidad `+11`, `+5`, `+10`, `+3` y `+1`
respectivamente (KB §4: «los cinco libros; Rayuela y Ficciones se cargan con 11 y 10»), y `libro.stock`
final resulte de la venta 1 descontando `−1` y `−2` (`RN-11`, `RN-12`, `CV-11`).

#### Scenario: Movimientos de stock inicial

- **WHEN** se consultan los movimientos con `motivo = 'Stock inicial'` agrupados por libro
- **THEN** hay exactamente uno por libro, con las cantidades `11`, `5`, `10`, `3` y `1` en el orden de
  `libro.id`, y con un `usuario_id` no nulo

#### Scenario: El seed no escribe stock directo

- **WHEN** se revisa el alta de cada libro del seed
- **THEN** el libro se crea con `stock = 0` y el valor final proviene de los movimientos, nunca de una
  asignación directa a `libro.stock`

### Requirement: Tras el seed el invariante de stock se cumple en los cinco libros

Después de ejecutar el seed, la consulta
`SELECT l.id FROM libro l LEFT JOIN movimiento_stock m ON m.libro_id = l.id GROUP BY l.id, l.stock HAVING l.stock <> COALESCE(SUM(m.cantidad), 0)`
SHALL devolver **0 filas** (`RN-11`, `docs/CHECKLIST_ENTREGA.md` §4).

#### Scenario: Invariante global

- **WHEN** se corre la query del invariante inmediatamente después de `python seed.py`
- **THEN** devuelve cero filas, incluidas las de Rayuela (`+11 −1 = 10`) y Ficciones (`+10 −2 = 8`)

#### Scenario: El propio seed verifica el invariante

- **WHEN** la verificación final del seed encuentra una fila que no cuadra
- **THEN** el script informa el libro y las cantidades en un mensaje propio y termina con código distinto
  de cero, sin dejar el proceso como si hubiera terminado bien

### Requirement: El seed deja el registro de seguridad del sistema

El seed SHALL escribir exactamente una línea de `evento_seguridad` con `actor = 'SISTEMA'` y la acción
«Carga de los datos iniciales» (consigna p. 20, `RN-16`).

#### Scenario: Línea de auditoría

- **WHEN** se ejecuta `SELECT actor, accion FROM evento_seguridad` tras el seed
- **THEN** aparece una línea con `actor = 'SISTEMA'` y `accion = 'Carga de los datos iniciales'`

### Requirement: El seed es idempotente y deja identificadores estables

El seed SHALL vaciar las tablas de dominio antes de cargar y SHALL reiniciar las identidades, de modo que
dos ejecuciones consecutivas produzcan el mismo estado y los mismos identificadores: venta `1`, libros `1`
a `5`, editoriales, géneros, autores y clientes en orden estable, y usuarios legibles por correo
(`CV-11`).

#### Scenario: Dos corridas consecutivas

- **WHEN** se ejecuta `python seed.py` dos veces seguidas
- **THEN** los conteos de usuarios, roles, editoriales, géneros, autores, libros, clientes, ventas,
  renglones, movimientos y eventos son los mismos, y `venta.id = 1` vuelve a ser `1`

#### Scenario: Vaciar no usa DELETE sobre movimientos

- **WHEN** el seed vacía el estado anterior existiendo movimientos de stock cargados
- **THEN** la limpieza termina sin error porque usa `TRUNCATE` —el disparador de `RN-12` rechaza
  `UPDATE` y `DELETE`— y no modifica `alembic_version`

### Requirement: El seed corre después de las migraciones y falla con un mensaje propio

El seed SHALL ejecutarse con éxito únicamente sobre un esquema creado por `alembic upgrade head`; SHALL NOT
crear ni modificar tablas, y si el esquema o la configuración faltan SHALL terminar con un mensaje propio en
español y código distinto de cero, sin trazas de PostgreSQL (consigna p. 8 y 19, `RN-15`, `CV-14`).

#### Scenario: Esquema migrado

- **WHEN** se corre `alembic upgrade head` y después `python seed.py` en una base vacía
- **THEN** el seed termina con código `0` y deja los datos completos

#### Scenario: Esquema sin migrar

- **WHEN** se corre `python seed.py` contra una base sin las tablas del parcial
- **THEN** el script informa que falta aplicar las migraciones y termina con código distinto de cero

#### Scenario: Sin creación implícita del esquema

- **WHEN** se busca `create_all` en el repositorio
- **THEN** no aparece ninguna ocurrencia, tampoco en el seed

### Requirement: Las credenciales del seed son de mentira y viven sólo en el seed

Las contraseñas del seed SHALL ser valores ficticios definidos únicamente en `parcial/seed.py`, SHALL
cumplir el límite de 72 bytes de bcrypt y SHALL hashearse con la función compartida de seguridad fuera del
bucle de eventos; ninguna de ellas SHALL aparecer en `env.example`, en la configuración ni en la
documentación como credencial real (`RN-15`, `CV-09`).

#### Scenario: Contraseña usable por el login

- **WHEN** se hace login con la contraseña ficticia del seed para `admin@example.com`
- **THEN** la respuesta es `200`, porque el hash se calculó con bcrypt y con el costo de `Settings`

#### Scenario: Sin secretos versionados

- **WHEN** se revisa `parcial/env.example` y la configuración de la aplicación
- **THEN** no aparece ninguna de las contraseñas del seed como valor de una variable de entorno
