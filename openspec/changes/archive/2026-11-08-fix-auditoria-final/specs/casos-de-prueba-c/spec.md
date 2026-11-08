# Spec Delta — casos-de-prueba-c

## MODIFIED Requirements

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

## ADDED Requirements

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
