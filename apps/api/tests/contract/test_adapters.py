"""Adaptadores de composición mensual: lógica sin red (resultados de EE simulados)."""

from datetime import date

import pytest

from app.schemas.analysis import AnalysisSpec
from app.services.analyses.runner import AnalysisError, RunStore, run_analysis
from app.services.earth_engine.adapters import (
    ADAPTERS,
    GLDASMonthly,
    MODISNDVIMonthly,
    MonthlyCompositeAdapter,
    month_starts,
)
from tests.contract.test_analyses_api import SQUARE


def test_catalog_has_five_available_datasets_with_recipes():
    assert set(ADAPTERS) == {"nasa-gpm-imerg-monthly-v07", "nasa-gldas-noah-v21-3h", "nasa-merra2-slv",
                             "nasa-modis-mod13q1-061", "nasa-modis-aqua-sst-l3smi"}
    for a in ADAPTERS.values():
        assert a.info.status == "available"
        if isinstance(a, MonthlyCompositeAdapter):
            assert {v.variable_id for v in a.info.variables} == set(a.recipes)


def test_unit_recipes():
    g = GLDASMonthly.recipes["air_temperature_c"]
    assert g.offset == -273.15 and g.scale_factor == 1.0
    n = MODISNDVIMonthly.recipes["ndvi"]
    assert n.scale_factor == 0.0001 and n.qa_band == "SummaryQA" and n.qa_max == 1


def test_rows_preserve_missing_and_flags():
    a = MODISNDVIMonthly()
    months = month_starts(date(2000, 1, 1), date(2000, 5, 1))
    props = {
        "2000-02-01": {"n": 1, "mean": 0.31, "count": 120},  # el producto empieza el 2000-02-18
        "2000-03-01": {"n": 2, "mean": None, "count": 0},  # imágenes sin píxeles válidos (nubes/QA)
        "2000-04-01": {"n": 2, "mean": 0.42, "count": 300},
    }
    rows = a.rows_from_props("ndvi", months, props)
    by = {r["period_label"]: r for r in rows}
    assert by["2000-01"]["value"] is None and "no_image" in by["2000-01"]["quality_flags"]
    assert "partial_month_product_start" in by["2000-02"]["quality_flags"]
    assert by["2000-03"]["value"] is None and "no_valid_pixels" in by["2000-03"]["quality_flags"]
    assert by["2000-04"]["value"] == 0.42 and by["2000-04"]["source_image_count"] == 2
    assert all(r["extraction_scale_m"] == 500.0 and r["unit"] == "adimensional" for r in rows)


def test_total_aggregation_rejected_for_mean_only_variables(tmp_path):
    spec = AnalysisSpec.model_validate({
        "data": {"dataset_id": "nasa-gldas-noah-v21-3h", "variable_id": "air_temperature_c"},
        "geography": {"custom_geometry": SQUARE},
        "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year",
                 "temporal_aggregation": "total"},
    })
    with pytest.raises(AnalysisError) as e:
        run_analysis(spec, RunStore(tmp_path))
    assert e.value.status == 409


def test_default_temporal_aggregation_follows_variable_and_hash_is_normalized(tmp_path):
    from tests.contract.test_analyses_api import FakeIMERG, make_spec

    store, fake = RunStore(tmp_path), {"nasa-gpm-imerg-monthly-v07": FakeIMERG()}
    implicit = AnalysisSpec.model_validate(make_spec())  # sin temporal_aggregation
    explicit = AnalysisSpec.model_validate(make_spec() | {"time": {
        "start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "month", "temporal_aggregation": "total"}})
    a, b = run_analysis(implicit, store, fake), run_analysis(explicit, store, fake)
    assert a["run_id"] == b["run_id"] and b["cache_hit"]
    assert a["request"]["time"]["temporal_aggregation"] == "total"
    gldas = GLDASMonthly().info.variable("air_temperature_c")
    assert gldas.temporal_aggregations[0] == "mean"
