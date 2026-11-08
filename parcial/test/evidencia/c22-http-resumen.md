# C-22 · ejecución real de los `.http` (2026-11-08)

Entorno: Windows 11, `python 3.13.2`, PostgreSQL 17.11 local
(`127.0.0.1:5432/libreria`), `uvicorn main:app --host 127.0.0.1 --port 8000`,
runner `npx --yes httpyac` 6.16.7. Antes de cada archivo se corrió
`python seed.py`; al terminar se volvió a sembrar y se detuvo `uvicorn`.

## Comandos

```powershell
cd parcial
python seed.py
cd <TEMP>\c22-http
npx --yes httpyac send <archivo>.compat.http --all --output response --no-color
```

Los archivos ejecutados son copias de compatibilidad **fuera del repositorio**
(`<TEMP>\c22-http`). Durante las corridas no se editaron los `.http`
versionados; después se corrigió una sola línea de `roles.http` (C-06.6, la
plantilla de la cookie de Ana). Las copias están en la carpeta temporal y no
se versionan.

## Transformaciones aplicadas a las copias

httpyac no resuelve las referencias de REST Client
`{{nombre.response.headers.Set-Cookie}}` ni `{{nombre.response.body.$.id}}`.
En las copias se reemplazaron por globales de httpyac, sin cambiar método, URL,
cabeceras ni cuerpos:

| Original (REST Client) | Copia (httpyac) |
|---|---|
| `{{login_admin.response.headers.Set-Cookie}}` | `{{$global.cookie_login_admin}}` |
| `{{login_vendedor.response.headers.Set-Cookie}}` | `{{$global.cookie_login_vendedor}}` |
| `{{login_ana.response.headers.Set-Cookie}}` | `{{$global.cookie_login_ana}}` |
| `{{login_ana_rol.response.headers.Set-Cookie}}` | `{{$global.cookie_login_ana_rol}}` |
| `{{login_nuevo.response.headers.Set-Cookie}}` | `{{$global.cookie_login_nuevo}}` |
| `{{venta_ana.response.body.$.id}}` | `{{$global.venta_ana_id}}` |
| `{{libro_c13.response.body.$.id}}` | `{{$global.libro_c13_id}}` |
| `{{venta_c13.response.body.$.id}}` | `{{$global.venta_c13_id}}` |
| `{{libro_baja.response.body.$.id}}` | `{{$global.libro_baja_id}}` |
| `{{venta_2renglones.response.body.$.id}}` | `{{$global.venta_2renglones_id}}` |
| `{{venta_4renglones.response.body.$.id}}` | `{{$global.venta_4renglones_id}}` |

Cada global se llena con un bloque de respuesta colocado después del request
nombrado: `$global.cookie_X = response.headers["set-cookie"]` y
`$global.X_id = response.parsedBody.id`.

El archivo versionado `roles.http` se corrigió el 2026-11-08: C-06.6 ahora
usa `Cookie: {{login_ana.response.headers.Set-Cookie}}`. La copia de
compatibilidad solo traduce esa referencia a `{{$global.cookie_login_ana}}`;
no cambia método, URL, cabeceras ni cuerpo de la petición.

**Secuencia de C-07.11**: se conservó
`@vence_en_corto = {{$datetime iso8601 1 m}}` y se insertó
`await sleep(62000)` después de `login_ana_rol`, antes del caso C-07.11. La
misma cookie se usa antes (200) y después (403) del vencimiento. No se usó
un flujo httpx aparte.

## Resultado

| Archivo | Requests HTTP | Resultado |
|---|---:|---|
| `auth.http` | 12 | **12/12**, C-03 200, C-03.2/3 401, C-04.1/2 401, C-05 401×5, sexto 429 con `Retry-After: 59957`, logout 200 con `Max-Age=0`. |
| `registro.http` | 7 | **7/7**, C-02.1 201, C-02.2/3 409, C-02.4/5/6 422, C-02.7 201. |
| `roles.http` | 28 | **28/28**, C-06.1 401, C-06.2 403, C-06.3 201, C-06.4 200, C-06.5 403, C-06.6 200, C-07 revocación/vencimiento 403, C-07.7/8 422, C-08 409, C-09 403→200. |
| `libros.http` | 25 | **25/25**, C-01.1 422, C-16.1…8, C-13.1…13 completos, sin 500. |
| `ventas.http` | 19 HTTP + bloque SQL | **19/19**, C-10 201/201/200, C-11 409, C-12 409/409/201+204/409, C-16.1…6 422, C-15 201/200. |

`httpyac` informa «20 requests processed» porque cuenta también el bloque de
comentarios SQL de C-10.4; las peticiones HTTP reales son las 19 de la tabla.

Salidas crudas: `c22-http-auth.txt`, `c22-http-registro.txt`,
`c22-http-roles.txt`, `c22-http-libros.txt`, `c22-http-ventas.txt`.
Los JWT de las cabeceras `Set-Cookie` se reemplazaron por `<jwt-redacted>` al
guardar la evidencia.

## Controles SQL posteriores

`c22-http-sql-controls.txt` y `c22-http-c14-solo-agregado.txt`:

```text
Tras la corrida de ventas: ventas 4, renglones 9, movimientos 15.
Invariante libro.stock = SUM(movimiento_stock.cantidad): 0 filas.
solo_agregado.sql: UPDATE rechazado, DELETE rechazado, 15 filas intactas.
```

El log de `uvicorn` registró `Comprobante de la venta 2 enviado al cliente`
después del 201 de C-10.1; se conserva el fragmento en
`c22-http-backgroundtasks.txt`.

## Cobertura

C-01, C-02, C-03, C-04, C-05, C-06, C-07, C-08, C-09, C-10, C-11, C-12,
C-13, C-15 y C-16 tienen salida HTTP real en esta corrida. C-14 se cubrió con
`test/solo_agregado.sql` contra la misma base sembrada. C-07.11 se cubrió con
la expiración real de 1 minuto más la espera de 62 s descrita arriba.
