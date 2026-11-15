"""Datos REALES para las propuestas visuales de F1 (plan §5.5): provincia de Trujillo y sus distritos (IGN),
NASA IMERG V07 2003–2024, calculados con el mismo motor que la API. Salida: docs/ux/prototypes/data.json.

Uso:  apps/api/.venv/Scripts/python scripts/build_ux_prototype_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.schemas.analysis import AnalysisSpec
from app.services.analyses.runner import AnalysisError, run_analysis
from app.services.geographies.registry import registry

PROVINCE = "pe-ign2020:1301"
OUT = ROOT / "docs" / "ux" / "prototypes" / "data.json"
IMERG = {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"}
PERIOD = {"start": "2003-01-01", "end_exclusive": "2025-01-01"}
SEN = {"estimator": "theil_sen", "interval_method": "theil_sen_analytic", "significance_test": "mann_kendall"}


def run(geo_id: str, granularity: str, extra: dict | None = None) -> dict:
    spec = AnalysisSpec.model_validate({"data": IMERG, "geography": {"geo_ids": [geo_id]},
                                        "time": PERIOD | {"granularity": granularity}, "statistics": SEN} | (extra or {}))
    return run_analysis(spec)


def compact_stats(s: dict) -> dict:
    keys = ("status", "estimator", "estimate", "estimate_unit", "ci_lower", "ci_upper", "confidence_level", "ci_method",
            "p_value", "test_method", "n_observations", "n_missing", "coverage_fraction", "warnings", "intercept")
    return {k: s.get(k) for k in keys}


def main() -> int:
    prov = registry.get(PROVINCE)
    annual = run(PROVINCE, "year")
    annual_ols = run(PROVINCE, "year", {"statistics": {"estimator": "ols", "interval_method": "hac_newey_west",
                                                       "significance_test": "ols_hac_t"}})
    monthly = run(PROVINCE, "month")
    anomaly = run(PROVINCE, "month", {"transforms": {"seasonality": "monthly_anomaly"}})
    districts = []
    for d in sorted(registry.children(prov), key=lambda g: g.name):
        try:
            r = run(d.geo_id, "year")
            st, run_id, err, series = compact_stats(r["statistics"]), r["run_id"], None, r["series"]
        except AnalysisError as e:
            st, run_id, err, series = None, None, {"status": e.status, "code": e.code, "detail": e.detail}, []
        districts.append({"geo_id": d.geo_id, "ubigeo": d.geo_id.split(":")[1], "name": d.name, "area_km2": d.area_km2,
                          "geometry": registry.geometry_geojson(d.geo_id), "run_id": run_id, "statistics": st, "series": series,
                          "error": err})
        print(f"{d.name:24} {d.area_km2:>8} km²  {st['estimate'] if st else err['code']}")
    data = {
        "_aviso": "Datos NASA reales (IMERG V07 vía Google Earth Engine) calculados con el motor de la plataforma. "
                  "Uso: propuestas visuales F1. Cada bloque incluye su run_id para reproducirlo por API.",
        "dataset": annual["source_versions"][0],
        "province": {"geo_id": prov.geo_id, "name": prov.name, "path": ["Perú", "La Libertad"],
                     "area_km2": prov.area_km2, "attribution": registry.attribution(prov.boundary_set_id),
                     "geometry": registry.geometry_geojson(prov.geo_id)},
        "annual": {"run_id": annual["run_id"], "series": annual["series"], "statistics": compact_stats(annual["statistics"])},
        "annual_ols": {"run_id": annual_ols["run_id"], "statistics": compact_stats(annual_ols["statistics"])},
        "monthly": {"run_id": monthly["run_id"], "series": monthly["series"]},
        "anomaly": {"run_id": anomaly["run_id"], "series": anomaly["series"],
                    "statistics": compact_stats(anomaly["statistics"])},
        "districts": districts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"OK → {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
