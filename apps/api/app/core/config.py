import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_dotenv(path: Path) -> None:
    """Carga mínima de .env (sin dependencias). No sobrescribe variables ya definidas."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name) or default


@dataclass(frozen=True)
class Settings:
    """Configuración por entorno. Nunca valores secretos por defecto."""

    ee_project: str | None = field(default_factory=lambda: _env("EE_PROJECT"))
    ee_service_account_file: str | None = field(default_factory=lambda: _env("EE_SERVICE_ACCOUNT_FILE"))
    ee_service_account_email: str | None = field(default_factory=lambda: _env("EE_SERVICE_ACCOUNT_EMAIL"))
    cache_dir: Path = field(default_factory=lambda: REPO_ROOT / (_env("CACHE_DIR", ".cache") or ".cache"))
    max_roi_area_km2: float = float(_env("MAX_ROI_AREA_KM2", "2000000") or 2e6)


settings = Settings()
