"""Configuración de la aplicación — `Settings` (pydantic-settings).

Contrato de este módulo:

- Las variables de `CV-09` se leen del entorno. `POSTGRES_PASSWORD` es
  `SecretStr` **sin valor por defecto**: si falta, la aplicación no arranca
  (fail-fast) y el error no imprime el secreto.
- La dirección de la base **no** es una variable: se deriva con
  `sqlalchemy.engine.URL.create`, nunca con una f-string, para que `@`, `:` y
  `%` en usuario o contraseña se escapen correctamente.
- `get_settings()` está cacheado con `lru_cache` y se llama **sólo** desde el
  `lifespan` de `main.py` y desde `migrations/env.py`. Nada de configuración se
  evalúa al importar: importar el paquete no debe exigir un entorno completo.
Los secretos no tienen default y no se registran en logs.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Ruta absoluta al `.env` de este proyecto (`despliegue/`), derivada de este
# archivo, para que funcione tanto si uvicorn se lanza desde `despliegue/` como
# si los tests corren desde la raíz del repo.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Configuración obligatoria de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    POOL_SIZE: int = 5
    SQL_ECHO: bool = False

    @computed_field(repr=False)  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """URL de conexión derivada, con driver asincrónico.

        `URL.create` escapa usuario y contraseña; `render_as_string` con
        `hide_password=False` es necesario porque la URL se entrega al motor
        (no se muestra en logs ni en respuestas). `repr=False` evita que la
        contraseña aparezca al imprimir `Settings`.
        """
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada.

    Se llama **sólo** desde el `lifespan` de `main.py` y desde
    `migrations/env.py`; nunca al importar un módulo.
    """
    return Settings()
