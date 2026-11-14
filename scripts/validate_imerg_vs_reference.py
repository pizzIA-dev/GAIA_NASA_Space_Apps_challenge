"""Validación local: extracción IMERG real (Earth Engine) vs serie histórica v12 del estudio NinoDetect.

Herramienta de desarrollo, NO parte del runtime. Requiere `earthengine authenticate`, EE_PROJECT en .env y la
referencia local extraída en data/_local_reference/. Uso:

    apps/api/.venv/Scripts/python scripts/validate_imerg_vs_reference.py [UBIGEO]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import numpy as np
import pandas as pd

from app.schemas.analysis import AnalysisSpec
from app.services.analyses.runner import RunStore, run_analysis

REF = ROOT / "data" / "_local_reference" / "NinoDetect_Entradas_NASA_Procesadas_v12"


def main(ubigeo: str = "130101") -> int:
    gj = json.loads((REF / "02_Trujillo_8_Distritos.geojson").read_text(encoding="utf-8"))
    geom = next(f["geometry"] for f in gj["features"] if f["properties"]["ubigeo"] == ubigeo)
    spec = AnalysisSpec.model_validate({
        "data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
        "geography": {"custom_geometry": geom},
        "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "month"},
    })
    run = run_analysis(spec, RunStore(ROOT / ".cache"))
    ours = pd.DataFrame(run["series"]).assign(fecha=lambda d: d.time_start_utc).set_index("fecha")["value"]

    ref = pd.read_csv(REF / "03_NASA_Series_Mensuales_Trujillo_Formato_Largo.csv", encoding="utf-8-sig",
                      dtype={"ubigeo": str})
    ref = ref[(ref.ubigeo == ubigeo) & (ref.variable == "precip_mm")].set_index("fecha")["valor"]
    j = pd.concat({"ours": ours, "ref": ref}, axis=1).dropna()
    diff = (j.ours - j.ref).abs()
    print(f"run_id={run['run_id']} cache_hit={run['cache_hit']} meses comparados={len(j)} de {len(ours)}")
    print(f"nulos nuestros={ours.isna().sum()}  corr={np.corrcoef(j.ours, j.ref)[0, 1]:.6f}")
    print(f"|diff| mm: media={diff.mean():.4f} max={diff.max():.4f}  (ref media mensual={j.ref.mean():.2f} mm)")
    s = run["statistics"]
    print(f"Tendencia mensual Theil–Sen: {s['estimate']:.3f} {s['estimate_unit']} "
          f"IC95 [{s['ci_lower']:.3f}, {s['ci_upper']:.3f}] p={s['p_value']:.3g} status={s['status']}")
    print("warnings:", s["warnings"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
