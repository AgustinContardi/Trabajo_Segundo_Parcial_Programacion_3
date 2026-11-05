# Tasks

## 1. Traducción de `IntegrityError`

- [x] 1.1 Crear `parcial/app/core/errors.py` con `traducir_integrity_error(exc)` y el diccionario
      `CONSTRAINTS` (nombre de constraint → `(status_code, mensaje)`), cubriendo las unicidades,
      FKs y CHECKs existentes; verificar que un `IntegrityError` conocido se traduce al código y
      mensaje esperados y que uno desconocido devuelve 409 genérico sin texto de PostgreSQL.
- [x] 1.2 Documentar la convención de mensajes RD-03 (español, segunda persona, sin jerga) en
      `app/core/errors.py` y verificar que ningún mensaje contiene nombres de tablas/columnas.

## 2. Manejador de `RequestValidationError`

- [x] 2.1 Implementar en `app/core/errors.py` (o módulo dedicado) el handler de
      `RequestValidationError` que responde `422` con cuerpo estable y nunca propaga la excepción;
      verificar con un JSON malformado que la respuesta es `422`.
- [x] 2.2 Registrar el handler en `parcial/main.py` y verificar que la app arranca y que un `id`
      no entero en la ruta devuelve `422` sin ejecutar el handler.
- [x] 2.3 Agregar validador de contraseña por bytes (≤ 72) en los schemas que reciben contraseña y
      verificar que 73 bytes devuelven `422` antes de bcrypt.
- [x] 2.4 Agregar validación de carácter NUL en strings y verificar que un string con NUL devuelve
      `422`.

## 3. Paginación conectada a los listados existentes

- [x] 3.1 Conectar `paginar()` en los endpoints de listado existentes (libros, editoriales, géneros,
      autores, clientes, ventas, usuarios/eventos según existan) con `page` (default 1) y `size`
      (default 20, rango 1..100); verificar que un listado válido devuelve el envoltorio canónico.
- [x] 3.2 Verificar que `size = 0` y `size = 101` devuelven `422`.
- [x] 3.3 Verificar que una página fuera de rango devuelve `422` con el mensaje
      «La página 4 no existe: hay 3».
- [x] 3.4 Verificar que cero resultados devuelve `items: []`, `total: 0`, `pages: 1`.
- [x] 3.5 Verificar que `total` se cuenta con los mismos filtros que la página (ej.
      `titulo=ficc&size=1` → `total 1`, `pages 1`, y `page=2` da `422`).

## 4. Base de schemas por módulo

- [x] 4.1 Establecer en cada módulo existente (`editoriales`, `generos`, `autores`, `libros`,
      `clientes`, `ventas`, `usuarios`) los schemas `Create`, `Update` y `Read` con
      `extra="forbid"`; verificar que un campo extra devuelve `422`.
- [x] 4.2 Aplicar `exclude_unset` en los PATCH y verificar que sólo los campos enviados se modifican.
- [x] 4.3 Verificar que ningún schema incluye `password_hash`.

## 5. Orden de resolución de errores en los servicios

- [x] 5.1 Documentar en cada servicio existente el orden `404 → 403 → 409 → 422` (comentario de
      contrato) y verificar con un caso combinado que se devuelve el primer código aplicable.

## 6. Verificación integrada

- [x] 6.1 Correr `grep -rn "create_all" parcial/` y verificar que queda vacío.
- [x] 6.2 Levantar la app y correr los casos del checklist §9 (envoltorio, page/size, página
      inexistente, total con los mismos filtros, ningún texto interno, ninguna entrada inválida en
      500, búsqueda con parámetros ligados, `extra="forbid"`/`exclude_unset` y códigos).
- [x] 6.3 Verificar §0: ninguna respuesta incluye `password_hash`.

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
- Verify the archived result.