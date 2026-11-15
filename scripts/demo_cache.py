"""Caché de demostración: series NASA reales de los ejemplos por defecto de la web, precargadas en cada compilación.

En el alojamiento gratuito (Render) el disco es efímero: la caché se pierde con cada despliegue o cuando el servicio
se duerme, y el primer visitante esperaba minutos. Aquí se guardan, versionadas, las EXTRACCIONES (series mensuales
de Earth Engine, no los resultados estadísticos) de:
  - Panel / Explorar: Lima (departamento, IGN) — 4 variables por defecto, 2003–2024.
  - Atlas: provincias de Lima — mismas 4 variables.
  - Análisis avanzado: lluvia de Lima y Arequipa.
La estadística se recalcula siempre con el motor vigente (la clave de extracción no depende del método).

    apps/api/.venv/Scripts/python scripts/demo_cache.py collect   # requiere Earth Engine local
    python scripts/e2e_fixtures.py seed <cache>                  # la siembra también copia esta caché
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

OUT = ROOT / "data" / "demo-cache"
LIMA, AREQUIPA = "pe-ign2020:15", "pe-ign2020:04"
VARS = [("nasa-gpm-imerg-monthly-v07", "precipitation_mm_month"), ("nasa-merra2-slv", "air_temperature_2m_c"),
        ("nasa-gldas-noah-v21-3h", "soil_moisture_0_10cm_kgm2"), ("nasa-modis-mod13q1-061", "ndvi")]
STATS = {"estimator": "theil_sen", "interval_method": "theil_sen_ar1", "significance_test": "mann_kendall_ar1"}


def specs() -> list[dict]:
    from app.services.geographies.registry import registry

    lima_provinces = [g.geo_id for g in registry.children(registry.get(LIMA))]
    out = []
    for geo in [LIMA, *lima_provinces]:
        for ds, var in VARS:
            out.append((geo, ds, var))
    out.append((AREQUIPA, *VARS[0]))
    return [{"data": {"dataset_id": ds, "variable_id": var}, "geography": {"geo_ids": [geo]},
             "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"},
             "statistics": STATS} for geo, ds, var in out]


def collect() -> None:
    from app.schemas.analysis import AnalysisSpec, extraction_key
    from app.services.analyses import runner

    store = runner.RunStore(runner.settings.cache_dir)
    (OUT / "extractions").mkdir(parents=True, exist_ok=True)
    rows = []
    for raw in specs():
        spec = AnalysisSpec.model_validate(raw)
        try:
            run = runner.run_analysis(spec)  # extrae en EE solo si no está ya en la caché local
        except runner.AnalysisError as e:
            print(f"omitida {raw['geography']['geo_ids'][0]} {raw['data']['variable_id']}: {e.code}")
            continue
        adapter = runner.ADAPTERS[spec.data.dataset_id]
        key = extraction_key(spec, adapter.info.version)
        src = store._p("extractions", key)
        shutil.copy2(src, OUT / "extractions" / src.name)
        rows.append({"file": src.name, "geo_id": raw["geography"]["geo_ids"][0], "dataset": spec.data.dataset_id,
                     "variable": spec.data.variable_id, "run_id": run["run_id"]})
        print(f"ok {rows[-1]['geo_id']:22s} {rows[-1]['variable']}")
    manifest = {"purpose": "Caché de demostración: extracciones NASA reales (Earth Engine) de los ejemplos por defecto "
                           "de la web; se siembran en cada compilación para que la portada cargue al instante.",
                "generated_at": datetime.now(UTC).isoformat(), "extractions": rows}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1024
    print(f"{len(rows)} extracciones → {OUT} ({size:.0f} KB)")


if __name__ == "__main__":
    if sys.argv[1:] != ["collect"]:
        raise SystemExit(__doc__)
    collect()
