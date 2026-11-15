from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.routes import Problem, problem_response, router
from app.core.config import settings
from app.services.earth_engine.adapters import ADAPTERS
from app.services.earth_engine.client import auth_mode
from app.services.statistics.trend_core import ALGORITHM_VERSION, COMPATIBILITY

app = FastAPI(
    title="GaIA API",
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


# Compresión: las geometrías (≈ 1,1 MB → ≈ 0,3 MB) y series cuentan contra la salida de datos del alojamiento gratuito.
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["Retry-After"],
)
app.include_router(router)


@app.exception_handler(Problem)
async def _problem_handler(request: Request, exc: Problem):
    return problem_response(request, exc)
