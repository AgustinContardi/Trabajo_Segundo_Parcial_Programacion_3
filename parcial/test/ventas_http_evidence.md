# Evidencia de ejecución — `parcial/test/ventas.http`

- **Change:** `c-16-fix-venta-transaccional` (tarea 5.2).
- **Fecha:** 2026-11-07.
- **Entorno:** PostgreSQL 17.11 local (`127.0.0.1:5432`, db `libreria`),
  `uvicorn main:app --port 8016` desde `parcial/`.
- **Método:** el entorno es headless y no permite la UI de REST Client. Se
  ejecutaron las **mismas peticiones** del `.http` con `httpx` contra el
  servidor real, conservando la cookie `access_token`. Los bloques del `.http`
  siguen siendo el formato de revisión manual; este archivo registra la
  ejecución equivalente y sus consultas de control.
- **Datos:** creados por un bootstrap temporal (fuera del repo) con stock
  sembrado por `LibroRepository.aplicar_movimiento(..., "Stock inicial", ...)`
  (RN-11). Los ids son de esta corrida.

## Datos de la corrida

| Recurso | Id | Stock inicial |
|---|---|---|
| Cliente | 359 | — |
| Rayuela (C-10) | 461 | 3 |
| Bestiario (C-10) | 462 | 1 |
| No barra (C-10) | 463 | 2 |
| Rayuela C-11 | 464 | 3 |
| Bestiario C-11 | 465 | 1 |
| Duplicado | 466 | 3 |
| Libro de baja | 467 | 2 (`borrado_en` no nulo) |

Usuario: `c16-fix-vendedor@example.com` con rol `VENDEDOR` vigente.

## Resultados HTTP

| Caso | Petición | Status | Cuerpo observado |
|---|---|---|---|
| Login | `POST /auth/login` | **200** | `{"mensaje":"Sesión iniciada","debe_cambiar_password":false,"expira_en_segundos":1800}` + `Set-Cookie: access_token=...; HttpOnly` |
| C-10 alta válida (2 renglones) | `POST /ventas/` | **201** | `{"id":99,...,"total":"69000.00","renglones":[{"libro_id":461,"cantidad":1,"precio_unitario":"45000.00","subtotal":"45000.00"},{"libro_id":462,"cantidad":1,"precio_unitario":"24000.00","subtotal":"24000.00"}]}` |
| C-10 sin barra final | `POST /ventas` | **201** | `{"id":100,...,"total":"10000.00","renglones":[{"libro_id":463,"cantidad":1,"precio_unitario":"10000.00",...}]}` — sin `307` ni `Location` |
| C-11 stock insuficiente | `POST /ventas/` | **409** | `{"detail":"Stock insuficiente para 'Bestiario C-11'"}` |
| C-12 cliente inexistente | `POST /ventas/` | **409** | `{"detail":"El cliente indicado no existe"}` |
| C-12 libro inexistente | `POST /ventas/` | **409** | `{"detail":"Uno o más libros indicados no existen"}` |
| C-12 libro dado de baja | `POST /ventas/` | **409** | `{"detail":"El libro 'Libro de baja' está dado de baja"}` |
| Duplicado + cliente inexistente | `POST /ventas/` | **409** | `{"detail":"El cliente indicado no existe"}` (el 409 gana al 422) |
| Duplicado válido | `POST /ventas/` | **422** | `{"detail":"No se puede incluir el mismo libro dos veces en una venta"}` |
| ID fuera de rango | `POST /ventas/` | **422** | `{"detail":[{"loc":["body","cliente_id"],"msg":"El valor supera el máximo permitido","type":"less_than_equal"}]}` |
| Cantidad booleana | `POST /ventas/` | **422** | `{"detail":[{"loc":["body","renglones",0,"cantidad"],"msg":"Debe ser un número entero válido","type":"int_type"}]}` |
| Cantidad fuera de rango | `POST /ventas/` | **422** | `{"detail":[{"loc":["body","renglones",0,"cantidad"],"msg":"El valor supera el máximo permitido","type":"less_than_equal"}]}` |
| Campo extra `precio` | `POST /ventas/` | **422** | `{"detail":[{"loc":["body","precio"],"msg":"El campo no está permitido","type":"extra_forbidden"}]}` |

Ninguna respuesta contiene nombres de tablas, columnas, constraints ni trazas
de PostgreSQL.

## Consultas de control

Antes de la corrida:

```
 ventas | renglones | movimientos
--------+-----------+-------------
     42 |        54 |         272

 id  | stock          (libros 461..467)
-----+-------
 461 |     3
 462 |     1
 463 |     2
 464 |     3
 465 |     1
 466 |     3
 467 |     2

invariante → 0 filas
```

Después de la corrida:

```
 ventas | renglones | movimientos
--------+-----------+-------------
     44 |        57 |         275

 id  | stock
-----+-------
 461 |     2      (3 - 1 vendido)
 462 |     0      (1 - 1 vendido)
 463 |     1      (2 - 1 vendido)
 464 |     3      (C-11 no escribió)
 465 |     1      (C-11 no escribió)
 466 |     3      (422 no escribió)
 467 |     2      (409 no escribió)

invariante global → 0 filas
```

- El crecimiento de `venta` (+2), `renglon_venta` (+3) y `movimiento_stock`
  (+3) corresponde **sólo** a las dos altas 201. Ningún 409/422 escribió.
- La venta 99 quedó con `total = 69000.00`; sus renglones copiaron
  `45000.00` y `24000.00`; sus movimientos son negativos, `motivo = 'Venta'`,
  con `usuario_id` del vendedor y `venta_id` de la venta.
- `GET /ventas/100` (no ejecutado aquí) no aplica; el detalle se cubre en los
  tests de integración.

## `BackgroundTasks`

La consola de uvicorn mostró, **después** de las respuestas:

```
Comprobante de la venta 99 enviado al cliente
Comprobante de la venta 100 enviado al cliente
```

## Cobertura equivalente en tests automáticos

Los mismos comportamientos están cubiertos por
`tests/test_ventas_api.py`, `tests/test_ventas_crear_api.py`,
`tests/test_ventas_crear_service.py`, `tests/test_ventas_service.py`,
`tests/test_ventas_errores_datos.py` y `tests/test_errors_validation.py`.
