"""Política de acceso, costes y límites (plan §12.2, §12.3, §12A.2). Sin Earth Engine."""

import dataclasses

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import routes
from app.core.limits import ExtractionGate, SlidingWindowLimiter
from app.core.security import ApiKeyStore, InvalidToken
from app.main import app
from app.services.analyses import runner
from app.services.analyses.runner import RunStore
from app.services.earth_engine.adapters import MERRA2Monthly
from tests.contract.test_analyses_api import SQUARE, FakeIMERG, make_spec

MERRA_SPEC = {"data": {"dataset_id": "nasa-merra2-slv", "variable_id": "air_temperature_2m_c"},
              "geography": {"custom_geometry": SQUARE},
              "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01"}}


class FakeMERRA(MERRA2Monthly):
    calls = 0

    def extract(self, variable_id, geometry, start, end_exclusive):
        FakeMERRA.calls += 1
        return FakeIMERG().extract(variable_id, geometry, start, end_exclusive)


@pytest.fixture
def ctx(tmp_path):
    keys = ApiKeyStore(tmp_path / "keys.json")
    full, _ = keys.create("completa")
    readonly, _ = keys.create("lectura", ("catalog:read", "runs:read"))
    limiter = SlidingWindowLimiter(3600.0)
    gate = ExtractionGate(2, wait_s=0.01)
    adapters = {"nasa-gpm-imerg-monthly-v07": FakeIMERG(), "nasa-merra2-slv": FakeMERRA()}
    app.dependency_overrides.update({
        routes.get_store: lambda: RunStore(tmp_path / "store"),
        routes.get_adapters: lambda: adapters,
        routes.get_key_store: lambda: keys,
        routes.get_limiter: lambda: limiter,
        routes.get_gate: lambda: gate,
    })
    yield TestClient(app), keys, {"Authorization": f"Bearer {full}"}, {"Authorization": f"Bearer {readonly}"}, gate
    app.dependency_overrides.clear()


def test_token_store_hashes_and_revokes(tmp_path):
    keys = ApiKeyStore(tmp_path / "k.json")
    token, rec = keys.create("x")
    assert token not in (tmp_path / "k.json").read_text()  # solo hash en disco
    assert keys.verify(token).subject == rec.key_id
    keys.revoke(rec.key_id)
    with pytest.raises(InvalidToken, match="revocado"):
        keys.verify(token)
    with pytest.raises(InvalidToken):
        keys.verify("ets_" + rec.key_id + "_falso")


def test_me_anonymous_and_key(ctx):
    c, _, full, _, _ = ctx
    anon = c.get("/api/v1/me").json()
    assert anon["kind"] == "anonymous" and anon["limits"]["allowed_tiers"] == ["cached", "light"]
    me = c.get("/api/v1/me", headers=full).json()
    assert me["kind"] == "api_key" and "heavy" in me["limits"]["allowed_tiers"]
    assert c.get("/api/v1/me", headers={"Authorization": "Bearer ets_x_y"}).status_code == 401


def test_estimate_cost_tiers(ctx):
    c, _, full, _, _ = ctx
    light = c.post("/api/v1/analyses/estimate-cost", json=make_spec()).json()
    assert light["cost"]["tier"] == "light" and light["allowed"]
    heavy = c.post("/api/v1/analyses/estimate-cost", json=MERRA_SPEC).json()
    assert heavy["cost"]["tier"] == "heavy" and heavy["cost"]["source_images"] == 264 * 730
    assert not heavy["allowed"] and heavy["denied"]["code"] == "token_required"
    assert c.post("/api/v1/analyses/estimate-cost", json=MERRA_SPEC, headers=full).json()["allowed"]


def test_anonymous_light_ok_heavy_needs_token(ctx):
    c, _, full, _, _ = ctx
    assert c.post("/api/v1/analyses", json=make_spec()).status_code == 200
    r = c.post("/api/v1/analyses", json=MERRA_SPEC)
    assert r.status_code == 401 and r.json()["title"] == "token_required" and r.json()["cost"]["tier"] == "heavy"
    ok = c.post("/api/v1/analyses", json=MERRA_SPEC, headers=full)
    assert ok.status_code == 200 and ok.json()["cost"]["tier"] == "heavy"
    # Una vez calculado, el resultado es 'cached' y cualquiera puede consultarlo/reproducirlo.
    again = c.post("/api/v1/analyses", json=MERRA_SPEC)
    assert again.status_code == 200 and again.json()["cache_hit"] and again.json()["cost"]["tier"] == "cached"


def test_readonly_scope_forbidden(ctx):
    c, _, _, readonly, _ = ctx
    r = c.post("/api/v1/analyses", json=make_spec(), headers=readonly)
    assert r.status_code == 403 and r.json()["title"] == "scope_forbidden"


def test_too_large_is_413(ctx):
    c, _, full, _, _ = ctx
    world = {"type": "Polygon", "coordinates": [[[-80, -60], [80, -60], [80, 60], [-80, 60], [-80, -60]]]}
    spec = make_spec() | {"geography": {"custom_geometry": world}}
    r = c.post("/api/v1/analyses", json=spec, headers=full)
    assert r.status_code == 413 and r.json()["title"] == "area_too_large"


def test_rate_limit_counts_only_new_extractions(ctx, monkeypatch):
    c, *_ = ctx
    monkeypatch.setattr(runner, "settings", dataclasses.replace(runner.settings, anon_extractions_per_hour=1))
    assert c.post("/api/v1/analyses", json=make_spec()).status_code == 200
    assert c.post("/api/v1/analyses", json=make_spec(confidence_level=0.9)).status_code == 200  # misma extracción
    spec2 = make_spec() | {"time": {"start": "2005-01-01", "end_exclusive": "2025-01-01"}}
    r = c.post("/api/v1/analyses", json=spec2)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0 and r.json()["title"] == "quota_exceeded"


def test_busy_earth_engine_is_503_with_retry_after(ctx):
    c, _, _, _, gate = ctx
    with gate.slot(), gate.slot():  # ocupar los 2 cupos
        r = c.post("/api/v1/analyses", json=make_spec())
    assert r.status_code == 503 and r.json()["title"] == "source_busy" and r.headers["Retry-After"] == "30"


def test_auth_mode_required(ctx, monkeypatch):
    c, _, full, _, _ = ctx
    monkeypatch.setattr(runner, "settings", dataclasses.replace(runner.settings, auth_mode="required"))
    assert c.post("/api/v1/analyses", json=make_spec()).status_code == 401
    assert c.post("/api/v1/analyses", json=make_spec(), headers=full).status_code == 200
    assert c.get("/api/v1/catalog/variables").status_code == 200  # el catálogo sigue siendo público


def test_my_api_keys_and_self_revoke(ctx):
    c, _, full, _, _ = ctx
    mine = c.get("/api/v1/me/api-keys", headers=full).json()["items"]
    assert len(mine) == 1 and "token_sha256" not in mine[0]
    kid = mine[0]["key_id"]
    assert c.delete(f"/api/v1/me/api-keys/{kid}", headers=full).json()["revoked"]
    assert c.get("/api/v1/me", headers=full).status_code == 401
