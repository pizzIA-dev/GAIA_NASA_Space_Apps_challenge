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
    # «Ligero» = permitido sin token. Desde 2026-11-15 cubre los 5 productos para 2001–2024 en territorios de hasta
    # ~400 000 km² (MERRA-2 horario 24 años ≈ 210 000 imágenes; NDVI 500 m de un país mediano ≈ 6e8 píxel-imágenes):
    # la primera consulta puede tardar 1–3 min y luego queda en caché para todos. Protecciones que se mantienen:
    # cupo por persona/hora, extracciones simultáneas limitadas y área máxima.
    light_max_images: int = int(_env("LIGHT_MAX_IMAGES", "250000") or 250000)
    light_max_pixel_images: float = float(_env("LIGHT_MAX_PIXEL_IMAGES", "1e9") or 1e9)
    heavy_max_images: int = int(_env("HEAVY_MAX_IMAGES", "600000") or 600000)
    heavy_max_pixel_images: float = float(_env("HEAVY_MAX_PIXEL_IMAGES", "3e9") or 3e9)
    anon_extractions_per_hour: int = int(_env("ANON_EXTRACTIONS_PER_HOUR", "20") or 20)
    key_extractions_per_hour: int = int(_env("KEY_EXTRACTIONS_PER_HOUR", "200") or 200)
    max_concurrent_extractions: int = int(_env("MAX_CONCURRENT_EXTRACTIONS", "4") or 4)
    extraction_wait_s: float = float(_env("EXTRACTION_WAIT_S", "30") or 30)
    # Casos de estudio locales (endpoints /cases): desactivados por defecto; la plataforma es general.
    enable_case_studies: bool = (_env("ENABLE_CASE_STUDIES", "false") or "false").lower() in ("1", "true", "yes")
    atlas_parallel_extractions: int = int(_env("ATLAS_PARALLEL_EXTRACTIONS", "6") or 6)
    # Orígenes web permitidos (CORS estricto, plan §12A.2). Los notebooks no dependen de CORS.
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in (_env("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000") or "").split(",")
        if o.strip()))


settings = Settings()
