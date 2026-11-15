"""POST /analyses/compare: familia de análisis con BH-FDR, errores por ítem y cuota de familia. Sin Earth Engine."""

import pytest
from earth_trend_client import EarthTrendClient
from fastapi.testclient import TestClient
from statsmodels.stats.multitest import multipletests

from app.api.v1 import routes
from app.core.limits import ExtractionGate, SlidingWindowLimiter
from app.core.security import ApiKeyStore
from app.main import app
from app.services.analyses.runner import RunStore
from tests.contract.test_access_policy import MERRA_SPEC, FakeMERRA
from tests.contract.test_analyses_api import FakeIMERG, make_spec
from tests.contract.test_geographies import SQ


def spec_for(geometry, start="2003-01-01"):
    s = make_spec()
    s["geography"] = {"custom_geometry": geometry}
    s["time"] = {"start": start, "end_exclusive": "2025-01-01", "granularity": "year"}
    return s


SHAPES = [SQ, {"type": "Polygon", "coordinates": [[[-79.2, -8.3], [-79.1, -8.3], [-79.1, -8.2], [-79.2, -8.3]]]},
          {"type": "Polygon", "coordinates": [[[-78.9, -8.0], [-78.8, -8.0], [-78.8, -7.9], [-78.9, -8.0]]]}]


class SometimesEmptyIMERG(FakeIMERG):
    """Devuelve una serie vacía para el segundo polígono (simula un territorio sin píxeles)."""

    def extract(self, variable_id, geometry, start, end_exclusive):
        rows = super().extract(variable_id, geometry, start, end_exclusive)
        if geometry == SHAPES[1]:
            for r in rows:
                r["value"] = None
        return rows


@pytest.fixture
def ctx(tmp_path):
    keys = ApiKeyStore(tmp_path / "keys.json")
    token, _ = keys.create("comparar")
    limiter = SlidingWindowLimiter(3600.0)
    adapters = {"nasa-gpm-imerg-monthly-v07": SometimesEmptyIMERG(), "nasa-merra2-slv": FakeMERRA()}
    app.dependency_overrides.update({
        routes.get_store: lambda: RunStore(tmp_path / "store"),
        routes.get_adapters: lambda: adapters,
        routes.get_key_store: lambda: keys,
        routes.get_limiter: lambda: limiter,
        routes.get_gate: lambda: ExtractionGate(2, wait_s=0.01),
    })
    yield TestClient(app), {"Authorization": f"Bearer {token}"}, limiter
    app.dependency_overrides.clear()


def test_compare_bh_fdr_and_per_item_errors(ctx):
    c, _, _ = ctx
    r = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(g) for g in SHAPES], "family_id": "prueba"})
    assert r.status_code == 200, r.text
    body = r.json()
    items = body["items"]
    assert [it["status"] for it in items] == ["succeeded", "failed", "succeeded"]
    assert items[1]["error"]["code"] == "insufficient_coverage"
    ok = [it for it in items if it["status"] == "succeeded"]
    ps = [it["statistics"]["p_value"] for it in ok]
    expected = multipletests(ps, method="fdr_bh")[1]
    assert [it["statistics"]["q_value"] for it in ok] == pytest.approx(list(expected))
    assert body["family_size"] == 2 and ok[0]["statistics"]["multiple_tests_family"] == "prueba"
    assert len(ok[0]["series"]) == 22 and ok[0]["run_id"].startswith("run_")


def test_compare_without_correction_keeps_q_null(ctx):
    c, _, _ = ctx
    body = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(SQ)], "multiple_testing": "none"}).json()
    assert body["items"][0]["statistics"]["q_value"] is None


def test_heavy_item_without_token_fails_alone(ctx):
    c, auth, _ = ctx
    body = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(SQ), MERRA_SPEC]}).json()
    assert body["items"][0]["status"] == "succeeded"
    assert body["items"][1]["error"]["code"] == "token_required"
    with_token = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(SQ), MERRA_SPEC]}, headers=auth).json()
    assert [it["status"] for it in with_token["items"]] == ["succeeded", "succeeded"]


def test_family_quota_is_checked_before_consuming(ctx, monkeypatch):
    import dataclasses

    from app.services.analyses import runner

    c, _, limiter = ctx
    monkeypatch.setattr(runner, "settings", dataclasses.replace(runner.settings, anon_extractions_per_hour=2))
    r = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(g, "2005-01-01") for g in SHAPES]})
    assert r.status_code == 429 and "3 extracciones nuevas" in r.json()["detail"]
    assert limiter.remaining("anon:testclient", 2) == 2  # nada consumido


def test_compare_limits_family_size(ctx):
    c, _, _ = ctx
    r = c.post("/api/v1/analyses/compare", json={"specs": [spec_for(SQ)] * (routes.COMPARE_MAX_SPECS + 1)})
    assert r.status_code == 422


def test_sdk_compare_matches_rest(ctx):
    c, auth, _ = ctx
    sdk = EarthTrendClient(base_url="http://testserver/api/v1", token=auth["Authorization"][7:], http_client=c)
    specs = [spec_for(SHAPES[0]), spec_for(SHAPES[2])]
    a = sdk.analyses.compare(specs, family_id="sdk")
    b = c.post("/api/v1/analyses/compare", json={"specs": specs, "family_id": "sdk"}, headers=auth).json()
    assert [it["run_id"] for it in a["items"]] == [it["run_id"] for it in b["items"]]
    assert [it["statistics"]["q_value"] for it in a["items"]] == [it["statistics"]["q_value"] for it in b["items"]]


def test_difference_contract_and_sdk(ctx):
    c, auth, _ = ctx
    a, b = spec_for(SHAPES[0]), spec_for(SHAPES[2])
    r = c.post("/api/v1/analyses/difference", json={"a": a, "b": b, "resamples": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    d = body["difference"]
    # El adaptador simulado devuelve la misma serie para cualquier geometría: diferencia exactamente 0.
    assert d["estimate"] == 0 and d["p_value"] == 1.0 and d["n_paired_observations"] == 22
    assert "pares de periodos" in d["ci_method"] and body["a"]["run_id"] != body["b"]["run_id"]
    sdk = EarthTrendClient(base_url="http://testserver/api/v1", token=auth["Authorization"][7:], http_client=c)
    assert sdk.analyses.difference(a, b, resamples=500)["difference"] == d


def test_difference_rejects_non_comparable_specs(ctx):
    c, _, _ = ctx
    a = spec_for(SHAPES[0])
    other_period = spec_for(SHAPES[2], start="2005-01-01")
    r = c.post("/api/v1/analyses/difference", json={"a": a, "b": other_period})
    assert r.status_code == 409 and "time" in r.json()["detail"]
    assert c.post("/api/v1/analyses/difference", json={"a": a, "b": a}).status_code == 422
    empty = c.post("/api/v1/analyses/difference", json={"a": a, "b": spec_for(SHAPES[1])})
    assert empty.status_code == 422 and empty.json()["detail"].startswith("B:")
    ols = {**a, "statistics": {"estimator": "ols", "interval_method": "hac_newey_west", "significance_test": "ols_hac_t"}}
    ols_b = {**spec_for(SHAPES[2]), "statistics": ols["statistics"]}
    r = c.post("/api/v1/analyses/difference", json={"a": ols, "b": ols_b})
    assert r.status_code == 409 and "Theil–Sen" in r.json()["detail"]
