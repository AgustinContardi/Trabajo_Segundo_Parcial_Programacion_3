# Imagen del TP capítulos 1 a 4 («la librería») — C-20.
#
# Contrato (change c-20-imagen-docker-tp-cap1a4, spec `imagen-contenedor`):
# base Alpine por debajo de 100 MB, dependencias antes que el código, proceso
# sin privilegios, sin secretos horneados, migraciones al arrancar, escucha en
# 0.0.0.0 y HEALTHCHECK contra /health/ready usando 127.0.0.1.
#
# El contexto de build es `despliegue/`, NO la raíz del repo:
#
#     cd despliegue
#     docker build -t libreria:local .
#
# La configuración llega sólo en tiempo de ejecución (--env-file). Este archivo
# no declara variables de base, ni ARG, ni cadenas de conexión.
#
# Esta imagen NO se reutiliza para `parcial/` (DD-15): es el TP tal como se
# entregó más los artefactos de despliegue.

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Dependencias primero: la capa se cachea mientras no cambie requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Código después: un cambio de código no reinstala dependencias.
COPY . .

# 3) Usuario sin privilegios. El chown va después del COPY porque los archivos
#    copiados pertenecen a root y `app` no podría escribir lo que necesite.
RUN addgroup -S app && adduser -S -G app app && chown -R app:app /app
USER app

EXPOSE 8000

# 4) Migraciones y arranque. `main:app`, NO `app.main:app`: el entrypoint del TP
#    es `despliegue/main.py` y `app/` no tiene `main.py`. Si la base no responde
#    o falta configuración obligatoria, esto falla y el contenedor muere.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]

# 5) Salud desde dentro del contenedor. `wget` viene en Alpine; `curl` NO.
#    Se usa 127.0.0.1 literal: el nombre de host local resuelve primero a ::1 y
#    uvicorn con --host 0.0.0.0 escucha sólo IPv4, así que el contenedor
#    quedaría `unhealthy` aunque responda desde afuera. El start-period cubre
#    el `alembic upgrade head` inicial contra la base.
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8000/health/ready || exit 1
