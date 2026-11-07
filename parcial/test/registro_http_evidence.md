# Evidencia de ejecución — `parcial/test/registro.http` (caso `C-02`)

- **Change:** `c-12-auto-registro-atomico` (tarea 6.2).
- **Fecha:** 2026-11-07.
- **Entorno:** PostgreSQL 17.11 local (`127.0.0.1:5432`, db `libreria`),
  `python -m uvicorn main:app --host 127.0.0.1 --port 8000` desde `parcial/`.
- **Método:** el entorno es headless y no permite la UI de REST Client. Se
  ejecutaron las **mismas peticiones y cuerpos** de `registro.http` con
  `httpx` contra el servidor real, y las mismas consultas de control con
  `asyncpg`. El `.http` sigue siendo el formato de revisión manual; este
  archivo registra la ejecución equivalente.
- **Datos:** sufijo único `20261107183720`; los ids son de esta corrida.

## Resultados HTTP

| Caso | Petición | Status | Cuerpo observado |
|---|---|---|---|
| C-02.1 alta válida | `POST /auth/registro` | **201** | `{"id":2123,"email":"c02-alta-20261107183720@example.com","nombre":"Ana Pérez","activo":true,"debe_cambiar_password":false}`; `Set-Cookie: []` |
| C-02.2 email ya usado como usuario | `POST /auth/registro` | **409** | `{"detail":"Ya existe un usuario con ese email"}` |
| C-02.3 email ya usado como cliente (ficha sembrada) | `POST /auth/registro` | **409** | `{"detail":"Ya existe un cliente con ese email"}` |
| C-02.4 campo `rol` | `POST /auth/registro` | **422** | `{"detail":[{"loc":["body","rol"],"msg":"El campo no está permitido","type":"extra_forbidden"}]}` |
| C-02.5 contraseña de 73 bytes | `POST /auth/registro` | **422** | `{"detail":[{"loc":["body","password"],"msg":"Los datos enviados no son válidos","type":"value_error"}]}` |
| C-02.6 40 «ñ» (80 bytes) | `POST /auth/registro` | **422** | `{"detail":[{"loc":["body","password"],"msg":"Los datos enviados no son válidos","type":"value_error"}]}` |
| C-02.7 contraseña de exactamente 72 bytes | `POST /auth/registro` | **201** | `{"id":2126,"email":"c02-72bytes-20261107183720@example.com","nombre":"Límite Setenta y Dos","activo":true,"debe_cambiar_password":false}` |

El `201` devuelve exactamente `id`, `email`, `nombre`, `activo` y
`debe_cambiar_password`: no aparece `password_hash` ni la contraseña en claro,
y no se emite cookie. Ningún `409`/`422` contiene nombres de tablas, columnas,
constraints ni trazas de PostgreSQL.

## Consultas de control

Antes de la corrida:

```
usuario=138  asignacion_rol=137  cliente=133
```

Verificación del alta C-02.1:

```
email            = c02-alta-20261107183720@example.com
hash_es_bcrypt   = true
rol              = CLIENTE
vence_en         = NULL
revocada_en      = NULL
cliente_ligada   = true        (cliente.usuario_id = usuario.id)
```

Tras sembrar la ficha de C-02.3 (`INSERT INTO cliente (nombre, email)`):

```
usuario=139  asignacion_rol=138  cliente=135
```

La ficha sembrada quedó intacta tras el `409`:

```
nombre     = Ficha ajena
email      = c02-ficha-20261107183720@example.com
usuario_id = NULL
```

Después de C-02.7:

```
usuario=140  asignacion_rol=139  cliente=136
delta desde el inicio = (+2, +2, +3)
```

- Sólo las dos altas `201` escribieron: `usuario` +2, `asignacion_rol` +2,
  `cliente` +2 nuevas.
- El `cliente` +3 incluye la ficha sembrada para C-02.3; los `409` y `422` no
  agregaron filas.
- Limpieza C-02.8 (`DELETE` de `asignacion_rol` → `cliente` → `usuario` por
  email `c02-%`): los tres counts vuelven a `138 / 137 / 133`.

## Cobertura equivalente en tests automáticos

Los mismos comportamientos están cubiertos con PostgreSQL real por
`tests/test_registro_api_db.py` (10 pruebas) y con dobles por
`tests/test_registro_api.py`, `tests/test_registro_service.py`,
`tests/test_registro_schemas.py`, `tests/test_registro_unit_of_work.py` y
`tests/test_registro_hash.py`.
