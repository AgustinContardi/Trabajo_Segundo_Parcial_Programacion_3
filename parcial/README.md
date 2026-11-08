# Parcial «la librería» — capítulos 1 a 6

API para la gestión de una librería: catálogo, clientes, ventas, stock y acceso
con roles. Este directorio es el proyecto que se entrega en el repositorio; el
TP de los capítulos 1 a 4 se adopta como base y se conserva sin reescribir su
lógica.

## Integrantes

Grupo **AURA**

- Enzo Giaquinta
- Agustin Contardi
- Fernando Torrez
- Ramiro Salcedo
- Ignacio Sanchez

## Requisitos

- Python 3.12
- PostgreSQL 16 accesible (la base puede estar vacía: el esquema se crea con
  Alembic, nunca con `create_all`)
- `pip` del entorno virtual

## Puesta en marcha desde cero

Todos los comandos se corren **dentro de `parcial/`**.

1. Crear y activar el entorno virtual:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instalar las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Crear el `.env` a partir del ejemplo y completar los valores:

   ```powershell
   Copy-Item env.example .env
   ```

   Editar `.env` con el usuario, la contraseña, la base, el host y el puerto de
   PostgreSQL. Generar una clave de firma propia, por ejemplo:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   y pegarla en `JWT_SECRET`. El `.env` **no** se versiona.

4. Aplicar las migraciones sobre la base vacía:

   ```powershell
   alembic upgrade head
   ```

   El historial tiene **cinco** versiones encadenadas, en este orden:
   `0001` (baseline del TP), `0002` (género), `0003` (acceso y stock),
   `0004` (sólo agregado de `movimiento_stock`) y
   `<revision>_0005_now_server_defaults.py` (defaults `now()` reales). El
   nombre de cada archivo conserva el prefijo ordinal además del hash de
   Alembic; `alembic current` debe mostrar la revisión de 0005 como `(head)`
   y `alembic check` no debe detectar diferencias.

5. Cargar los datos iniciales (la semilla **vacía la base** antes de cargar los
   datos: no correrla sobre una base con información que se quiera conservar):

   ```powershell
   python seed.py
   ```
   La semilla deja siempre el mismo estado: libros 1–5, venta 1 y un stock
   coherente con sus movimientos. No toca `alembic_version`.

6. Levantar la API:

   ```powershell
   uvicorn main:app --reload
   ```

7. Comprobar la salud:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/health/live
   Invoke-RestMethod http://127.0.0.1:8000/health/ready
   ```
