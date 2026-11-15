"""Genera examples/notebooks/01_analisis_tendencias_api.ipynb (fuente versionable del notebook).

Uso:  apps/api/.venv/Scripts/python scripts/build_notebook_01.py [--execute]
Con --execute lo corre contra EARTH_TREND_API_URL (servidor levantado) y guarda las salidas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "notebooks" / "01_analisis_tendencias_api.ipynb"

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    md("""# Análisis de tendencias NASA desde Python — vía API (sin Earth Engine en el cliente)

Este notebook reproduce, **solo con la API REST y el SDK oficial**, lo que la plataforma web hace al pulsar *Analizar*:
elegir variable NASA, territorio, periodo, estimador e intervalo de confianza, y obtener **qué cambia, dónde, cuánto y
si el cambio es estadísticamente distinguible de cero**.

* No necesita credenciales de Google Earth Engine: el backend procesa los datos NASA.
* No usa notebooks ni archivos de estudios anteriores.
* Variables de entorno: `EARTH_TREND_API_URL` (p. ej. `http://localhost:8000/api/v1`) y, si el servidor lo exige,
  `EARTH_TREND_API_TOKEN`.

> **Cómo leer los resultados.** Un IC del 95 % es una propiedad del *procedimiento* bajo sus supuestos, no "95 % de
> probabilidad de que el valor esté dentro". Un p-valor alto **no** prueba ausencia de cambio: indica que los datos no
> permiten distinguirlo de cero con ese método."""),
    code("""# pip install -e packages/python-sdk[plot]   (desde la raíz del repositorio)
import os
import pandas as pd
from earth_trend_client import EarthTrendClient, EarthTrendAPIError

os.environ.setdefault("EARTH_TREND_API_URL", "http://localhost:8000/api/v1")
client = EarthTrendClient(timeout=900)
client.health()"""),
    md("## 1. ¿Qué variables NASA hay? (catálogo)"),
    code("""variables = pd.DataFrame(client.catalog.variables())
variables[["dataset_id", "variable_id", "physical_quantity", "unit_display", "temporal_aggregations"]]"""),
    code("""datasets = pd.DataFrame(client.catalog.datasets())
datasets[["dataset_id", "ee_collection_id", "nominal_resolution", "temporal_coverage_start", "native_granularity"]]"""),
    md("""## 2. ¿Dónde? (territorio con fronteras versionadas)

Para Perú se usa por defecto la cartografía oficial del IGN (ADM1–ADM3 con UBIGEO); para el resto del mundo,
geoBoundaries. Cada territorio tiene un `geo_id` estable que incluye la versión de la frontera."""),
    code("""hits = client.geographies.search("trujillo", country="PER")
pd.DataFrame(hits)[["geo_id", "name", "admin_level", "path", "area_km2", "boundary_set_id"]]"""),
    code("""provincia = next(h for h in hits if h["admin_level"] == "ADM2")
provincia["geo_id"], provincia["area_km2"]"""),
    md("""## 3. ¿Cuánto cambia y es significativo? — precipitación anual IMERG 2003–2024

Totales anuales (los años incompletos se excluyen, no se rellenan). Estimador Theil–Sen (robusto a extremos), su
propio IC y prueba de Mann–Kendall."""),
    code("""base = {
    "data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
    "geography": {"geo_ids": [provincia["geo_id"]]},
    "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year",
             "temporal_aggregation": "total"},
}
spec_sen = base | {"statistics": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                                  "significance_test": "mann_kendall"}}
run_sen = client.analyses.run(spec_sen, idempotency_key="nb01-imerg-anual-sen")
st = client.analyses.statistics(run_sen.id)
print(run_sen.id)
print(f"{st.estimate:.2f} {st.estimate_unit} · {st.confidence_interval} · {st.hypothesis_test} · N={st.n_observations}")
for w in st.warnings:
    print("aviso:", w)"""),
    code("""ax = client.analyses.plot(run_sen.id)"""),
    md("""## 4. ¿Resiste el resultado a un cambio de método?

Misma serie, otros procedimientos. La extracción NASA se reutiliza desde caché: solo cambia la estadística."""),
    code("""variantes = {
    "Theil–Sen + IC analítico + MK": spec_sen["statistics"],
    "OLS + IC HAC (Newey–West) + t-HAC": {"estimator": "ols", "interval_method": "hac_newey_west",
                                          "significance_test": "ols_hac_t"},
    "Theil–Sen + bootstrap por bloques (b=3)": {"estimator": "theil_sen", "interval_method": "moving_block_bootstrap",
                                                "significance_test": "mann_kendall", "block_length": 3, "seed": 2026},
    "Theil–Sen + IC 90 %": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                            "significance_test": "mann_kendall", "confidence_level": 0.90},
}
filas = []
for nombre, stats in variantes.items():
    r = client.analyses.run(base | {"statistics": stats})
    s = client.analyses.statistics(r.id)
    filas.append({"método": nombre, "pendiente": s.estimate, "unidad": s.estimate_unit,
                  "IC_inf": s.confidence_interval.lower, "IC_sup": s.confidence_interval.upper,
                  "nivel": s.confidence_interval.level, "p": s.hypothesis_test.p_value,
                  "extracción_en_caché": r.raw["extraction_cache_hit"], "run_id": r.id})
pd.DataFrame(filas).round(3)"""),
    md("""## 5. Serie mensual sin estacionalidad (anomalías respecto a la climatología de cada mes)

Enero se compara con eneros, febrero con febreros, etc. El IC usa bootstrap por bloques de 12 meses para respetar la
dependencia temporal."""),
    code("""spec_anom = base | {
    "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "month"},
    "transforms": {"seasonality": "monthly_anomaly"},
    "statistics": {"estimator": "theil_sen", "interval_method": "moving_block_bootstrap",
                   "significance_test": "mann_kendall", "block_length": 12, "resamples": 1000, "seed": 2026},
}
run_anom = client.analyses.run(spec_anom)
st_anom = client.analyses.statistics(run_anom.id)
serie = client.analyses.series_dataframe(run_anom.id)
print(st_anom.estimate, st_anom.estimate_unit, st_anom.confidence_interval, st_anom.hypothesis_test, sep=" · ")
serie.set_index("time_start_utc")["value"].plot(figsize=(10, 3), lw=0.8, title="Anomalía mensual de precipitación (mm)");"""),
    md("""## 6. Otra variable: vegetación (MODIS NDVI, 250 m, máscara de calidad)"""),
    code("""spec_ndvi = {
    "data": {"dataset_id": "nasa-modis-mod13q1-061", "variable_id": "ndvi"},
    "geography": {"geo_ids": [provincia["geo_id"]]},
    "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year",
             "temporal_aggregation": "mean"},
    "statistics": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                   "significance_test": "mann_kendall"},
}
run_ndvi = client.analyses.run(spec_ndvi)
s = client.analyses.statistics(run_ndvi.id)
print(f"NDVI: {s.estimate:.4f} {s.estimate_unit} · {s.confidence_interval} · {s.hypothesis_test} · {s.status}")"""),
    md("""## 7. La plataforma también dice cuándo un dato **no** representa al territorio, o no existe

**a)** Un distrito de 12 km² frente a una celda del reanálisis MERRA-2 (~55 × 69 km): el valor existe, pero es el de una
celda mucho mayor que el distrito. La API lo entrega **con un aviso**, nunca como "medición del distrito"."""),
    code("""distrito = client.geographies.search("victor larco", country="PER", level="ADM3")[0]
r = client.analyses.run({"data": {"dataset_id": "nasa-merra2-slv", "variable_id": "air_temperature_2m_c"},
                         "geography": {"geo_ids": [distrito["geo_id"]]},
                         "time": {"start": "2020-01-01", "end_exclusive": "2021-01-01"}})
print(distrito["name"], distrito["area_km2"], "km²")
print(client.analyses.statistics(r.id).warnings)"""),
    md("""**b)** Temperatura superficial del **mar** sobre una provincia andina: no hay píxeles oceánicos. La API responde
`422 insufficient_coverage` explicando la causa, en lugar de extrapolar o devolver cero."""),
    code("""andina = client.geographies.search("cusco", country="PER", level="ADM2")[0]
try:
    client.analyses.run({"data": {"dataset_id": "nasa-modis-aqua-sst-l3smi", "variable_id": "sst_c"},
                         "geography": {"geo_ids": [andina["geo_id"]]},
                         "time": {"start": "2020-01-01", "end_exclusive": "2021-01-01"}})
except EarthTrendAPIError as e:
    print(e.status, e.code)
    print(e.detail)"""),
    md("""## 8. Reproducibilidad: todo resultado es recuperable por su `run_id`

El manifiesto identifica la especificación (hash), la colección NASA y su versión, la geometría y la versión del
algoritmo. Con el `run_id` cualquiera puede recuperar exactamente el mismo resultado, desde Python o desde la web."""),
    code("""m = client.analyses.manifest(run_sen.id)
{k: m[k] for k in ("run_id", "analysis_spec_hash", "source_versions", "provenance", "compute")}"""),
    md("""### Lo mismo sin SDK (HTTP puro)"""),
    code("""import requests
url = os.environ["EARTH_TREND_API_URL"].rstrip("/")
headers = {"Authorization": f"Bearer {os.environ['EARTH_TREND_API_TOKEN']}"} if os.environ.get("EARTH_TREND_API_TOKEN") else {}
raw = requests.get(f"{url}/analyses/{run_sen.id}/statistics", headers=headers, timeout=60).json()
assert raw["estimate"] == st.estimate and raw["ci_lower"] == st.confidence_interval.lower  # mismo resultado
{k: raw[k] for k in ("estimate", "estimate_unit", "ci_lower", "ci_upper", "p_value", "status")}"""),
    md("""---
**Fuentes y atribución.** NASA GPM IMERG V07, MODIS MOD13Q1 061 y MERRA-2, procesados mediante Google Earth Engine;
coberturas, cuotas y latencias sujetas al servicio. Límites: IGN Perú vía OCHA HDX COD-AB (CC BY-IGO) y
geoBoundaries gbOpen v6.0.0 (CC BY 4.0). Resultados exploratorios de tendencia: no constituyen alertas oficiales."""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
    "language_info": {"name": "python"},
})


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if "--execute" in sys.argv:
        from nbclient import NotebookClient

        NotebookClient(nb, timeout=1800, kernel_name="earth-trend", resources={"metadata": {"path": str(ROOT)}}).execute()
        nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, OUT)
    print(f"OK → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
