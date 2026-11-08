# Evidencia de C-18 — casos `C-01…C-16` en `parcial/test/`

> **Qué es este archivo.** El registro honesto de qué se escribió y qué se ejecutó para el
> change `c-18-casos-c-http-y-solo-agregado`, cómo se ejecutó y qué salida se observó.
> Tres estados posibles, sin ambigüedad:
>
> - `archivo escrito`: el bloque existe con su `# Esperado:` y su `RN-xx`, pero no se ejecutó.
> - `corrida equivalente`: se ejecutó con `httpx` contra el servidor real (uvicorn + PostgreSQL);
>   se guardan status y cuerpo observados. El `.http` sigue siendo el formato de revisión manual.
> - `corrida REST Client`: la hizo el usuario en su GUI. **En este entorno no se hizo**: REST
>   Client es una GUI y el agente corre headless. Ningún caso se marca así.
>
> Fecha de las corridas: **2026-11-08**. Base: PostgreSQL 17 en `127.0.0.1:5432/libreria`
> (usuario `libreria`; credenciales en `parcial/.env`, no se reproducen acá).

---

## 1. Entorno y puesta en marcha

```powershell
cd parcial
alembic upgrade head                 # esquema sólo por Alembic (CV-14)
python seed.py                       # estado canónico de C-17
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- `GET /health/live` → **200** `{"status":"ok"}`.
- `GET /health/ready` → **200** `{"status":"ok"}`.
- Para C-01 y C-15 el servidor se arrancó con `SQL_ECHO=true`; para C-10, sin configuración
  extra de logging (`python -u -m uvicorn main:app`, `-u` sólo evita el buffer de stdout al
  redirigir la consola).
- Antes de **cada** archivo se corrió `python seed.py` (un archivo = una corrida desde el seed;
  no se encadenan archivos). Después de la última corrida la base quedó sembrada y consistente.

## 2. Línea base del seed (tarea 1.1)

Se corrió `python seed.py` **dos veces**. Las dos corridas imprimieron los mismos conteos y los
mismos ids:

| Control | Resultado |
|---|---|
| `SELECT titulo, stock FROM libro ORDER BY id` | Rayuela 10, Antología 5, Ficciones 8, Respiración artificial 3, Bestiario 1 |
| `SELECT total FROM venta WHERE id = 1` | `69000.00` |
| `SELECT count(*) FROM movimiento_stock` | `7` |
| Invariante `libro.stock = SUM(movimiento_stock.cantidad)` | **0 filas** (0 violaciones) |
| `usuario / asignacion_rol / editorial / genero / autor / libro / cliente` | 5 / 5 / 3 / 3 / 6 / 5 / 3 |
| `perfil_cliente / venta / renglon_venta / evento_seguridad` | 1 / 1 / 2 / 1 |

Ids estables: usuarios 1 `admin@`, 2 `admin2@`, 3 `vendedor@`, 4 `ana@`, 5 `nuevo@`; clientes
1 Lucía, 2 Tomás, 3 Ana Paz; libros 1…5; venta 1.

Contraseñas ficticias del seed (`seed.py`, docstring): `admin-ficticia-2024`,
`admin2-ficticia-2024`, `vendedor-ficticia-2024`, `ana-ficticia-2024`,
`nuevo-ficticia-2024`.

## 3. Inventario de archivos (tarea 1.2)

| Archivo | Casos | Estado |
|---|---|---|
| `test/registro.http` | C-02 | reescrito sobre el seed (sin `INSERT` de preparación) |
| `test/auth.http` | C-03, C-04, C-05 | reescrito sobre el seed |
| `test/roles.http` | C-06, C-07, C-08, C-09 | reescrito sin el bootstrap SQL de `ana@`/`beto@`/`vencido@` |
| `test/libros.http` | C-01, C-13, C-16 (catálogo) | **nuevo** |
| `test/ventas.http` | C-10, C-11, C-12, C-15, C-16 (cuerpo) | reescrito sobre el seed |
| `test/solo_agregado.sql` | C-14 | **nuevo** |
| `test/tp.http` | — | **retirado** (ver §4) |
| `evidencia/c-10-backgroundtasks.txt` | C-10 | captura cruda entregable (copia de `test/evidencia/`) |
| `test/evidencia/c-14_solo_agregado.txt` | C-14 | captura cruda de `psql` |
| `test/evidencia/c-15_consultas_2y4.txt` | C-15 | captura cruda con `SQL_ECHO=true` |

`registro_http_evidence.md` y `ventas_http_evidence.md` (de changes anteriores) se conservan como
historial; este archivo es el registro de C-18.

### Casos que faltaban antes de C-18 (detectados en el inventario)

C-01 con sesión, C-08, C-09, C-13, C-14, C-15, la paginación y el PATCH parcial de C-16, el
`stock` en PATCH → 422, el aviso de `BackgroundTasks` (C-10) y las dos sesiones con `# @name` /
`# @no-cookie-jar` de C-07. Todos quedaron cubiertos.

## 4. Retiro de `tp.http` (tarea 1.4)

`parcial/test/tp.http` se borró. Motivos y destino de sus verificaciones útiles:

- `GET /libros/abc` → **migrado** a `libros.http` C-01.1, ahora con sesión y con el cuerpo
  esperado (`422`, `loc: ["path","libro_id"]`, `int_parsing`).
- Búsqueda `' OR '1'='1` → **migrada** a `libros.http` C-16.6, con `items: []`, `total: 0`.
- El resto usaba el payload viejo (`"stock"` en el alta, hoy `422` por `extra="forbid"`), ids
  fijos que no coincidían con los datos del archivo y casos que ya no corresponden a `C-02`
  (ISBN repetido del alta, perfil duplicado). Esos contratos viven hoy en `libros.http` y
  `registro.http`.

## 5. Resultado por caso

Todas las filas son **corrida equivalente** (`httpx` contra uvicorn + PostgreSQL), salvo donde se
indica otra cosa. "Observado" resume el status y el fragmento decisivo; el cuerpo completo de la
corrida quedó en la sesión de trabajo y los valores clave están en las capturas de §6.

### C-02 — `test/registro.http`

| Bloque | Esperado | Observado |
|---|---|---|
| C-02.1 alta válida | 201, 5 claves, sin `Set-Cookie` | **201** `{"id":6,"email":"c02-alta-…","nombre":"Ana Pérez","activo":true,"debe_cambiar_password":false}`, sin `Set-Cookie` |
| C-02.2 correo de usuario | 409 «Ya existe un usuario con ese email» | **409** idéntico |
| C-02.3 correo de cliente | 409 «Ya existe un cliente con ese email» | **409** idéntico; `lucia@` sigue con `usuario_id` NULL |
| C-02.4 `rol` extra | 422 `extra_forbidden` | **422** `loc: ["body","rol"]`, «El campo no está permitido» |
| C-02.5 73 bytes | 422 | **422** `loc: ["body","password"]`, `value_error` |
| C-02.6 40 «ñ» (80 bytes) | 422 | **422** idéntico a C-02.5 |
| C-02.7 72 bytes | 201 | **201** `{"id":9,…}` |

Conteos SQL antes/después: `usuario` 5→7, `asignacion_rol` 5→7, `cliente` 3→5; exactamente +2/+2/+2
por las dos altas 201. La ficha de `lucia@example.com` conserva `usuario_id` NULL (el 409 de
C-02.3 no dejó filas sueltas).

### C-03 / C-04 / C-05 — `test/auth.http`

| Bloque | Esperado | Observado |
|---|---|---|
| C-03.1 login | 200 + `Set-Cookie` HttpOnly, sin token en el cuerpo | **200** `{"mensaje":"Sesión iniciada","debe_cambiar_password":false,"expira_en_segundos":1800}`; `access_token=…; HttpOnly; Max-Age=1800; Path=/; SameSite=lax` |
| C-03.2 `/auth/yo` sin cookie | 401 | **401** `{"detail":"No autenticado"}` |
| C-03.3 `Authorization: Bearer` inventado | 401 | **401** `{"detail":"No autenticado"}` |
| C-04.1 contraseña mala | 401 «Credenciales inválidas» | **401**, 16,2 ms |
| C-04.2 correo inexistente | 401 mismo cuerpo, tiempo comparable | **401**, 11,9 ms |
| C-05 intentos 1–5 | 401 cada uno | **401** ×5 |
| C-05 sexto intento | 429 + `Retry-After` ms | **429** `{"detail":"Demasiados intentos de inicio de sesión"}`, `Retry-After: 59945` |
| logout (complemento) | 200 + `Max-Age=0` | **200** `{"mensaje":"Sesión cerrada"}`, `Max-Age=0` |

`SELECT … FROM intento_acceso WHERE email='c05-no-existe@example.com'` → **6 filas**, todas
`exito = false` (5 procesadas + la limitada).

### C-06 / C-07 / C-08 / C-09 — `test/roles.http`

| Bloque | Esperado | Observado |
|---|---|---|
| C-06.1 `GET /ventas/1` sin cookie | 401 | **401** «No autenticado» |
| C-06.2 vendedor crea libro | 403 | **403** «No autorizado» |
| C-06.3 venta de Ana por el vendedor | 201 `cliente_id: 3` | **201** id 2, `total "22000.00"`, Ficciones |
| C-06.4 Ana lee su venta | 200 | **200** `cliente_id: 3`, detalle completo |
| C-06.5 Ana lee la venta de Lucía | 403 | **403** «No autorizado» |
| C-06.6 Ana lista sus ventas en `GET /mis-ventas` | 200, sólo `cliente_id: 3` | **200** envoltorio `{items,total,page,size,pages}` (tras el seed no hay ventas previas: `items: []`); ruta anterior → **404** |
| C-07.1 `/auth/yo` antes | 200 `roles:["VENDEDOR"]` | **200** `roles: ["VENDEDOR"]`, `roles_token: ["VENDEDOR"]` |
| C-07.2 revocar VENDEDOR | 200 con `revocada_en` | **200** fila id 3, `revocada_en` con fecha |
| C-07.3 misma cookie en ruta pública | 200 | **200** `/libros/1` |
| C-07.4 misma cookie en ruta ADMIN | 403 | **403** «No autorizado» |
| C-07.5 `/auth/yo` después | `roles: []`, `roles_token: ["VENDEDOR"]` | **200** exactamente eso |
| C-07.6 historial de roles | fila revocada visible | **200** `revocada_en` no nulo |
| C-07.7 `vence_en` en el pasado | 422 | **422** `loc: ["body","vence_en"]`, `value_error` |
| C-07.8 `vence_en` sin zona | 422 | **422** idéntico |
| C-07.9 `vence_en` futuro válido | 201 | **201** fila id 6 |
| C-07.10 login de Ana con el rol vigente | 200 | **200** |
| C-07.11 venta ajena **antes** de vencer | 200 (el rol está vigente) | **200** |
| C-07.11 venta ajena **después** de vencer | 403 | **403** «No autorizado»; `/auth/yo` → `roles: ["CLIENTE"]`, `roles_token: ["CLIENTE","VENDEDOR"]` |
| C-08.1 auto-revocación de ADMIN | 409 | **409** «No puede revocar su propio rol de administrador» |
| C-08.2 la fila sigue vigente | 200 con `revocada_en: null` | **200** |
| C-09.1 login de `nuevo@` | 200 `debe_cambiar_password: true` | **200** exacto |
| C-09.2 grupo protegido con clave pendiente | 403 | **403** «No autorizado» |
| C-09.3 `/auth/yo` con clave pendiente | 200 | **200** |
| C-09.4 cambiar contraseña | 200 «Contraseña actualizada» | **200** |
| C-09.5 misma cookie en grupo protegido | 200 | **200** envoltorio de ventas de Ana |

`asignacion_rol`: la fila `VENDEDOR` de `vendedor@` (id 3) quedó con `revocada_en`; la de Ana
(id 6) con `vence_en`. Ninguna se borró (RN-05).

> **C-07.9 → C-07.11 en la corrida equivalente.** El `.http` calcula
> `@vence_en_corto` al vuelo como `now() + 1 minuto` con la variable dinámica
> de REST Client (`{{$datetime iso8601 1 m}}`). Para que C-07.11 sea
> concluyente, la corrida equivalente asignó `vence_en = now + 2 s`, comprobó
> 200 antes del vencimiento y 403 después con la misma cookie. Si el minuto
> todavía no pasó, el rol sigue vigente y C-07.11 devuelve 200: no es un
> defecto, es que el vencimiento no ocurrió.

### C-01 / C-13 / C-16 catálogo — `test/libros.http`

| Bloque | Esperado | Observado |
|---|---|---|
| C-01.1 `GET /libros/abc` con sesión | 422 `loc: ["path","libro_id"]` | **422** `int_parsing`; sin `SELECT … FROM libro` entre petición y respuesta |
| C-16.1 `?size=2` | 200 `total: 5`, `pages: 3` | **200** exacto |
| C-16.2 `?size=2&page=4` | 422 «La página 4 no existe: hay 3» | **422** exacto |
| C-16.3 `?titulo=ficc&size=1` | 200 `total: 1`, `pages: 1` | **200** exacto |
| C-16.4 igual + `page=2` | 422 «…hay 1» | **422** exacto |
| C-16.5 `?size=500` | 422 | **422** `loc: ["query","size"]`, `less_than_equal` |
| C-16.6 `' OR '1'='1` | 200 `items: []`, `total: 0`, `pages: 1` | **200** exacto |
| C-16.7 PATCH sólo `titulo` | 200, `precio` intacto | **200** `"precio":"25000.00"` |
| C-16.8 PATCH con `stock` | 422 | **422** `extra_forbidden` «El campo no está permitido» |
| C-13.1 alta ADMIN | 201 stock 3 | **201** id 6, `"stock":3` |
| C-13.2 movimientos | 200 «Stock inicial» | **200** `cantidad: 3`, `motivo: "Stock inicial"` |
| C-13.3 reponer 2 | 200 stock 5 | **200** `"stock":5` |
| C-13.4 venta de 1 ejemplar | 201 | **201** id 2, `"total":"10000.00"` |
| C-13.5 DELETE | 204 | **204** |
| C-13.6 catálogo sin el libro | 200, libro ausente | **200** `total: 5`, id 6 ausente |
| C-13.7 `GET /libros/{id}` de baja | 404 | **404** «Libro no encontrado» |
| C-13.8 venta vieja | 200 con el título | **200** `titulo: "Libro de baja y re-alta C-13"` |
| C-13.9 re-alta mismo ISBN | 201 id nuevo | **201** id 7 |
| C-13.10 segundo alta vigente | 409 | **409** «Ya existe un libro con ese ISBN» |
| C-13.11 vender el dado de baja | 409 | **409** «El libro '…' está dado de baja» |
| C-13.12 reponer el dado de baja | 409 | **409** «El libro está dado de baja» |
| C-13.13 segundo DELETE | 404 | **404** «Libro no encontrado» |

Control SQL de C-13: dos filas con ISBN `978-950-00-9001-1` (id 6 con `borrado_en` no nulo y stock
4; id 7 vigente y stock 3). Los libros 1…5 conservaron stock 10/5/8/3/1. Invariante: 0 filas.

> **Desvío detectado y corregido en el `.http`.** `GET /libros/?page=4` con el `size` por defecto
> (20) da «La página 4 no existe: **hay 1**», no «hay 3»: el mensaje depende de `size`. El caso
> quedó como `?size=2&page=4` → «hay 3», que es el ejemplo de la consigna. Además `?size=500` lo
> rechaza la validación de `Query` (`less_than_equal`), no el mensaje propio de `paginar`; el
> `# Esperado:` se ajustó al cuerpo real.

### C-10 / C-11 / C-12 / C-15 / C-16 cuerpo — `test/ventas.http`

| Bloque | Esperado | Observado |
|---|---|---|
| C-10.1 venta de 2 renglones | 201 total 47000.00, precios copiados | **201** id 2; renglones `25000.00` / `22000.00`, subtotales correctos |
| C-10.2 `POST /ventas` sin barra | 201, sin 307 | **201** id 3 |
| C-10.3 detalle | 200 con 2 renglones | **200** exacto |
| C-11.1 Rayuela ×1 + Bestiario ×2 | 409 «Stock insuficiente para 'Bestiario'» | **409** exacto; `(venta, renglon, movimientos)` 3·5·10 antes y después; stocks 8/1 intactos; invariante 0 |
| C-12.1 cliente inexistente | 409 | **409** «El cliente indicado no existe» |
| C-12.2 libro inexistente | 409 | **409** «Uno o más libros indicados no existen» |
| C-12.3 alta + baja del libro descartable | 201 / 204 | **201** / **204** |
| C-12.4 vender el libro de baja | 409 | **409** «El libro 'Libro descartable C-12' está dado de baja»; venta/renglón sin cambios |
| C-16.1 `renglones: []` | 422 `too_short` | **422** «La lista no puede estar vacía» |
| C-16.2 libro repetido | 422 | **422** «No se puede incluir el mismo libro dos veces en una venta» |
| C-16.3 `precio` extra | 422 `extra_forbidden` | **422** `loc: ["body","precio"]` |
| C-16.4 `total` extra | 422 | **422** `loc: ["body","total"]` |
| C-16.5 `fecha` extra | 422 | **422** `loc: ["body","fecha"]` |
| C-16.6 `cantidad: 0` | 422 `greater_than_equal` | **422** `loc: ["body","renglones",0,"cantidad"]` |
| C-15.1 venta de 4 renglones | 201 total 104000.00 | **201** id 4 |
| C-15.2 detalle de 4 renglones | 200 con 4 renglones | **200** |

Controles SQL de C-10: `SELECT … FROM renglon_venta WHERE venta_id = 2` → `1|1|25000.00` y
`3|1|22000.00`; `movimiento_stock` de esa venta → dos filas `-1`, motivo `Venta`, `usuario_id` 3;
stock de Rayuela 10→9 y Ficciones 8→7. Conteos: 1·2·7 (seed) → 2·4·9 (tras C-10) → 3·5·10 (tras
C-10.2) → idénticos tras C-11 y C-12 (salvo el `Stock inicial` del libro descartable: 11) → 4·9·15
tras C-15. **Invariante global: 0 violaciones en todos los puntos medidos.**

### C-14 — `test/solo_agregado.sql`

| Sentencia | Esperado | Observado |
|---|---|---|
| `UPDATE movimiento_stock …` | error del disparador | `ERROR: movimiento_stock es de solo agregado: operacion UPDATE no permitida` |
| `DELETE FROM movimiento_stock …` | error del disparador | `ERROR: movimiento_stock es de solo agregado: operacion DELETE no permitida` |
| `SELECT count(*)` posterior | 7 filas | **7** |

Captura completa: [`test/evidencia/c-14_solo_agregado.txt`](evidencia/c-14_solo_agregado.txt).
`psql` se corrió **sin** `ON_ERROR_STOP` para que el segundo error se viera; el exit code no es el
criterio (el archivo no abre transacción propia).

## 6. Capturas producidas en este change

| Captura | Qué demuestra | Ruta |
|---|---|---|
| C-10 | el mensaje `Comprobante de la venta <id> enviado al cliente` aparece **después** de la línea de la respuesta `201` | `evidencia/c-10-backgroundtasks.txt` (copia entregable; original en `test/evidencia/`) |
| C-14 | los dos `ERROR` del disparador y las 7 filas intactas | `evidencia/c-14_solo_agregado.txt` |
| C-15 | **6 SELECT** con 2 renglones y **6 SELECT** con 4 renglones | `evidencia/c-15_consultas_2y4.txt` |

C-19 consolida estas tres capturas en `parcial/evidencia/` con el nombre definitivo.

### C-01 (prueba de "sin ejecutar el handler")

Con `SQL_ECHO=true`, la consola del servidor mostró, en este orden:

```
INFO:     127.0.0.1:… - "POST /auth/login HTTP/1.1" 200 OK
INFO:     127.0.0.1:… - "GET /libros/abc HTTP/1.1" 422 Unprocessable Content
```

Entre la línea de la respuesta del login y la de `GET /libros/abc` **no hay ninguna consulta**; y
después de la línea del `422` tampoco se emite SQL. La validación del path ocurre antes del
handler.

## 7. Trazabilidad con `docs/CHECKLIST_ENTREGA.md` §10 (tarea 10.1)

| Ítem | Archivo · bloque |
|---|---|
| C-01 | `libros.http` · C-01.1 |
| C-02 | `registro.http` · C-02.1 … C-02.7 |
| C-03 | `auth.http` · C-03.1 … C-03.3 |
| C-04 | `auth.http` · C-04.1, C-04.2 |
| C-05 | `auth.http` · C-05 (5 fallos + 429) |
| C-06 | `roles.http` · C-06.1 … C-06.5 |
| C-07 | `roles.http` · C-07.1 … C-07.11 |
| C-08 | `roles.http` · C-08.1, C-08.2 |
| C-09 | `roles.http` · C-09.1 … C-09.5 |
| C-10 | `ventas.http` · C-10.1 … C-10.3 + captura `c-10-backgroundtasks.txt` |
| C-11 | `ventas.http` · C-11.1 |
| C-12 | `ventas.http` · C-12.1 … C-12.4 |
| C-13 | `libros.http` · C-13.1 … C-13.13 |
| C-14 | `solo_agregado.sql` + captura `c-14_solo_agregado.txt` |
| C-15 | `ventas.http` · C-15.1, C-15.2 + captura `c-15_consultas_2y4.txt` |
| C-16 | `libros.http` · C-16.1 … C-16.8; `ventas.http` · C-16.1 … C-16.6 |

Los dieciséis `C-NN` aparecen al menos una vez en `parcial/test/*.http` y ninguno queda sin
ubicación. El aviso de `BackgroundTasks` (§10, último ítem de C-10) está en §6 de este archivo.

## 8. Hallazgos y desvíos (sin cambios de producción)

1. **`page=4` depende de `size`** (§5, C-16). El `.http` se corrigió a `size=2&page=4`; el
   comportamiento del servidor es correcto y coincide con la consigna.
2. **`size=500` lo rechaza la capa HTTP**, con `loc: ["query","size"]` y mensaje «El valor supera
   el máximo permitido». El mensaje propio de `paginar` queda para llamadas internas; el status
   (422) es el exigido.
3. **Rutas canónicas con barra final.** `GET /libros`, `GET /ventas` y `POST /libros` sin barra
   responden `307` (o `405` en `GET /ventas`, por la ruta `POST ""`); los `.http` usan `/libros/`
   y `/ventas/`. `POST /ventas` **sin** barra responde `201` sin redirección (C-10.2), que es el
   caso exigido.
4. **C-07 y el reloj.** REST Client no calcula fechas: `@vence_en_corto` se edita a mano y el
   efecto del vencimiento se demuestra en la corrida equivalente (§5).
5. **C-09 invalida la clave del seed** (`nuevo@`). Para repetir `roles.http` hay que volver a
   sembrar; está advertido en el encabezado del archivo y en la tarea C-09.5.
6. **Ningún defecto de producción apareció.** No se modificó `app/`, `main.py`, `migrations/`,
   `seed.py` ni `despliegue/`.

## 9. Lo que falta y no se declara cumplido

### Pasada manual ejecutada (2026-11-08)

No hay VS Code REST Client instalado en este entorno y el agente corre headless. La pasada
manual se hizo con **httpyac 6.16.7** (`npx --yes httpyac send <archivo> --all --output response
--no-color`) contra uvicorn + PostgreSQL 17.11, después de `python seed.py` para cada archivo.
Es una corrida real de los `.http`, no una captura de la GUI de REST Client.

| Archivo | Resultado | Captura |
|---|---|---|
| `auth.http` | 12/12 OK (C-03/04/05) | `test/evidencia/manual-auth.txt` |
| `registro.http` | 7/7 OK (C-02) | `test/evidencia/manual-registro.txt` |
| `roles.http` | 28/28 OK (C-06/07/08/09) | `test/evidencia/manual-roles.txt` |
| `libros.http` | 25/25 OK (C-01/13/16 catálogo) | `test/evidencia/manual-libros.txt` |
| `ventas.http` | 20/20 OK (C-10/11/12/15/16 cuerpo) | `test/evidencia/manual-ventas.txt` |
| `solo_agregado.sql` | dos errores del disparador y 7 filas | `test/evidencia/manual-solo_agregado.txt` |
| C-10 BackgroundTasks | 201 antes de los comprobantes | `test/evidencia/uvicorn-manual-c10-combined.log` |
| C-07 vencimiento real | 200 antes / 403 después, roles vs roles_token | `test/evidencia/manual-c07-vencimiento.txt` |

**Compatibilidad de httpyac.** httpyac expone el cuerpo de una respuesta nombrada, pero no
`response.headers.Set-Cookie` como REST Client. Para `roles.http`, `libros.http` y `ventas.http`
se usó una copia temporal en `test/_compat/` que sólo reemplaza esa expresión por una cookie
exportada en un script posterior al login; el contenido de las peticiones no cambió. Las copias
temporales no forman parte del entregable y se borraron al cerrar la pasada.

**C-07.11.** Con `@vence_en_corto = 2030-01-01` el rol sigue vigente y el `.http` devuelve 200;
eso es el comportamiento documentado, no un defecto. La corrida enfocada asignó
`vence_en = now + 3 s`, obtuvo 200 antes, 403 después y `/auth/yo` con
`roles: ["CLIENTE"]` / `roles_token: ["CLIENTE","VENDEDOR"]` (`manual-c07-vencimiento.txt`).

**C-14.** `psql -f` sin `ON_ERROR_STOP` termina con exit code 1 por los dos `ERROR` esperados;
el criterio es el texto de ambos errores y `count(*) = 7`, no el exit code.

### Pendiente

- **Corrida en REST Client (GUI): pendiente del usuario.** La pasada manual con httpyac cubre la
  ejecución de los archivos; abrir cada uno en VS Code después de `python seed.py` sigue siendo
  la verificación visual de la GUI. No se inventaron capturas de REST Client.
- **C-19** consolida las capturas en `parcial/evidencia/` y arma la suite `tests/`; C-18 no lo
  hace.
