"""Criterio de aceptación F0 (plan §14.2): CSV materializado → pendiente + explicación, sin GEE ni UI."""

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.analyses.series_csv import analyze_series_csv


def write_fixture(path):
    rng = np.random.default_rng(42)
    times = pd.date_range("2003-01-01", periods=120, freq="MS", tz="UTC")
    values = 20 + 0.03 * np.arange(120) + rng.normal(0, 0.5, 120)
    df = pd.DataFrame({
        "time_start_utc": times.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "geo_id": "SYNTH-0001",
        "variable_id": "synthetic_temperature_c",
        "value": values,
        "unit": "degC",
        "source_dataset_id": "SYNTHETIC-TEST-ONLY",
        "product_version": "n/a",
    })
    df.loc[5, "value"] = np.nan  # faltante real, no cero
    df.to_csv(path, index=False)


def test_csv_to_trend_with_explanation(tmp_path):
    f = tmp_path / "serie.csv"
    write_fixture(f)
    out = analyze_series_csv(f)
    st = out["statistics"]
    assert st["status"] == "ok"
    assert st["n_missing"] == 1
    assert 3.0 < st["estimate"] < 4.6  # 0.03/mes = 0.36/año = 3.6/década
    assert st["ci_lower"] < st["estimate"] < st["ci_upper"]
    assert out["provenance"]["source_dataset_id"] == "SYNTHETIC-TEST-ONLY"
    assert "Theil–Sen" in out["explanation"] and "IC del 95%" in out["explanation"]


def test_health_and_capabilities():
    c = TestClient(app)
    assert c.get("/api/v1/health").json()["status"] == "ok"
    caps = c.get("/api/v1/catalog/capabilities").json()
    assert "theil_sen_analytic" in caps["estimators"]["theil_sen"]["interval_methods"]
    assert "hac_newey_west" not in caps["estimators"]["theil_sen"]["interval_methods"]
