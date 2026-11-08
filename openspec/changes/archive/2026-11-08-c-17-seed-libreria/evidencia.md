# Evidencia — C-17 seed-libreria

Fecha: 2026-11-08. Base local: PostgreSQL 17, `127.0.0.1:5432`, base `libreria_parcial`
(creada desde cero; no se tocó `libreria_db`, que conserva el esquema heredado del TP cap. 1-4).

| Paso | Comando | Resultado |
|---|---|---|
| Línea base (1.1) | `python -m pytest tests -q` (base recién migrada) | **459 passed, 1 skipped** — 417 pruebas preexistentes + 42 nuevas de `test_seed_datos.py`; el skip es el E2E |
| Migraciones | `alembic upgrade head` (desde base vacía) | `0001 → 0002 → dd4a0e5e9cf7 → c8d2dea5529f`, 15 tablas |
| Seed, corrida 1 | `python seed.py` | exit `0`, conteos completos |
| Seed, corrida 2 | `python seed.py` | exit `0`, mismos conteos e ids |
| E2E (4.4) | `$env:SEED_E2E=1; pytest tests/test_seed_ejecucion.py -q` | **1 passed in 8.15s** (dos corridas reales dentro del test) |
| No regresión sobre base sembrada (4.5) | `python -m pytest tests -q` | **459 passed, 1 skipped** — se aisló `test_admin_roles_concurrencia.py` para que el seed no rompa su precondición (ver nota) |
| State final tras la suite | `python seed.py` | exit `0`; la base vuelve al estado del seed (`5 usuarios`, stocks `10/5/8/3/1`, venta 1 `69000.00`, 7 movimientos) |

## Salida de `python seed.py` (idéntica en ambas corridas)

```
Seed sobre 127.0.0.1:5432/libreria_parcial — la base se vacía antes de cargar.
Seed OK. Conteos verificados:
  usuario: 5
  asignacion_rol: 5
  editorial: 3
  genero: 3
  autor: 6
  libro: 5
  cliente: 3
  perfil_cliente: 1
  venta: 1
  renglon_venta: 2
  movimiento_stock: 7
  evento_seguridad: 1
  venta 1: total 69000.00
```

## §8 — `SELECT` literales del checklist

### Usuarios y roles

```
        email         |   rol    | revocada_en | vence_en
----------------------+----------+-------------+----------
 admin@example.com    | ADMIN    |             |
 admin2@example.com   | ADMIN    |             |
 vendedor@example.com | VENDEDOR |             |
 ana@example.com      | CLIENTE  |             |
 nuevo@example.com    | VENDEDOR |             |
(5 rows)
```

### `titulo, stock`

```
 id |                titulo                 | stock |  precio
----+---------------------------------------+-------+----------
  1 | Rayuela                               |    10 | 25000.00
  2 | Antología de la literatura fantástica |     5 | 30000.00
  3 | Ficciones                             |     8 | 22000.00
  4 | Respiración artificial                |     3 | 27000.00
  5 | Bestiario                             |     1 | 18000.00
(5 rows)
```

### Clientes

```
 id |     nombre      | usuario_id
----+-----------------+------------
  1 | Lucía Fernández |
  2 | Tomás Ríos      |
  3 | Ana Paz         |          4
(3 rows)
```

### Venta 1 y renglones

```
 id |  total
----+----------
  1 | 69000.00
(1 row)

 venta_id | libro_id | cantidad | precio_unitario
----------+----------+----------+-----------------
        1 |        1 |        1 |        25000.00
        1 |        3 |        2 |        22000.00
(2 rows)
```

### Movimientos de stock

```
 libro_id | cantidad |    motivo     | usuario_id | venta_id
----------+----------+---------------+------------+----------
        1 |       11 | Stock inicial |          1 |
        1 |       -1 | Venta         |          3 |        1
        2 |        5 | Stock inicial |          1 |
        3 |       10 | Stock inicial |          1 |
        3 |       -2 | Venta         |          3 |        1
        4 |        3 | Stock inicial |          1 |
        5 |        1 | Stock inicial |          1 |
(7 rows)
```

### Evento de seguridad

```
  actor  |            accion
---------+------------------------------
 SISTEMA | Carga de los datos iniciales
(1 row)
```

### Invariante de §4 (debe dar 0 filas)

```
 id
----
(0 rows)
```

## Nota sobre el test de concurrencia de C-15

`tests/test_admin_roles_concurrencia.py` hacía `assert base == 0` sobre
`contar_admins_vigentes()` porque necesita que sus dos administradores de prueba sean «los
últimos». El seed deja dos `ADMIN` vigentes (requisito del PDF), así que la precondición dejaba
de cumplirse y la suite fallaba **sólo con el seed cargado**.

Solución aplicada: el test cierra temporalmente por SQL las asignaciones `ADMIN` vigentes antes
del escenario (sin pasar por el servicio, que rechazaría dejar cero administradores) y las
restaura en `finally`. Conserva exactamente su semántica (`[200, 409]`, queda un admin vigente) y
deja la base como estaba; verificado tras la corrida: `2` administradores vigentes, los del seed.
