"""Tendencia NASA con HTTP puro (sin SDK), plan §12A.5.

Variables de entorno: EARTH_TREND_API_URL (p. ej. http://localhost:8000/api/v1) y EARTH_TREND_API_TOKEN (opcional
mientras la API local no exige autenticación). No requiere Earth Engine ni archivos de estudios anteriores.
"""

import os
import time

import requests

BASE = os.environ.get("EARTH_TREND_API_URL", "http://localhost:8000/api/v1").rstrip("/")
HEADERS = {"Authorization": f"Bearer {os.environ['EARTH_TREND_API_TOKEN']}"} if os.environ.get(
    "EARTH_TREND_API_TOKEN") else {}


def call(method: str, path: str, **kw):
    for attempt in range(4):
        r = requests.request(method, f"{BASE}/{path}", headers={**HEADERS, **kw.pop("headers", {})}, timeout=600, **kw)
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(float(r.headers.get("Retry-After", 2 ** attempt)))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text}")
        return r.json()
    raise RuntimeError("Reintentos agotados")


geo = call("GET", "geographies/search", params={"q": "trujillo", "country": "PER", "level": "ADM2"})["items"][0]
print("Territorio:", geo["geo_id"], " > ".join(geo["path"] + [geo["name"]]), f"{geo['area_km2']} km²")

spec = {
    "data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
    "geography": {"geo_ids": [geo["geo_id"]]},
    "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year",
             "temporal_aggregation": "total"},
    "statistics": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                   "significance_test": "mann_kendall"},
}
run = call("POST", "analyses", json=spec, headers={"Idempotency-Key": "ejemplo-requests-001"})
while run["status"] not in {"succeeded", "failed", "cancelled"}:
    time.sleep(3)
    run = call("GET", f"analyses/{run['run_id']}")

st = call("GET", f"analyses/{run['run_id']}/statistics")
print(f"run_id={run['run_id']}  estado={st['status']}")
print(f"Pendiente {st['estimator']}: {st['estimate']:.2f} {st['estimate_unit']}  "
      f"IC{st['confidence_level']:.0%} [{st['ci_lower']:.2f}, {st['ci_upper']:.2f}]  p={st['p_value']:.3f}")
for w in st["warnings"]:
    print("  aviso:", w)
