"""Sondas de salud — único archivo del módulo `health`.

- `GET /health/live` no toca la base: confirma que el proceso responde.
- `GET /health/ready` ejecuta `SELECT 1`; si la base no contesta responde 503
  con un cuerpo fijo y sin filtrar el texto del driver, la URL ni la traza.

El proceso puede estar **vivo** y no estar **listo**; reiniciarlo no arregla una
base caída. Esa distinción es la que usa el `HEALTHCHECK` de la imagen (`C-20`).
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

logger = logging.getLogger("libreria.health")

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Proceso vivo: no consulta la base de datos."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Base disponible: `SELECT 1`; 503 genérico si no contesta."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        # La causa queda en el log del servidor; al cliente sólo le llega el
        # cuerpo fijo, sin texto del driver, URL ni traza.
        logger.warning("Sonda de disponibilidad fallida: la base no responde")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok"})
