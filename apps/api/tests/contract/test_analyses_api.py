"""Contrato /api/v1/analyses con un adaptador simulado (sin Earth Engine). Datos SINTÉTICOS."""


import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.v1 import routes
from app.main import app
from app.schemas.analysis import AnalysisSpec
from app.services.analyses.runner import RunStore
from app.services.earth_engine.adapters import IMERGMonthly, month_starts

SQUARE = {"type": "Polygon", "coordinates": [[[-79.1, -8.2], [-78.9, -8.2], [-78.9, -8.0], [-79.1, -8.0],
                                              [-79.1, -8.2]]]}


class FakeIMERG(IMERGMonthly):
    def __init__(self, missing=()):
        self.calls = 0
        self.missing = set(missing)

    def extract(self, variable_id, geometry, start, end_exclusive):
        self.calls += 1
        rng = np.random.default_rng(0)
        rows = []
        for i, d in enumerate(month_starts(start, end_exclusive)):
            v = 50 + 20 * np.sin(2 * np.pi * d.month / 12) + 0.1 * i + rng.normal(0, 3)
            rows.append({"time_start_utc": d.isoformat(), "value": None if i in self.missing else float(v),
                         "unit": "mm", "extracted_at": "2026-11-14T00:00:00+00:00"})
        return rows


def make_spec(**stats):
    return {
        "data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
        "geography": {"custom_geometry": SQUARE},
        "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "month"},
        "statistics": stats,
    }


@pytest.fixture
def client(tmp_path):
    fake = FakeIMERG()
    app.dependency_overrides[routes.get_store] = lambda: RunStore(tmp_path)
    app.dependency_overrides[routes.get_adapters] = lambda: {"nasa-gpm-imerg-monthly-v07": fake}
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def test_trend_run_and_followup_resources(client):
    c, _fake = client
    r = c.post("/api/v1/analyses", json=make_spec())
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "succeeded" and run["analysis_spec_hash"].startswith("sha256:")
    assert run["statistics"]["estimate_unit"] == "mm/decade"
    assert len(run["series"]) == 264
    rid = run["run_id"]
    assert c.get(f"/api/v1/analyses/{rid}/statistics").json()["estimate"] == run["statistics"]["estimate"]
    assert len(c.get(f"/api/v1/analyses/{rid}/series").json()["series"]) == 264
    assert c.get(f"/api/v1/analyses/{rid}/manifest").json()["source_versions"][0]["band"] == "precipitation"


def test_same_spec_is_cache_hit_and_new_ci_reuses_extraction(client):
    c, fake = client
    first = c.post("/api/v1/analyses", json=make_spec()).json()
    again = c.post("/api/v1/analyses", json=make_spec()).json()
    assert again["cache_hit"] and again["run_id"] == first["run_id"]
    other = c.post("/api/v1/analyses", json=make_spec(confidence_level=0.9)).json()
    assert other["run_id"] != first["run_id"] and other["extraction_cache_hit"]
    assert fake.calls == 1  # cambiar el IC no relanza Earth Engine (§11.5)


def test_incompatible_method_is_409_problem_json(client):
    c, _ = client
    r = c.post("/api/v1/analyses", json=make_spec(estimator="theil_sen", interval_method="hac_newey_west"))
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_invalid_spec_is_422(client):
    c, _ = client
    bad = make_spec()
    bad["geography"] = {"custom_geometry": {"type": "Point", "coordinates": [0, 0]}}
    assert c.post("/api/v1/analyses", json=bad).status_code == 422


def test_unknown_dataset_404(client):
    c, _ = client
    spec = make_spec()
    spec["data"]["dataset_id"] = "nope"
    assert c.post("/api/v1/analyses", json=spec).status_code == 404


def test_annual_totals_exclude_incomplete_years(tmp_path):
    from app.services.analyses.runner import run_analysis

    spec = AnalysisSpec.model_validate(make_spec() | {"time": {"start": "2003-01-01", "end_exclusive": "2025-01-01",
                                                              "granularity": "year"}})
    run = run_analysis(spec, RunStore(tmp_path), {"nasa-gpm-imerg-monthly-v07": FakeIMERG(missing={5})})
    assert run["series"][0]["value"] is None  # 2003 incompleto → nulo, no total parcial
    assert run["statistics"]["n_observations"] == 21
    assert any("incompletos" in w for w in run["statistics"]["warnings"])


def test_monthly_anomaly_removes_seasonality(tmp_path):
    from app.services.analyses.runner import run_analysis

    spec = AnalysisSpec.model_validate(make_spec() | {"transforms": {"seasonality": "monthly_anomaly"}})
    run = run_analysis(spec, RunStore(tmp_path), {"nasa-gpm-imerg-monthly-v07": FakeIMERG()})
    vals = np.array([s["value"] for s in run["series"]])
    assert abs(np.nanmean(vals)) < 1e-9
    assert run["statistics"]["estimate"] == pytest.approx(12.0, abs=1.5)  # 0.1 mm/mes = 12 mm/década
