"""Validación local de los adaptadores GLDAS / MERRA-2 / MODIS NDVI / SST contra la serie v12 del estudio previo.

Herramienta de desarrollo, no runtime. Usa las mismas geometrías del estudio (data/_local_reference) para comparar
manzanas con manzanas. Uso:  apps/api/.venv/Scripts/python scripts/validate_adapters_vs_reference.py [UBIGEO ...]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import pandas as pd

from app.schemas.analysis import AnalysisSpec
from app.services.analyses.runner import AnalysisError, RunStore, run_analysis

REF = ROOT / "data" / "_local_reference" / "NinoDetect_Entradas_NASA_Procesadas_v12"
# Polígono oceánico del estudio previo (frente a Trujillo), documentado en su notebook 02.
OCEAN = {"type": "Polygon", "coordinates": [[[-80.55, -8.80], [-79.45, -8.80], [-79.45, -7.50], [-80.55, -7.50],
                                             [-80.55, -8.80]]]}
PAIRS = [
    ("nasa-gldas-noah-v21-3h", "soil_moisture_0_10cm_kgm2", "suelo_humedad_kgm2"),
    ("nasa-gldas-noah-v21-3h", "air_temperature_c", "t_aire_gldas_C"),
    ("nasa-merra2-slv", "air_temperature_2m_c", "t_aire_merra_C"),
    ("nasa-merra2-slv", "total_precipitable_water_kgm2", "vapor_aire_kgm2"),
    ("nasa-merra2-slv", "wind_u_10m_ms", "viento_u_ms"),
    ("nasa-merra2-slv", "wind_v_10m_ms", "viento_v_ms"),
    ("nasa-modis-mod13q1-061", "ndvi", "ndvi"),
    ("nasa-modis-aqua-sst-l3smi", "sst_c", "sst_oceano_C"),
]


def main(ubigeos: list[str]) -> int:
    gj = {f["properties"]["ubigeo"]: f["geometry"]
          for f in json.loads((REF / "02_Trujillo_8_Distritos.geojson").read_text(encoding="utf-8"))["features"]}
    ref = pd.read_csv(REF / "03_NASA_Series_Mensuales_Trujillo_Formato_Largo.csv", encoding="utf-8-sig",
                      dtype={"ubigeo": str})
    store = RunStore(ROOT / ".cache")
    print(f"{'variable':32} {'territorio':16} {'n_ref':>5} {'n_ours':>6} {'n_común':>7} {'|d|med':>8} {'|d|max':>8} "
          f"{'corr':>8} {'seg':>5}")
    for ds, var, ref_var in PAIRS:
        targets = ["OCEANO_TRUJILLO"] if ref_var == "sst_oceano_C" else ubigeos
        for u in targets:
            geom = OCEAN if u == "OCEANO_TRUJILLO" else gj[u]
            spec = AnalysisSpec.model_validate({
                "data": {"dataset_id": ds, "variable_id": var}, "geography": {"custom_geometry": geom},
                "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "temporal_aggregation": "mean"},
            })
            t0 = time.time()
            try:
                run = run_analysis(spec, store)
            except AnalysisError as e:
                print(f"{var:32} {u:16} ERROR {e.code}: {e.detail}")
                continue
            ours = pd.Series({s["time_start_utc"]: s["value"] for s in run["series"]}, dtype=float)
            r = ref[(ref.ubigeo == u) & (ref.variable == ref_var)].set_index("fecha")["valor"]
            j = pd.concat({"o": ours, "r": r}, axis=1).dropna()
            d = (j.o - j.r).abs()
            corr = j.o.corr(j.r) if len(j) > 2 else float("nan")
            print(f"{var:32} {u:16} {r.notna().sum():>5} {ours.notna().sum():>6} {len(j):>7} {d.mean():>8.4f} "
                  f"{d.max():>8.4f} {corr:>8.5f} {time.time() - t0:>5.0f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["130101", "130106"]))
