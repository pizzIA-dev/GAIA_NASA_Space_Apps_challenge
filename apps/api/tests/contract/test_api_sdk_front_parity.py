"""Paridad REST ↔ SDK Python (plan §12A.4). La parte web (Playwright) se añadirá en F1/F4.

Ambos caminos deben devolver el mismo run_id, spec_hash, fuentes, serie y estadística, porque comparten el mismo motor.
Datos SINTÉTICOS (adaptador simulado), sin Earth Engine.
"""

import math

import httpx
import pytest
from earth_trend_client import EarthTrendAPIError, EarthTrendClient, Statistics
from fastapi.testclient import TestClient

from app.api.v1 import routes
from app.core.security import ApiKeyStore
from app.main import app
from app.services.analyses.runner import RunStore
from tests.contract.test_analyses_api import FakeIMERG, make_spec


@pytest.fixture
def env(tmp_path):
    fake = FakeIMERG(missing={7})  # un faltante real para verificar que no se convierte en 0
    app.dependency_overrides[routes.get_store] = lambda: RunStore(tmp_path)
    app.dependency_overrides[routes.get_adapters] = lambda: {"nasa-gpm-imerg-monthly-v07": fake}
    keys = ApiKeyStore(tmp_path / "keys.json")
    token, _ = keys.create("paridad")
    app.dependency_overrides[routes.get_key_store] = lambda: keys
    http = TestClient(app)
    sdk = EarthTrendClient(base_url="http://testserver/api/v1", token=token, http_client=http)
    yield http, sdk, fake
    app.dependency_overrides.clear()


def test_rest_and_sdk_return_identical_results(env):
    http, sdk, fake = env
    spec = make_spec(estimator="ols", interval_method="hac_newey_west", significance_test="ols_hac_t")

    rest = http.post("/api/v1/analyses", json=spec, headers={"Authorization": sdk._headers["Authorization"]}).json()
    run = sdk.analyses.run(spec, idempotency_key="paridad-001")

    assert run.id == rest["run_id"] and run.analysis_spec_hash == rest["analysis_spec_hash"]
    assert fake.calls == 1  # el SDK reutilizó la misma extracción/run

    st = sdk.analyses.statistics(run.id)
    assert isinstance(st, Statistics)
    assert st.raw == rest["statistics"]
    assert st.estimate == rest["statistics"]["estimate"]
    assert (st.confidence_interval.lower, st.confidence_interval.upper) == (
        rest["statistics"]["ci_lower"], rest["statistics"]["ci_upper"])
    assert st.hypothesis_test.p_value == rest["statistics"]["p_value"]

    df = sdk.analyses.series_dataframe(run.id)
    assert len(df) == len(rest["series"]) == 264
    for v_sdk, row in zip(df["value"], rest["series"], strict=True):
        if row["value"] is None:
            assert math.isnan(v_sdk)  # faltante preservado, nunca 0
        else:
            assert v_sdk == row["value"]

    manifest = sdk.analyses.manifest(run.id)
    assert manifest["source_versions"] == rest["source_versions"]
    assert manifest["analysis_spec_hash"] == rest["analysis_spec_hash"]


def test_changing_ci_from_sdk_recomputes_without_new_extraction(env):
    _, sdk, fake = env
    a = sdk.analyses.run(make_spec())
    b = sdk.analyses.run(make_spec(confidence_level=0.9))
    assert a.id != b.id and b.raw["extraction_cache_hit"] and fake.calls == 1
    sa, sb = sdk.analyses.statistics(a.id), sdk.analyses.statistics(b.id)
    assert sa.estimate == sb.estimate  # mismo estimador
    assert sb.confidence_interval.upper - sb.confidence_interval.lower < (
        sa.confidence_interval.upper - sa.confidence_interval.lower)  # IC 90 % más estrecho que 95 %


def test_sdk_raises_typed_problem_errors(env):
    _, sdk, _ = env
    with pytest.raises(EarthTrendAPIError) as e:
        sdk.analyses.submit(make_spec(estimator="theil_sen", interval_method="hac_newey_west"))
    assert e.value.status == 409 and e.value.code == "incompatible_method"
    with pytest.raises(EarthTrendAPIError) as e:
        sdk.analyses.get("run_inexistente")
    assert e.value.status == 404


def test_catalog_search_and_capabilities(env):
    _, sdk, _ = env
    hits = sdk.catalog.search("precip")
    assert any(h["variable_id"] == "precipitation_mm_month" for h in hits)
    assert "theil_sen" in sdk.catalog.capabilities()["estimators"]
    assert sdk.health()["status"] == "ok"


def test_sdk_sends_token_and_retries_on_429():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("Authorization"))
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"title": "quota_exceeded"})
        return httpx.Response(200, json={"status": "ok"})

    sdk = EarthTrendClient(base_url="http://x/api/v1", token="abc",
                           http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert sdk.health() == {"status": "ok"}
    assert calls == ["Bearer abc", "Bearer abc"]


def test_openapi_exposes_all_implemented_v1_endpoints():
    """Guarda contra la desaparición silenciosa de rutas (regresión detectada en sesión 2)."""
    paths = set(app.openapi()["paths"])
    required = {
        "/api/v1/health", "/api/v1/catalog/capabilities", "/api/v1/catalog/datasets", "/api/v1/catalog/variables",
        "/api/v1/geographies/boundary-sets", "/api/v1/geographies/countries", "/api/v1/geographies/search",
        "/api/v1/geographies/{geo_id}", "/api/v1/analyses", "/api/v1/analyses/{run_id}",
        "/api/v1/analyses/{run_id}/statistics", "/api/v1/analyses/{run_id}/series", "/api/v1/analyses/{run_id}/manifest",
        "/api/v1/analyses/estimate-cost", "/api/v1/me", "/api/v1/me/api-keys", "/api/v1/me/api-keys/{key_id}",
    }
    assert required <= paths, required - paths
