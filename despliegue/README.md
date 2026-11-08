# Parcial «la librería» — TP capítulos 1 a 4

API para la gestión de una librería: catálogo, clientes y ventas.
Este directorio es el proyecto que se entrega en el repositorio; el TP de los
capítulos 1 a 4 se adopta como base y se conserva sin reescribir su lógica.

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

Todos los comandos se corren **dentro de `despliegue/`**.

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

   Editar `.env` con el usuario, la contraseña, la base, el host y el puerto
   de PostgreSQL.

4. Aplicar las migraciones sobre la base vacía:

   ```powershell
   alembic upgrade head
   ```

5. Levantar la API:

   ```powershell
   uvicorn main:app --reload
   ```

6. Comprobar la salud:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/health/live
   Invoke-RestMethod http://127.0.0.1:8000/health/ready
   ```
