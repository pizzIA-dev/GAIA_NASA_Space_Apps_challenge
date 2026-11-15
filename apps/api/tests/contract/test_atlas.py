"""POST /atlas: pendiente por subunidad (extracciones en paralelo), caché compartida con /analyses y BH-FDR.
Adaptador y geografías SIMULADOS (sin Earth Engine)."""

import pytest
from fastapi.testclient import TestClient
from statsmodels.stats.multitest import multipletests

from app.api.v1 import routes
from app.core.limits import ExtractionGate, SlidingWindowLimiter
from app.main import app
from app.services.analyses.runner import RunStore
from tests.contract.test_analyses_api import FakeIMERG
from tests.contract.test_geographies import geos, pe_geos  # noqa: F401 — fixtures

BODY = {"parent_geo_id": "pe-ign2020:1301", "dataset_id": "nasa-gpm-imerg-monthly-v07",
        "variable_id": "precipitation_mm_month", "start_year": 2003, "end_year": 2024}


@pytest.fixture
def ctx(tmp_path, pe_geos):  # noqa: F811
    fake = FakeIMERG()
    limiter = SlidingWindowLimiter(3600.0)
    app.dependency_overrides.update({
        routes.get_geographies: lambda: pe_geos,
        routes.get_store: lambda: RunStore(tmp_path / "store"),
        routes.get_adapters: lambda: {"nasa-gpm-imerg-monthly-v07": fake},
        routes.get_limiter: lambda: limiter,
        routes.get_gate: lambda: ExtractionGate(2, wait_s=0.01),
    })
    yield TestClient(app), fake, limiter
    app.dependency_overrides.clear()


def test_atlas_bh_fdr_quota_and_shared_cache(ctx):
    c, fake, limiter = ctx
    r = c.post("/api/v1/atlas", json=BODY)
    assert r.status_code == 200, r.text
    b = r.json()
    assert fake.calls == 2 and b["new_extractions"] == 2 and b["cost"]["tier"] == "light"
    assert limiter.remaining("anon:testclient", 20) == 19  # cada 12 unidades nuevas = una extracción del cupo
    assert [it["geo_id"] for it in b["items"]] == ["pe-ign2020:130101", "pe-ign2020:130111"]
    ok = [it for it in b["items"] if it["status"] == "succeeded"]
    assert len(ok) == 2 and b["n_succeeded"] == 2
    expected = multipletests([it["statistics"]["p_value"] for it in ok], method="fdr_bh")[1]
    assert [it["statistics"]["q_value"] for it in ok] == pytest.approx(list(expected))
    assert ok[0]["statistics"]["multiple_tests_family"] == "atlas:pe-ign2020:1301"
    assert b["scale"]["center"] == 0 and b["scale"]["max_abs_estimate"] > 0
    assert any("píxel" in w for w in ok[0]["statistics"]["warnings"])  # distritos menores que un píxel IMERG

    # Mismo análisis que Explorar → el run del atlas se reutiliza en /analyses (misma especificación, mismo run_id)
    spec = {"data": {"dataset_id": BODY["dataset_id"], "variable_id": BODY["variable_id"]},
            "geography": {"geo_ids": ["pe-ign2020:130101"]},
            "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"},
            "statistics": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                           "significance_test": "mann_kendall"}}
    run = c.post("/api/v1/analyses", json=spec).json()
    assert run["run_id"] == ok[0]["run_id"] and run["cache_hit"] is True

    again = c.post("/api/v1/atlas", json=BODY).json()
    assert fake.calls == 2 and again["new_extractions"] == 0 and again["cost"]["tier"] == "cached"


def test_atlas_validation_errors(ctx):
    c, _, _ = ctx
    assert c.post("/api/v1/atlas", json=BODY | {"end_year": 2008}).status_code == 422
    assert c.post("/api/v1/atlas", json=BODY | {"parent_geo_id": "pe-ign2020:99"}).status_code == 404
    leaf = c.post("/api/v1/atlas", json=BODY | {"parent_geo_id": "pe-ign2020:130101"})
    assert leaf.status_code == 422 and leaf.json()["title"] == "no_subunits"
    assert c.post("/api/v1/atlas", json=BODY | {"variable_id": "nope"}).status_code == 404


def test_sdk_atlas_matches_rest(ctx):
    from earth_trend_client import EarthTrendClient

    c, _, _ = ctx
    sdk = EarthTrendClient(base_url="http://testserver/api/v1", http_client=c)
    a = sdk.analyses.atlas(BODY["parent_geo_id"], BODY["dataset_id"], BODY["variable_id"])
    b = c.post("/api/v1/atlas", json=BODY).json()
    assert [it["run_id"] for it in a["items"]] == [it["run_id"] for it in b["items"]]
    assert [it["statistics"]["q_value"] for it in a["items"]] == [it["statistics"]["q_value"] for it in b["items"]]
