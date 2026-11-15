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

    # Acceso y límites (plan §12.3 / §12A.2). AUTH_MODE: "optional" = anónimo con cupo ligero; "required" = todo
    # POST /analyses exige token.
    auth_mode: str = field(default_factory=lambda: _env("AUTH_MODE", "optional") or "optional")
    api_keys_file: Path = field(default_factory=lambda: Path(
        _env("API_KEYS_FILE") or REPO_ROOT / (_env("CACHE_DIR", ".cache") or ".cache") / "security" / "api_keys.json"))
    light_max_images: int = int(_env("LIGHT_MAX_IMAGES", "50000") or 50000)
    light_max_pixel_images: float = float(_env("LIGHT_MAX_PIXEL_IMAGES", "5e7") or 5e7)
    heavy_max_images: int = int(_env("HEAVY_MAX_IMAGES", "600000") or 600000)
    heavy_max_pixel_images: float = float(_env("HEAVY_MAX_PIXEL_IMAGES", "3e9") or 3e9)
    anon_extractions_per_hour: int = int(_env("ANON_EXTRACTIONS_PER_HOUR", "20") or 20)
    key_extractions_per_hour: int = int(_env("KEY_EXTRACTIONS_PER_HOUR", "200") or 200)
    max_concurrent_extractions: int = int(_env("MAX_CONCURRENT_EXTRACTIONS", "2") or 2)


settings = Settings()
