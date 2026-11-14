import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Configuración por entorno. Nunca valores secretos por defecto."""

    ee_project: str | None = os.getenv("EE_PROJECT") or None
    ee_service_account_file: str | None = os.getenv("EE_SERVICE_ACCOUNT_FILE") or None
    cache_dir: str = os.getenv("CACHE_DIR", ".cache")


settings = Settings()
