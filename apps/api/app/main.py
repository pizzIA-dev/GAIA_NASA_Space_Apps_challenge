from fastapi import FastAPI

from app.api.v1.routes import router
from app.core.config import settings
from app.services.earth_engine.adapters import ADAPTERS
from app.services.earth_engine.client import auth_mode
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
        "earth_engine_auth_mode": auth_mode()
        or ("service_account" if settings.ee_service_account_file else "user") + " (no inicializado)",
    }


@app.get("/api/v1/catalog/capabilities", tags=["catalog"])
def capabilities() -> dict:
    """Métodos estadísticos disponibles y sus combinaciones válidas (la UI y el SDK los descubren aquí)."""
    return {
        "estimators": COMPATIBILITY,
        "confidence_levels": [0.90, 0.95, 0.99],
        "granularities": ["month", "year"],
        "datasets": sorted(ADAPTERS),
        "seasonality": ["none", "monthly_anomaly"],
        "temporal_aggregations": ["total", "mean"],
    }


app.include_router(router)
