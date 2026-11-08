# casos-de-prueba-c Specification

## Purpose
Define la evidencia ejecutable que demuestra los casos `C-01…C-16` de la consigna y el aviso de
`BackgroundTasks` sobre la API real, de modo que la corrección pueda reproducir cada caso y comparar el
resultado observado con el esperado.

## Requirements

### Requirement: La suite cubre C-01…C-16 en archivos `.http` por módulo

`parcial/test/` SHALL contener archivos `.http` que, en conjunto, demuestren los dieciséis casos de la
consigna, organizados por módulo, y cada bloque SHALL declarar en un comentario el status esperado, el cuerpo
o fragmento esperado y las `RN-xx` que lo justifican (consigna p. 21-22, checklist §10).

#### Scenario: Inventario de archivos

- **WHEN** se lista `parcial/test/*.http`
- **THEN** existen archivos para registro, autenticación, roles/usuarios, libros/catálogo y ventas, y entre
  todos aparecen los identificadores `C-01` a `C-16` al menos una vez

#### Scenario: Cada caso declara su resultado esperado

- **WHEN** se abre el bloque de un caso `C-NN`
- **THEN** el comentario inmediatamente anterior indica el status esperado (por ejemplo `201`, `409`, `422`,
  `429`) y, cuando aplica, la forma del cuerpo y las cabeceras, más la referencia `RN-xx`

#### Scenario: Trazabilidad con la checklist

- **WHEN** se compara la lista de casos con `docs/CHECKLIST_ENTREGA.md` §10
- **THEN** cada ítem `C-NN` de la checklist se puede ubicar en un bloque concreto de un archivo de
  `parcial/test/`, sin casos faltantes ni duplicados con resultados contradictorios

### Requirement: Los casos parten del estado del seed canónico

Cada archivo `.http` SHALL asumir que se ejecutó `alembic upgrade head` y `python seed.py` inmediatamente
antes, y SHALL usar los identificadores y credenciales del seed en lugar de sembrar usuarios, clientes o
libros ad hoc (C-17, checklist §8).

#### Scenario: Puesta en marcha indicada en el encabezado

- **WHEN** se lee la cabecera de cualquier archivo
- **THEN** indica que la API debe estar en `http://127.0.0.1:8000`, con PostgreSQL real y el seed recién
  ejecutado, y enumera las credenciales ficticias que usa

#### Scenario: Ids estables del seed

- **WHEN** un caso necesita la venta 1, los libros 1…5 o un usuario por correo
- **THEN** usa los valores que el seed garantiza con `RESTART IDENTITY` (venta `1`, libros `1…5`, correos
  `admin@`, `admin2@`, `vendedor@`, `ana@` y `nuevo@example.com`) y no un id inventado

#### Scenario: Sin preparación SQL obligatoria fuera del seed

- **WHEN** se corre el archivo después del seed
- **THEN** no hace falta ejecutar bloques `INSERT` manuales para que los casos funcionen; las consultas SQL
  del archivo son sólo de verificación o de la mutación que el propio caso demuestra

### Requirement: C-07 se demuestra con dos sesiones simultáneas en un archivo

El archivo de roles SHALL iniciar dos sesiones en el mismo documento —cada login con `# @name`— y SHALL
enviar las peticiones de cada sesión con `# @no-cookie-jar` y la cabecera
`Cookie: {{login_<sesión>.response.headers.Set-Cookie}}`, de modo que una sesión pueda revocar el rol de la
otra sin perder su propia cookie (consigna p. 23, checklist §10). El bloque de vencimiento (C-07.11) SHALL
incluir en su encabezado los pasos exactos para regenerar el `403` con una fecha relativa (asignar
`vence_en` a `now() + 1 minuto`, esperar el vencimiento y repetir con la misma cookie), porque una fecha
fija en el futuro lejano no demuestra el caso.

#### Scenario: Dos logins nombrados

- **WHEN** se lee el archivo de roles
- **THEN** hay un login de administrador y uno de vendedor, cada uno con su `# @name` y su cookie guardada en
  una variable distinta

#### Scenario: Petición con cookie explícita

- **WHEN** una petición usa la sesión del vendedor después de que el administrador cambió sus roles
- **THEN** lleva `# @no-cookie-jar` y `Cookie: {{login_vendedor.response.headers.Set-Cookie}}`, y no depende
  del cookie jar global de REST Client

#### Scenario: Revocación y vencimiento con la cookie ya emitida

- **WHEN** el administrador revoca `VENDEDOR` y el vendedor repite con su cookie original
- **THEN** la respuesta es `403`, `/auth/yo` muestra la diferencia entre roles de la base y roles del token, y
  la fila revocada sigue existiendo con `revocada_en` no nulo

#### Scenario: Vencimiento inválido por contrato

- **WHEN** se asigna un rol con `vence_en` sin zona horaria o en el pasado
- **THEN** la respuesta es `422`, no `409` ni `500`

#### Scenario: Vencimiento real reproducible

- **WHEN** se sigue el procedimiento del encabezado de C-07.11 con una fecha relativa
- **THEN** la misma cookie responde `200` antes del vencimiento y `403` después, sin editar valores a mano
  fuera de los pasos indicados

### Requirement: C-14 se demuestra con SQL de sólo agregado

`parcial/test/solo_agregado.sql` SHALL contener un `UPDATE` y un `DELETE` sobre `movimiento_stock` que el
disparador de `RN-12` rechaza, ejecutables con `psql -f` sobre la base del seed, y la corrida SHALL registrar
los dos errores del motor.

#### Scenario: UPDATE rechazado

- **WHEN** se ejecuta `psql -f parcial/test/solo_agregado.sql`
- **THEN** la sentencia `UPDATE movimiento_stock …` falla con el error del disparador y no modifica ninguna fila

#### Scenario: DELETE rechazado

- **WHEN** el mismo archivo ejecuta `DELETE FROM movimiento_stock …`
- **THEN** la sentencia falla con el error del disparador y la tabla conserva sus filas

#### Scenario: Captura de la corrida

- **WHEN** se evidencia C-14
- **THEN** existe la salida de `psql` con los dos errores, que C-19 incorpora a `parcial/evidencia/`

### Requirement: C-15 demuestra que el detalle no varía con la cantidad de renglones

La evidencia de C-15 SHALL registrar el detalle de una venta de 2 renglones y el de una de 4 renglones con
`SQL_ECHO=true`, y SHALL mostrar la misma cantidad de sentencias `SELECT` en los dos casos (consigna p. 13 y
22, `CV-02`).

#### Scenario: Venta de 2 renglones

- **WHEN** se pide `GET /ventas/{id}` de la venta 1 del seed con `SQL_ECHO=true`
- **THEN** la consola muestra las consultas del detalle y se pueden contar las líneas `SELECT`

#### Scenario: Venta de 4 renglones

- **WHEN** se registra una venta con 4 libros distintos y se pide su detalle con `SQL_ECHO=true`
- **THEN** la cantidad de líneas `SELECT` es la misma que en el caso de 2 renglones

#### Scenario: Captura para C-19

- **WHEN** se cierra C-18
- **THEN** existe un archivo de consola con los dos conteos, que C-19 archiva como evidencia oficial

### Requirement: El aviso del comprobante se demuestra después de la respuesta

La evidencia de C-10 SHALL usar `uvicorn main:app` sin configuración adicional de logging y SHALL mostrar que
la línea del comprobante aparece en la consola después de la línea de la respuesta HTTP (consigna p. 13 y 20,
checklist §10).

#### Scenario: Venta registrada con el servidor normal

- **WHEN** se registra una venta válida contra el servidor arrancado con `uvicorn main:app`
- **THEN** la respuesta `201` queda registrada antes que el mensaje del comprobante

#### Scenario: El aviso no bloquea la respuesta

- **WHEN** se mide el orden de las líneas de la consola
- **THEN** el mensaje del comprobante no aparece antes de la respuesta ni impide que la venta se confirme

### Requirement: La evidencia distingue archivo escrito de corrida real

El change SHALL dejar constancia separada de qué archivos se escribieron con su resultado esperado y qué
casos se ejecutaron realmente con qué salida; SHALL NOT declarar una ejecución que no se hizo (checklist §10,
consigna p. 21-22).

#### Scenario: Archivo sin corrida

- **WHEN** un `.http` se entrega pero su ejecución con REST Client no se pudo realizar en el entorno del
  agente
- **THEN** el registro dice «archivo escrito, ejecución pendiente del usuario» y no presenta una salida
  inventada

#### Scenario: Corrida equivalente documentada

- **WHEN** un caso se ejecuta por un medio equivalente (por ejemplo `httpx` contra el servidor real)
- **THEN** el registro lo dice explícitamente, guarda el status y el cuerpo observados y aclara que el `.http`
  sigue siendo el formato de revisión manual

#### Scenario: Capturas producidas en este change

- **WHEN** se revisa la evidencia de C-14 y C-15
- **THEN** sus capturas existen y el change deja escrito que C-19 las consolida en `parcial/evidencia/`

### Requirement: C-06 demuestra el path standalone de mis ventas

`parcial/test/roles.http` SHALL incluir un bloque C-06 que solicite `GET /mis-ventas` (sin prefijo
`/ventas`) con la cookie de un cliente, declare el status esperado y el envoltorio, y `EVIDENCIA.md` SHALL
registrar su corrida. El archivo MUST NOT usar `/ventas/mis-ventas` como path canónico.

#### Scenario: Bloque de mis ventas

- **WHEN** se busca `GET /mis-ventas` en `parcial/test/roles.http`
- **THEN** existe al menos un bloque C-06 con `# Esperado:` y la cookie de un cliente con ficha

#### Scenario: Path incorrecto ausente

- **WHEN** se busca `/ventas/mis-ventas` en `parcial/test/`
- **THEN** no aparece como ruta canónica ni en la evidencia
