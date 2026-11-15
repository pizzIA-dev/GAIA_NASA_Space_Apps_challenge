"""Ciclo estacional: valores analíticos con serie SINTÉTICA y endpoint sobre un run (sin Earth Engine)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import routes
from app.main import app
from app.services.analyses.runner import RunStore
from app.services.analyses.seasonal import seasonal_summary
from app.services.earth_engine.adapters import month_starts
from tests.contract.test_analyses_api import FakeIMERG, make_spec


def rows(missing=()):
    out = []
    for d in month_starts(date(2001, 1, 1), date(2004, 1, 1)):  # 3 años
        v = None if (d.year, d.month) in missing else float(d.month * 10 + (d.year - 2001))
        out.append({"time_start_utc": d.isoformat(), "value": v})
    return out


def test_matrix_and_climatology_are_exact():
    s = seasonal_summary(rows(), "mm")
    assert s["years"] == [2001, 2002, 2003] and len(s["matrix"]) == 3 and len(s["matrix"][0]) == 12
    assert s["matrix"][1][2] == 31.0  # marzo 2002 = 3*10 + 1
    mar = s["climatology"][2]
    assert (mar["mean"], mar["median"], mar["min"], mar["max"], mar["n_valid"]) == (31.0, 31.0, 30.0, 32.0, 3)
    assert mar["p25"] == pytest.approx(30.5) and mar["p75"] == pytest.approx(31.5)
    assert s["peak_month"] == "dic" and s["low_month"] == "ene"
    assert s["extremes"][0]["label"] == "dic 2003" and s["extremes"][0]["anomaly"] == pytest.approx(1.0)


def test_missing_months_stay_null_and_are_counted():
    s = seasonal_summary(rows(missing={(2002, 3)}), "mm")
    assert s["matrix"][1][2] is None and s["n_missing"] == 1
    mar = s["climatology"][2]
    assert mar["n_valid"] == 2 and mar["n_years"] == 3 and mar["mean"] == pytest.approx(31.0)


def test_month_without_any_data_has_null_stats():
    s = seasonal_summary(rows(missing={(y, 5) for y in (2001, 2002, 2003)}), "mm")
    may = s["climatology"][4]
    assert may["n_valid"] == 0 and may["mean"] is None and may["p25"] is None


def test_seasonal_endpoint_uses_cached_extraction(tmp_path):
    fake = FakeIMERG()
    app.dependency_overrides[routes.get_store] = lambda: RunStore(tmp_path)
    app.dependency_overrides[routes.get_adapters] = lambda: {"nasa-gpm-imerg-monthly-v07": fake}
    try:
        c = TestClient(app)
        spec = make_spec()
        spec["time"] = {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"}
        run = c.post("/api/v1/analyses", json=spec).json()
        s = c.get(f"/api/v1/analyses/{run['run_id']}/seasonal").json()
        assert len(s["years"]) == 22 and len(s["climatology"]) == 12 and s["unit"] == "mm"
        assert fake.calls == 1  # no volvió a extraer
        assert c.get("/api/v1/analyses/run_no_existe/seasonal").status_code == 404
    finally:
        app.dependency_overrides.clear()
