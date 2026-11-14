from fastapi import FastAPI

from app.core.config import settings
from app.services.statistics.trend_core import ALGORITHM_VERSION, COMPATIBILITY

app = FastAPI(
    title="Earth Trend Studio API (nombre provisional)",
    version="0.1.0",
    description="API científica de tendencias del sistema terrestre. Mismo motor para web, REST y SDK Python.",
)


@app.get("/api/v1/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "algorithm_version": ALGORITHM_VERSION,
        "earth_engine_configured": settings.ee_project is not None,
    }


@app.get("/api/v1/catalog/capabilities", tags=["catalog"])
def capabilities() -> dict:
    """Métodos estadísticos disponibles y sus combinaciones válidas (la UI y el SDK los descubren aquí)."""
    return {
        "estimators": COMPATIBILITY,
        "confidence_levels": [0.90, 0.95, 0.99],
        "granularities": ["month", "year"],
        "datasets": [],  # F2: registro de adaptadores GEE
    }
