# legacy-baseline Specification

## Purpose
Garantiza que el TP de los capítulos 1-4 se incorpora al parcial como base verificable —sin reescribir su
lógica ni inventar su esquema— y que su copia de despliegue se mantiene separada e intacta.

## Requirements

### Requirement: Adopción del TP sin reescribir su lógica

Al recibir el TP cap. 1-4, el proyecto SHALL incorporarlo a `parcial/` conservando sus rutas, contratos y
comportamiento entregados. Las modificaciones del parcial SHALL agregarse encima, nunca reemplazar la
lógica heredada.

#### Scenario: Rutas heredadas conservadas

- **WHEN** se compara el conjunto de rutas del TP original con el adoptado
- **THEN** todas las rutas del TP siguen existiendo con el mismo método, path y contrato de entrada/salida

#### Scenario: Comportamiento heredado conservado

- **WHEN** se ejecutan los casos de catálogo, clientes y ventas que el TP ya resolvía
- **THEN** responden con el mismo status y el mismo cuerpo que en el TP entregado

#### Scenario: Cambios del parcial por agregado

- **WHEN** se revisan los archivos heredados que el parcial necesita tocar
- **THEN** los cambios son agregados compatibles (columnas, relaciones o rutas nuevas) y no una
  reescritura de la lógica existente

### Requirement: Migraciones heredadas conservadas y encadenadas

El proyecto SHALL conservar las migraciones `0001` y `0002` del TP con sus revisiones y enlaces originales,
y SHALL encadenar cualquier migración nueva a partir de la última revisión heredada.

#### Scenario: Historial heredado completo

- **WHEN** se ejecuta el historial de migraciones del proyecto adoptado
- **THEN** aparecen las dos revisiones del TP en su orden original

#### Scenario: Migraciones heredadas no editadas

- **WHEN** se comparan los archivos de las migraciones `0001` y `0002` con los del TP original
- **THEN** son idénticos

#### Scenario: Cadena consistente

- **WHEN** se aplican todas las migraciones sobre una base vacía
- **THEN** la cadena llega a la última revisión sin errores ni saltos

### Requirement: Cierre documentado de las columnas heredadas

El proyecto SHALL documentar en `docs/BASELINE_TP_CAP1a4.md` el valor confirmado de `SU-01` (tipo de las
claves primarias), `SU-07` (columna de vendedor en `venta`), `SU-08` (nombre de la columna del precio
copiado en `renglon_venta`) y `SU-09` (revisiones de las migraciones `0001` y `0002`), cada uno con su
evidencia.

#### Scenario: Documento completo

- **WHEN** se revisa `docs/BASELINE_TP_CAP1a4.md`
- **THEN** los cuatro supuestos aparecen con valor confirmado y con la evidencia usada para confirmarlo

#### Scenario: Evidencia verificable

- **WHEN** se sigue la evidencia citada para cualquiera de los cuatro supuestos
- **THEN** se llega a un archivo, migración o consulta del TP cap. 1-4 que confirma el valor

### Requirement: Esquema heredado verificado intacto

Tras adoptar el TP, el esquema resultante SHALL conservar las tablas y columnas heredadas sin renombrarlas
ni eliminarlas, y los tipos de dinero y fecha heredados SHALL mantenerse tal como fueron entregados.

#### Scenario: Tablas heredadas presentes

- **WHEN** se aplican las migraciones heredadas y se listan las tablas
- **THEN** están todas las tablas de catálogo, clientes y ventas del TP

#### Scenario: Columnas heredadas sin cambios

- **WHEN** se comparan las columnas de las tablas heredadas con las del TP original
- **THEN** no falta, sobra ni se renombró ninguna columna

#### Scenario: Tipos preservados

- **WHEN** se inspeccionan las columnas de dinero y de fecha heredadas
- **THEN** conservan exactamente el tipo con el que fueron entregadas y ninguna columna de dinero pasa a
  coma flotante

### Requirement: Copia de despliegue separada e intacta

El proyecto SHALL mantener en `despliegue/` una copia intacta del TP cap. 1-4, sin ninguna modificación del
parcial, y SHALL tratarla como un proyecto independiente.

#### Scenario: Copia sin cambios del parcial

- **WHEN** se busca en `despliegue/` cualquiera de las incorporaciones del parcial (roles, movimientos de
  stock, Unit of Work, rutas nuevas)
- **THEN** no aparece ninguna

#### Scenario: Copia idéntica al TP

- **WHEN** se compara `despliegue/` con el TP cap. 1-4 recibido al cierre de este change
- **THEN** el contenido es idéntico y sólo se le agregan artefactos de despliegue en changes posteriores

### Requirement: Baseline incompleto no se completa con supuestos

Mientras falte el TP cap. 1-4 o alguna de las cuatro columnas heredadas no pueda confirmarse, el baseline
SHALL considerarse no adoptado y el change SHALL permanecer bloqueado en esa parte, sin inventar nombres,
tipos ni revisiones.

#### Scenario: Material faltante

- **WHEN** no se dispone del repo o `.zip` del TP cap. 1-4
- **THEN** no se crea ningún archivo que declare valores del esquema heredado y la parte de adopción queda
  pendiente

#### Scenario: Columna no confirmada

- **WHEN** una de las cuatro columnas heredadas no puede verificarse contra las migraciones del TP
- **THEN** se registra como pendiente y no se asume un nombre o tipo plausible
