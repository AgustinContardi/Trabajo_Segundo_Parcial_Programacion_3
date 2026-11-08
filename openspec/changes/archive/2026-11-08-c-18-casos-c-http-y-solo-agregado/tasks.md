# Tasks — C-18 casos-c-http-y-solo-agregado

> **Modo de evidencia (RED → corrida → registro).** En cada archivo se escribe primero el bloque con su
> `# Esperado:` y su `RN-xx`; recién después se ejecuta y se anota la salida. Un caso sin resultado esperado
> previo no demuestra nada (checklist §10, governance ALTO). Comandos desde `parcial/`. REST Client es una GUI:
> el agente corre el equivalente con `httpx`/`curl` y lo declara; la corrida en REST Client la hace el usuario.

## 1. Línea base y mapa de cobertura

- [x] 1.1 **Línea base del seed.** Sobre una base migrada, correr `python seed.py` dos veces y verificar con
  `SELECT titulo, stock FROM libro ORDER BY id` (10/5/8/3/1), `SELECT total FROM venta WHERE id = 1`
  (69000.00), `SELECT count(*) FROM movimiento_stock` (7) y la query del invariante (0 filas). Anotar el
  resultado en `parcial/test/EVIDENCIA.md`. **Rastrea:** C-17, checklist §8, `RN-11`.
- [x] 1.2 **Inventario.** Listar los `.http` actuales, marcar qué casos C cubre cada uno y detectar los
  faltantes (C-01, C-08, C-09, C-13, C-14, C-15, C-16 de catálogo, aviso de C-10). Verificar con
  `ls parcial/test/*.http` y una tabla caso → archivo → estado (`falta`/`existente`) en `EVIDENCIA.md`.
  **Rastrea:** checklist §10.
- [x] 1.3 **Servidor y entorno.** Arrancar `uvicorn main:app` con `SQL_ECHO=true` en una terminal y comprobar
  `GET /health/live` y `GET /health/ready` → 200. Dejar escrito en `EVIDENCIA.md` el comando, el puerto y la
  base usada (sin credenciales). **Rastrea:** checklist §10, `CV-09`.
- [x] 1.4 **Retirar `tp.http`.** Borrar `parcial/test/tp.http` y dejar anotado en `EVIDENCIA.md` que sus dos
  verificaciones útiles (`GET /libros/abc`, búsqueda `' OR '1'='1`) se mudan a `libros.http` y que el resto
  usaba el payload viejo (`stock`), hoy `422`. Verificar con `ls parcial/test` (sin `tp.http`). **Rastrea:**
  diseño §1.

## 2. `registro.http` — C-02

- [x] 2.1 **RED (esperado primero).** Escribir `parcial/test/registro.http` con `@host` y `@sufijo`, y los
  bloques con su `# Esperado:`: alta válida 201 con `id/email/nombre/activo/debe_cambiar_password` y sin
  `password_hash` ni `Set-Cookie`; correo `admin@example.com` → 409 «Ya existe un usuario con ese email»;
  correo `lucia@example.com` → 409 «Ya existe un cliente con ese email»; `rol` extra → 422; 73 bytes → 422;
  40 «ñ» (80 bytes) → 422; 72 bytes → 201. **Rastrea:** checklist §10 C-02, `RN-02`, `RN-15`.
- [x] 2.2 **Verificación SQL de «sin filas sueltas».** Incluir en los comentarios los `SELECT count(*)` de
  `usuario`, `asignacion_rol` y `cliente` antes/después, y el `SELECT nombre, usuario_id FROM cliente WHERE
  email = 'lucia@example.com'` que debe seguir con `usuario_id` nulo. Verificar que el archivo no requiere
  ningún `INSERT` de preparación. **Rastrea:** diseño §5, `RN-15`.
- [x] 2.3 **Corrida.** Ejecutar el archivo (REST Client o equivalente) después de `python seed.py` y registrar
  en `EVIDENCIA.md` status y cuerpo observados de cada bloque, con el método usado. Verificar que los tres
  `count(*)` sólo crecen en las dos altas 201. **Rastrea:** checklist §10 C-02.

## 3. `auth.http` — C-03, C-04, C-05

- [x] 3.1 **RED (C-03).** Escribir en `parcial/test/auth.http` el login de `admin@example.com` con
  `# Esperado: 200`, `Set-Cookie: access_token=…; HttpOnly; Max-Age=1800; Path=/; SameSite=lax`, cuerpo
  `{"mensaje":"Sesión iniciada",...}` **sin token**; y los dos 401: sin cookie y con
  `Authorization: Bearer <token inventado>`. **Rastrea:** checklist §10 C-03, `RN-04`, `RN-06`.
- [x] 3.2 **RED (C-04).** Agregar contraseña incorrecta de `admin@` y correo inexistente
  (`c04-no-existe@example.com`) → los dos 401 con el mismo cuerpo `{"detail":"Credenciales inválidas"}` y
  tiempo comparable (anotar la duración que muestra el cliente). **Rastrea:** checklist §10 C-04, `RN-08`.
- [x] 3.3 **RED (C-05).** Agregar cinco intentos fallidos con `c05-no-existe@example.com` → 401 cada uno, y el
  sexto → 429 «Demasiados intentos de inicio de sesión» con `Retry-After` entero (ms). Incluir el `SELECT` de
  `intento_acceso` que debe mostrar al menos los cinco fallos con `exito = false` (la fila del 429 es la de
  `AB-03`). **Rastrea:** checklist §10 C-05, `RN-07`, `AB-03`.
- [x] 3.4 **Corrida.** Ejecutar después del seed y registrar en `EVIDENCIA.md`: status de los nueve bloques,
  flags de la cookie, ausencia de token en el cuerpo, duraciones de C-04 y el `SELECT` de `intento_acceso`.
  Verificar con `grep -c "C-0" parcial/test/auth.http` que los tres casos están rotulados. **Rastrea:**
  checklist §10 C-03/04/05.

## 4. `roles.http` — C-06, C-07, C-08, C-09

- [x] 4.1 **RED (C-06).** Reescribir `roles.http` sin el bootstrap SQL de `ana@`/`beto@`/`vencido@`: dos
  logins nombrados (admin y vendedor) y los bloques: `GET /ventas/1` sin cookie → 401; `POST /libros` con
  cookie de vendedor → 403 «No autorizado»; el vendedor crea una venta de Ana
  (`cliente_id: 3, libro_id: 3, cantidad: 1`) → 201; Ana (CLIENTE) lee **su** venta → 200 y `GET /ventas/1`
  (Lucía) → 403. **Rastrea:** checklist §10 C-06, `RN-04`, `RN-14`.
- [x] 4.2 **RED (C-07) dos sesiones.** Escribir dentro del mismo archivo los dos logins con `# @name
  login_admin` y `# @name login_vendedor`, y las peticiones del vendedor con `# @no-cookie-jar` y
  `Cookie: {{login_vendedor.response.headers.Set-Cookie}}`. Incluir: `/auth/yo` inicial con
  `roles: ["VENDEDOR"]`; `DELETE /usuarios/3/roles/VENDEDOR` con cookie del admin → 200; la misma cookie del
  vendedor en `GET /libros/1` → 200 (sigue autenticado) y en `POST /libros` → 403; `/auth/yo` con `roles: []`
  y `roles_token: ["VENDEDOR"]`; `GET /usuarios/3/roles` con el admin → fila con `revocada_en` no nulo.
  **Rastrea:** checklist §10 C-07, consigna p. 23, `RN-04`, `RN-05`.
- [x] 4.3 **RED (C-07 vencimiento).** Agregar `POST /usuarios/4/roles` con `vence_en` en el pasado → 422 y con
  `vence_en` sin zona (`"2030-01-01T00:00:00"`) → 422; un alta con zona y futuro → 201; luego login de Ana y
  `GET /ventas/1` → 403 (el rol vencido no autoriza). **Rastrea:** checklist §10 C-07, `RN-03`.
- [x] 4.4 **RED (C-08).** Agregar `DELETE /usuarios/1/roles/ADMIN` con la cookie de `admin@` → 409 «No puede
  revocar su propio rol de administrador» y comprobar en `GET /usuarios/1/roles` que la fila sigue vigente.
  **Rastrea:** checklist §10 C-08, `RN-05`.
- [x] 4.5 **RED (C-09).** Agregar login de `nuevo@example.com` (contraseña del seed) → 200 con
  `debe_cambiar_password: true`; `GET /clientes/3/ventas` → 403; `GET /auth/yo` → 200; `POST
  /auth/cambiar-password` con `password_actual`/`password_nueva` → 200 «Contraseña actualizada»; `GET
  /clientes/3/ventas` con **la misma cookie** → 200. Dejar escrito que este caso invalida la clave del seed y
  que hay que volver a sembrar. **Rastrea:** checklist §10 C-09, `RN-06`, `RN-16`, `IN-03`.
- [x] 4.6 **Corrida.** Ejecutar `roles.http` después del seed (el orden del archivo es C-06 → C-07 → C-08 →
  C-09) y registrar status/cuerpo y el `SELECT` de `asignacion_rol`. Verificar que ninguna petición dependió
  del cookie jar global. **Rastrea:** checklist §10 C-06/07/08/09.

## 5. `libros.http` — C-01, C-13, C-16 (catálogo)

- [x] 5.1 **RED (C-01).** Crear `parcial/test/libros.http` con `GET /libros/abc` enviando la cookie de sesión y
  `# Esperado: 422` (validación de path, `loc: ["path","libro_id"]`), más la comprobación en la consola con
  `SQL_ECHO=true`: entre la línea de la petición y la respuesta **no** aparece un `SELECT … FROM libro WHERE
  libro.id`. **Rastrea:** checklist §10 C-01, `RN-15`.
- [x] 5.2 **RED (C-13).** Agregar en orden: alta ADMIN con ISBN `978-950-00-9001-1`, `precio: 10000.00`,
  `stock_inicial: 3` → 201; `GET /libros/{id}/movimientos` → 200 con «Stock inicial»; `POST
  /libros/{id}/reponer {cantidad: 2}` → 200 y stock 5; venta de 1 ejemplar (vendedor) → 201; `DELETE
  /libros/{id}` → 204; `GET /libros` y `GET /libros/{id}` → el libro ya no aparece / 404; `GET
  /ventas/{venta_id}` → 200 con el título del libro dado de baja; `POST /libros` con el mismo ISBN → 201
  (re-alta); segundo alta con ese ISBN vigente → 409; vender y reponer el libro dado de baja → 409;
  segundo `DELETE` → 404. **Rastrea:** checklist §10 C-13, §8, `RN-01`, `RN-11`, `RN-13`.
- [x] 5.3 **RED (C-16 catálogo).** Agregar: `GET /libros?size=2` → 200 `total: 5`, `pages: 3`; `GET
  /libros?page=4` → 422 «La página 4 no existe: hay 3»; `GET /libros?titulo=ficc&size=1` → `total: 1`,
  `pages: 1` y `page=2` → 422; `GET /libros?size=500` → 422; `GET
  /libros?titulo=%27%20OR%20%271%27%3D%271` → 200 con `items: []`, `total: 0`, `pages: 1`; `PATCH
  /libros/1` con sólo `{"titulo": "Rayuela (edición corregida)"}` → 200 y `precio` intacto; `PATCH /libros/1`
  con `{"stock": 99}` → 422 «El campo no está permitido». **Rastrea:** checklist §10 C-16, §9, `RN-15`.
- [x] 5.4 **Corrida y control.** Ejecutar después del seed y registrar en `EVIDENCIA.md` los status/cuerpos.
  Verificar con `SELECT id, titulo, borrado_en, stock FROM libro WHERE isbn = '978-950-00-9001-1' ORDER BY id`
  que quedan dos filas —una con `borrado_en` no nulo y otra vigente— y que los cinco libros del seed siguen con
  stock 10/5/8/3/1. **Rastrea:** checklist §10 C-01/13/16, `RN-13`.

## 6. `ventas.http` — C-10, C-11, C-12, C-15, C-16 (cuerpo de venta)

- [x] 6.1 **RED (C-10).** Reescribir `ventas.http` sobre el seed: login de `vendedor@example.com`; venta
  `cliente_id: 1` (Lucía) con 2 renglones —1 Rayuela (`libro_id: 1`, 25000.00) y 1 Ficciones (`libro_id: 3`,
  22000.00)— → 201 con `total: 47000.00`, `precio_unitario` copiado y `subtotal`; stock de Rayuela 9 y Ficciones
  7; un movimiento negativo por renglón con `motivo: 'Venta'` y `usuario_id` del vendedor; `POST /ventas` sin
  barra final → 201 sin 307. **Rastrea:** checklist §10 C-10, `RN-09`, `RN-10`, `RN-11`.
- [x] 6.2 **RED (C-11).** Agregar la venta Rayuela ×1 + Bestiario (`libro_id: 5`) ×2 → 409 «Stock insuficiente
  para 'Bestiario'», con la consulta de control antes/después (conteos de `venta`, `renglon_venta`,
  `movimiento_stock` iguales; stock de Rayuela intacto; invariante 0 filas). **Rastrea:** checklist §10 C-11,
  `RN-10`, `RN-11`.
- [x] 6.3 **RED (C-12).** Agregar los tres 409: `cliente_id: 999999999`; `libro_id: 999999999`; libro dado de
  baja (creado y dado de baja en el propio archivo, porque el seed no trae uno). Cada uno con su mensaje
  esperado y la consulta de control de «sin escrituras». **Rastrea:** checklist §10 C-12, `RN-10`, `RN-13`.
- [x] 6.4 **RED (C-16 cuerpo).** Agregar `renglones: []` → 422; `libro_id` repetido → 422; `precio` en el
  cuerpo → 422; `total` → 422; `fecha` → 422; `cantidad: 0` → 422. Sin escrituras en todos. **Rastrea:**
  checklist §10 C-16, §8, `RN-09`, `RN-15`.
- [x] 6.5 **RED (C-15).** Agregar una venta con 4 renglones (1 ejemplar de los libros 1, 2, 3 y 4) → 201,
  dejando anotado su `id` y que se usa para capturar las consultas del detalle junto con la venta 1. **Rastrea:**
  checklist §10 C-15, `CV-02`.
- [x] 6.6 **Corrida.** Ejecutar después del seed y registrar status/cuerpos y las consultas de control. Verificar
  que `GET /ventas/{id}` del C-10 muestra 2 renglones y precios copiados. **Rastrea:** checklist §10
  C-10/11/12/16.

## 7. C-14 — `solo_agregado.sql` y su captura

- [x] 7.1 **RED.** Crear `parcial/test/solo_agregado.sql` con el `UPDATE` y el `DELETE` sobre
  `movimiento_stock` del diseño §8 y un comentario que declare los dos errores esperados
  (`movimiento_stock es de solo agregado: operacion UPDATE no permitida` y `… DELETE no permitida`) y que la
  tabla debe conservar sus 7 filas. **Rastrea:** checklist §10 C-14, `RN-12`.
- [x] 7.2 **Corrida y captura.** Ejecutar `psql -f test/solo_agregado.sql` (sin `ON_ERROR_STOP`, para que se
  vean los dos errores) y guardar la salida completa en `parcial/test/evidencia/c-14_solo_agregado.txt`;
  comprobar con `SELECT count(*) FROM movimiento_stock` que sigue en 7. Verificar con `Select-String` que la
  captura contiene los dos `ERROR`. **Rastrea:** checklist §10 y §12, `RN-12`.

## 8. C-15 — captura de consultas con 2 y 4 renglones

- [x] 8.1 **Preparación.** Con `SQL_ECHO=true`, pedir `GET /ventas/1` dos veces (una para descartar el
  calentamiento del pool) y guardar la segunda. **Rastrea:** checklist §10 C-15, `CV-02`.
- [x] 8.2 **Corrida y conteo.** Pedir `GET /ventas/<id de la venta de 4 renglones>` y guardar la consola en
  `parcial/test/evidencia/c-15_consultas_2y4.txt`, con las marcas de inicio de cada petición y el conteo de
  líneas que comienzan con `SELECT`. Verificar que los dos conteos son iguales y dejarlo escrito en el archivo.
  **Rastrea:** checklist §10 C-15, `CV-02`.

## 9. C-10 — aviso de `BackgroundTasks`

- [x] 9.1 **Servidor normal.** Arrancar `uvicorn main:app` sin configuración extra de logging, registrar una
  venta válida y guardar en `parcial/test/evidencia/c-10-backgroundtasks.txt` la consola con la línea de la
  respuesta y el mensaje `Comprobante de la venta <id> enviado al cliente`. **Rastrea:** checklist §10
  (BackgroundTasks), `RN-09`.
- [x] 9.2 **Verificación de orden.** Comprobar en la captura que el mensaje del comprobante aparece en una
  línea posterior a la de la respuesta `201` y que `asyncio.sleep(0.5)` no bloqueó la respuesta. Si el orden es
  el inverso, marcarlo como defecto y no editar el logging en este change. **Rastrea:** checklist §10, diseño
  §10.

## 10. Integración, registro y cierre

- [x] 10.1 **Barrido de §10.** Recorrer `docs/CHECKLIST_ENTREGA.md` §10 ítem por ítem y completar en
  `EVIDENCIA.md` la fila de cada `C-NN` con archivo, status esperado, método y resultado observado; ningún ítem
  queda sin ubicación. Verificar con `Select-String -Path parcial/test/*.http -Pattern "C-(0[1-9]|1[0-6])"` que
  los dieciséis aparecen. **Rastrea:** checklist §10.
- [x] 10.2 **Cobertura de resultados esperados.** Confirmar que existen bloques para: 422 de C-01 con sesión;
  201 y dos 409 de C-02 sin filas sueltas; 401 de C-03 con `Authorization: Bearer`; C-04 con misma forma y
  duración; 429 + `Retry-After` de C-05; 401/403 y propiedad de C-06; revocación/vencimiento/`/auth/yo` de
  C-07; 409 de C-08; 403 y misma cookie de C-09; totales/stock/movimientos de C-10; 409 y 0 filas de C-11; tres
  409 de C-12; baja/re-alta/venta vieja de C-13; disparador de C-14; conteo de C-15; paginación, inyección y
  PATCH de C-16. Verificar por `Select-String` de los títulos `C-NN` y corregir el que falte. **Rastrea:**
  checklist §10, diseño §1.
- [x] 10.3 **Sin cambios de producción.** Verificar `git status --short` y comprobar que sólo hay archivos bajo
  `parcial/test/` y `openspec/`; `git diff -- parcial/app parcial/main.py parcial/migrations parcial/seed.py
  despliegue` debe salir vacío. **Rastrea:** reglas duras 16-17, diseño (Non-Goals).
- [x] 10.4 **Registro honesto.** Revisar `EVIDENCIA.md`: cada caso tiene método (`REST Client` vs equivalente),
  fecha y entorno; los casos no ejecutados dicen `archivo escrito`; no hay salidas inventadas. Verificar
  leyendo el archivo de punta a punta. **Rastrea:** spec `casos-de-prueba-c`, diseño §11.
- [x] 10.5 **Aceptación.** Correr el barrido de aceptación del change: checklist §10 completo, §1 (`test/` con
  los `.http` y `solo_agregado.sql`) y §12 parcial (existen las capturas de C-14 y C-15, y queda escrito que
  C-19 las consolida en `parcial/evidencia/`). Anotar los ítems que quedan pendientes de la corrida REST Client
  del usuario, sin darlos por cumplidos. **Rastrea:** `CHANGES.md` C-18.

## Workflow follow-up

- Archivar el change con `openspec archive` cuando la aceptación esté revisada y el usuario haya confirmado.
- C-19 consume estas capturas y el mapa caso → archivo para consolidar `parcial/evidencia/` y la suite `tests/`.
