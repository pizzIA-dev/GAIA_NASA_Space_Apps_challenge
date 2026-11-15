"""La caché de demostración (data/demo-cache) cubre los ejemplos por defecto de la web: si cambian los ejemplos o la
versión de un producto sin regenerarla (scripts/demo_cache.py collect), la portada volvería a tardar minutos."""

from app.core.config import REPO_ROOT
from app.schemas.analysis import AnalysisSpec, extraction_key
from app.services.earth_engine.adapters import ADAPTERS

DEMO = REPO_ROOT / "data" / "demo-cache" / "extractions"
DEFAULT_VARS = [("nasa-gpm-imerg-monthly-v07", "precipitation_mm_month"), ("nasa-merra2-slv", "air_temperature_2m_c"),
                ("nasa-gldas-noah-v21-3h", "soil_moisture_0_10cm_kgm2"), ("nasa-modis-mod13q1-061", "ndvi")]


def _file(geo: str, ds: str, var: str) -> str:
    spec = AnalysisSpec.model_validate({
        "data": {"dataset_id": ds, "variable_id": var}, "geography": {"geo_ids": [geo]},
        "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"}})
    return extraction_key(spec, ADAPTERS[ds].info.version).replace("sha256:", "") + ".json"


def test_default_panel_territory_is_preloaded():
    for ds, var in DEFAULT_VARS:  # Panel/Explorar por defecto: Lima
        assert (DEMO / _file("pe-ign2020:15", ds, var)).is_file(), f"falta {var} de Lima en la caché de demostración"
    assert (DEMO / _file("pe-ign2020:04", *DEFAULT_VARS[0])).is_file()  # Análisis avanzado: Arequipa
