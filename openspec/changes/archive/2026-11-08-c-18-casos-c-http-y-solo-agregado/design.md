# Design — C-18 casos-c-http-y-solo-agregado

**Decision: no (no UI)** — el change no toca pantallas, componentes ni estilos; produce artefactos de prueba.

## Context

Estado real del repo que condiciona el diseño (verificado, no supuesto):

- `parcial/test/` tiene hoy: `auth.http` (C-03/04/05 + logout + entradas inválidas), `registro.http` (C-02 con
  `@sufijo` y conteos SQL), `roles.http` (C-06/C-07 con usuarios `ana@`, `beto@`, `vendedor@`, `vencido@`
  sembrados por SQL manual), `ventas.http` (C-10/11/12 y el contrato de C-16), `tp.http` (baseline con
  `"stock"` en el alta, ya inválido) y dos registros de evidencia de C-12/C-16.
- Desde C-17, `python seed.py` deja un estado estable y **verificado por el propio script**: usuarios
  `admin@`, `admin2@` (ADMIN), `vendedor@`, `nuevo@` (VENDEDOR, este con `debe_cambiar_password`), `ana@`
  (CLIENTE); libros `1…5` = Rayuela, Antología, Ficciones, Respiración artificial, Bestiario con stock
  **10/5/8/3/1** y precios 25000/30000/22000/27000/18000; clientes `1` Lucía, `2` Tomás, `3` Ana Paz (ligada a
  `ana@`); venta `1` de Lucía con total `69000.00` (1 Rayuela + 2 Ficciones); siete movimientos; una línea
  `evento_seguridad` con actor `SISTEMA`; `intento_acceso` **vacía**. Las contraseñas ficticias están en el
  docstring de `seed.py`.
- Rutas relevantes ya implementadas: `GET /libros/{id}` público; `POST/PATCH/DELETE /libros`, `/libros/{id}/reponer` y
  `/libros/{id}/movimientos` ADMIN; `POST /auth/login|registro|logout|cambiar-password`, `GET /auth/yo` abiertos;
  `GET /ventas/{id}`, `GET /ventas`, `GET /ventas/mis-ventas`, `POST /ventas` protegidas; `POST /usuarios`,
  `POST/DELETE /usuarios/{id}/roles[/{rol}]`, `GET /usuarios/{id}/roles`, `GET /eventos` ADMIN.
- Las rutas de catálogo usan prefijo `/libros` y aceptan `page`, `size`, `titulo` y `genero_id`; `paginar`
  responde `422` con `"La página N no existe: hay M"` y `size` fuera de 1…100.
- `0004` define `trg_movimiento_stock_no_modificable` (`BEFORE UPDATE OR DELETE`) con el mensaje
  `movimiento_stock es de solo agregado: operacion <OP> no permitida`.
- El registro de ventas usa `BackgroundTasks` (después del commit) con `asyncio.sleep(0.5)` y una línea de log;
  `uvicorn main:app` con el logging por defecto ya la muestra.
- El entorno del agente es headless: **no puede operar la GUI de REST Client**. Sí puede correr `psql`,
  `uvicorn` y peticiones equivalentes con `httpx`.

## Goals / Non-Goals

**Goals**

- Dejar `parcial/test/` con la evidencia exigida: C-01…C-16 en `.http` por módulo, `solo_agregado.sql` para
  C-14 y el caso del aviso de C-10.
- Que cada bloque sea autoexplicativo para la corrección: status, cuerpo/fragmento esperado y `RN-xx`.
- Que los archivos dependan sólo de `alembic upgrade head` + `python seed.py`, sin bootstraps SQL ad hoc.
- Producir las capturas crudas de C-14 y C-15 y un registro honesto de qué se ejecutó.

**Non-Goals**

- No cambiar código de producción, contratos, esquema, migraciones ni `seed.py`.
- No tocar `despliegue/` ni los casos D.
- No duplicar la suite `tests/` (C-19) ni convertir `test/` en pytest.
- No “arreglar” en este change un defecto que aparezca al correr un caso: se documenta y se decide un change
  aparte; C-18 sólo mide.

## Decisions

### 1. Cinco archivos `.http`, asignados por módulo, y retiro de `tp.http`

| Archivo | Casos | Contenido |
|---|---|---|
| `test/registro.http` | C-02 | 201 de alta; 409 por correo de usuario (`admin@`) y por correo de cliente (`lucia@`); 422 de `rol`, 73 bytes y 80 bytes; 72 bytes aceptado; conteos SQL antes/después |
| `test/auth.http` | C-03, C-04, C-05 | cookie y sus flags; cuerpo sin token; 401 sin cookie y con `Authorization: Bearer`; 401 idéntico para contraseña mala y correo inexistente; cinco fallos + sexto 429 con `Retry-After` y verificación en `intento_acceso` |
| `test/roles.http` | C-06, C-07, C-08, C-09 | 401/403 y propiedad; dos sesiones y revocación/vencimiento; 422 de `vence_en`; 409 de auto-revocación de ADMIN; cambio obligatorio de `nuevo@` y misma cookie después |
| `test/libros.http` | C-01, C-13, C-16 | 422 de `{id}` no entero con sesión; reponer/baja/re-alta/venta vieja; paginación, inyección, PATCH parcial y `stock` en PATCH → 422 |
| `test/ventas.http` | C-10, C-11, C-12, C-15, C-16 | venta de 2 renglones con totales/stock/movimientos y aviso; 409 sin escrituras; los tres 409; venta de 4 renglones; contrato del cuerpo de venta |
| `test/solo_agregado.sql` | C-14 | `UPDATE` y `DELETE` rechazados por el disparador |

`tp.http` se retira: su payload usa `stock` (hoy `422` por `extra="forbid"`), su “C-02 ISBN repetido” ya no
corresponde al caso C-02 de la consigna y sus ids fijos (`libro_id: 4`, `cliente_id: 2`) no coinciden con los
datos que el archivo declara. Sus dos verificaciones útiles —`GET /libros/abc` y la búsqueda con
`' OR '1'='1`— se mudan a `libros.http`, ya con la respuesta esperada. Los dos `.md` de evidencia de C-12/C-16
se conservan como historial; C-18 agrega su propio registro.

### 2. Un archivo = una corrida desde el seed; el orden dentro del archivo es parte del caso

Cada archivo se ejecuta completo después de `python seed.py`. Los casos que mutan estado se ordenan de forma
explícita y el encabezado lo advierte: C-09 deja `nuevo@` con otra contraseña; C-07 revoca roles; C-13 crea,
da de baja y re-alta un libro; C-06 registra una venta para Ana. Por eso **no se encadenan archivos**: la
puesta en marcha de la corrección es `alembic upgrade head` → `python seed.py` → abrir un archivo, y se repite
el seed antes de cada uno. Esto es exactamente lo que la consigna pide («antes de cada archivo se corre
`python seed.py`») y evita ids y stocks contaminados.

Dentro de `roles.http` el orden es: sesiones → C-06 (venta de Ana creada por el vendedor) → C-07 (revocación y
vencimiento) → C-08 (auto-revocación) → C-09 (cambio de contraseña, último porque invalida la clave del seed).

### 3. C-06 no inventa datos: el vendedor registra la venta de Ana

El seed no trae una venta de Ana, y el caso exige «la cliente ve su venta 200 y la ajena 403». En vez de
insertar filas por SQL, `roles.http` inicia el vendedor y hace `POST /ventas` con
`cliente_id = 3, renglones: [{libro_id: 3, cantidad: 1}]`; la respuesta `201` da el `id` que Ana consulta
después con su cookie (`200`), mientras que `GET /ventas/1` (la de Lucía) da `403`. La venta queda explicada
como preparación del caso, no como una escritura oculta, y consume stock de un libro que ningún caso posterior
del mismo archivo necesita.

### 4. C-07 usa dos sesiones reales en el mismo documento

Los dos logins se guardan con nombre y las peticiones de cada identidad no comparten cookie jar:

```
# @name login_admin
POST {{host}}/auth/login
...
###
# @name login_vendedor
POST {{host}}/auth/login
...
###
# @no-cookie-jar
GET {{host}}/auth/yo
Cookie: {{login_vendedor.response.headers.Set-Cookie}}
```

El administrador revoca `VENDEDOR` de `vendedor@` con `DELETE /usuarios/3/roles/VENDEDOR`; la siguiente
petición del vendedor con **su** cookie da `403`, `/auth/yo` muestra `roles` sin `VENDEDOR` y `roles_token`
con `VENDEDOR`, y `GET /usuarios/3/roles` (con la cookie del admin) confirma que la fila sigue con
`revocada_en` no nulo. El vencimiento se prueba con `POST /usuarios/4/roles` (Ana) y un `vence_en` en el pasado
y otro sin zona → `422` en los dos; luego se asigna un vencimiento futuro válido → `201` y se comprueba que no
autoriza después (con la cookie de Ana y una venta ajena → `403`; o simplemente `GET /auth/yo` con roles
vigentes sin el rol vencido).

### 5. C-02 se apoya en los datos del seed, sin `INSERT` de preparación

Los dos `409` se consiguen con filas que el seed ya deja: `admin@example.com` ya existe como **usuario** y
`lucia@example.com` ya existe como **cliente** con `usuario_id` nulo. El comentario del bloque indica los
`count(*)` de `usuario`, `asignacion_rol` y `cliente` antes y después, y el `SELECT` de la ficha de Lucía para
probar que el registro rechazado no se apropió de ella (`usuario_id` sigue nulo). El alta válida usa un correo
`c02-<sufijo>@example.com` y el propio comentario advierte que hay que cambiar el sufijo o volver a sembrar.

### 6. C-13 crea su propio libro para no alterar el catálogo del seed antes de C-16

`libros.http` hace: alta ADMIN con ISBN `978-950-00-9001-1` y `stock_inicial: 3` → `201`; `reponer` +2 → `200`
y stock 5 con movimiento `Reposición`; `GET /libros/{id}/movimientos` → `200` con los dos movimientos; venta de
1 ejemplar por el vendedor → `201` (para tener una venta vieja); `DELETE /libros/{id}` → `204`; el libro
desaparece de `GET /libros` y `GET /libros/{id}` → `404`; `GET /ventas/{venta_id}` sigue mostrando el título;
`POST /libros` con el mismo ISBN → `201` (re-alta); un segundo alta con ese ISBN aún vigente → `409`; vender o
reponer el libro dado de baja → `409`. Se hace con un libro nuevo para que los stocks 10/5/8/3/1 del seed sigan
intactos en los casos de C-16 del mismo archivo.

### 7. C-16 se reparte entre catálogo y ventas, sin repetir el mismo resultado

En `libros.http`: `GET /libros?size=2` → `200` con `total: 5`, `pages: 3`, `size: 2`; `page=4` → `422` «La
página 4 no existe: hay 3»; `GET /libros?titulo=ficc&size=1` → `total: 1`, `pages: 1`, `page: 2` → `422`;
`GET /libros?titulo=%27%20OR%20%271%27%3D%271` → `200` con `items: []`, `total: 0`, `pages: 1`;
`PATCH /libros/1` con sólo `titulo` → `200` y `precio` sin cambios; `PATCH /libros/1` con `stock` → `422`.
En `ventas.http`: `renglones: []` → `422`, libro repetido → `422`, `precio`/`total`/`fecha` en el cuerpo →
`422`, y `POST /ventas` sin barra final → `201` sin `307`. El `PATCH` que cambia un título se revierte con
`alembic`/seed en la siguiente corrida; se documenta que no se busca persistencia.

### 8. C-14: dos sentencias en un archivo, `psql` sigue tras el error

`test/solo_agregado.sql` apunta a filas reales del seed y no usa transacción propia (si la usara, el primer
error la abortaría y no se vería el segundo):

```sql
UPDATE movimiento_stock
   SET cantidad = cantidad
 WHERE id = (SELECT min(id) FROM movimiento_stock);

DELETE FROM movimiento_stock
 WHERE id = (SELECT max(id) FROM movimiento_stock);
```

`psql -f test/solo_agregado.sql` sin `ON_ERROR_STOP` imprime los dos `ERROR` (`… operacion UPDATE no
permitida` y `… operacion DELETE no permitida`) y termina; las filas siguen ahí. El registro de evidencia
guarda la salida completa y el `SELECT count(*) FROM movimiento_stock` posterior, que debe seguir en 7.

### 9. C-15: contar `SELECT` con `SQL_ECHO=true`, no “a ojo”

Se arranca `uvicorn` con `SQL_ECHO=true` y se captura la consola en un archivo. La venta de 2 renglones es la
`1` del seed; la de 4 se registra en el mismo archivo con 1 ejemplar de Rayuela, Antología, Ficciones y
Respiración artificial (stock suficiente). El método de conteo queda escrito: se marca en la captura el inicio
de cada petición (`GET /ventas/1` y `GET /ventas/<n>`) y se cuentan las líneas cuyo SQL comienza con `SELECT`
entre marcas, **incluyendo** las de autenticación/rol (idénticas en ambas) para no depender de recortes
manuales. El resultado esperado es el **mismo número** en los dos detalles. El archivo de captura se guarda en
`parcial/test/evidencia/c-15_consultas_2y4.txt`; C-19 lo copia a `parcial/evidencia/` con el nombre definitivo.

### 10. C-10 y el aviso: la prueba es el orden de las líneas de uvicorn

Se arranca `uvicorn main:app` sin `--log-config` ni variables extra, se registra la venta desde
`ventas.http` y se guarda la consola. Lo que se evidencia es el orden: la línea del access log de la respuesta
`201` aparece antes que `Comprobante de la venta <id> enviado al cliente`. La captura va a
`parcial/test/evidencia/c-10-backgroundtasks.txt`; si el mensaje apareciera antes, el caso falla y se reporta
como defecto (no se “ajusta” el logging en C-18).

### 11. La evidencia separa autoría de ejecución

`parcial/test/EVIDENCIA.md` es una tabla caso → archivo → status esperado → método → resultado observado →
fecha/entorno. Tres estados posibles, sin ambigüedad:

- `archivo escrito`: el bloque existe y el resultado esperado está documentado, pero no se ejecutó.
- `corrida equivalente`: se ejecutó con `httpx` (o `curl`) contra el servidor real; se guardan status y cuerpo
  observados y se aclara que el `.http` sigue siendo el formato de revisión manual.
- `corrida REST Client`: la hizo el usuario en su GUI; el registro lo indica y adjunta su captura.

Ningún caso se marca ejecutado sin salida. Esta distinción es la que evita que el change mienta sobre el
entorno headless y la que la corrección puede auditar.

## Risks / Trade-offs

- **[La GUI de REST Client no corre headless]** → Se entregan los `.http` y una corrida equivalente con
  `httpx` documentada; la corrida real con REST Client queda como tarea del usuario, explícita en
  `EVIDENCIA.md`. No se inventan capturas.
- **[C-09 cambia la contraseña de `nuevo@` y C-07 revoca roles]** → Cada archivo asume seed fresco y el
  encabezado lo dice; dentro de `roles.http` esos casos van al final. Repetir el archivo exige volver a sembrar.
- **[C-13 y C-06 escriben datos]** → Se usan un libro nuevo y una venta de Ana para no mover los stocks que
  C-10/C-11/C-16 asumen; aun así, el archivo se corre después del seed y no se encadena con otro.
- **[C-05 bloquea un correo durante la ventana de 60 s]** → Se usa un correo inexistente dedicado
  (`c05-...@example.com`), nunca una cuenta del seed, para no bloquear C-03/C-04 del mismo archivo.
- **[La codificación de algunos mensajes del repo está rota]** → Los comentarios se escriben en UTF-8 con los
  acentos correctos; las comparaciones de la checklist se hacen por status y por el texto esperado de la
  consigna, y si un `detail` real difiere por mojibake se anota como defecto, no se “corrige” el `.http` para
  taparlo.
- **[Contar `SELECT` a mano es frágil]** → Se fija el método (marcas de petición + líneas que empiezan con
  `SELECT`) y se guarda la captura completa, de modo que la corrección pueda recontar.
- **[`psql` sin `ON_ERROR_STOP` devuelve código 0 pese a los errores]** → El criterio de C-14 son los dos
  mensajes de error en la salida y las filas intactas, no el exit code; el registro lo aclara.
- **[Un caso puede revelar un defecto real]** → C-18 no modifica producción: se documenta el desvío, se marca
  el ítem como no cumplido y se propone un change de corrección. Ése es el valor de la evidencia.

## Migration Plan

1. Reescribir/crear los cinco `.http`, retirar `tp.http` y agregar `solo_agregado.sql`.
2. Sobre una base migrada: `python seed.py` y correr cada archivo (REST Client o equivalente), anotando
   resultados en `EVIDENCIA.md`.
3. Producir las capturas de C-10, C-14 y C-15 en `parcial/test/evidencia/`.
4. Revertir es borrar los archivos nuevos y restaurar `tp.http` desde git; no hay cambios de esquema ni de
   datos persistentes.

## Open Questions

- El nombre definitivo de las capturas dentro de `parcial/evidencia/` lo fija C-19; en C-18 se usan nombres
  descriptivos y se deja la correspondencia escrita.
- Si la corrección prefiere un `.http` por caso en vez de por módulo, el contenido ya está separado por
  bloques `### C-NN` y se puede dividir sin reescribir los cuerpos.
