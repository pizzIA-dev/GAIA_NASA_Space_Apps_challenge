"""Caso Trujillo con los datos oficiales versionados (data/case-trujillo, generados por la ingesta)."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.cases import trujillo

c = TestClient(app)


def test_reconciliation_with_historical_reference():
    s = c.get("/api/v1/cases/trujillo-el-nino").json()
    assert s["reconciliation"]["official_2017_2025"] == 16 and s["reconciliation"]["status"] == "coincide"
    assert len(s["reconciliation"]["official_districts_2017_2025"]) == 8
    assert s["counts"]["duplicates_by_code"] == 0 and s["counts"]["dates_not_day_precision"] == 0
    assert s["enfen_rule"]["status"] == "umbral_citado_pendiente_de_verificacion"
    assert any("Alto Trujillo" in lim for lim in s["limitations"])


def test_no_event_has_verified_causality():
    ev = c.get("/api/v1/cases/trujillo-el-nino/events").json()["items"]
    assert ev and all(e["causal_attribution"]["status"] == "no_verificada" for e in ev)
    assert not any(e["display_class"] == "atribucion_verificada" for e in ev)


def test_2017_events_coincide_with_el_nino_costero_2017_but_2018_with_la_nina():
    ev = {e["sinpad_code"]: e for e in c.get("/api/v1/cases/trujillo-el-nino/events?year_from=2017&year_to=2018").json()["items"]}
    assert ev["84509"]["enfen"]["episode_id"] == "EN-COSTERO-2017"
    assert ev["84509"]["display_class"] == "coincidencia_el_nino"
    assert ev["92871"]["enfen"]["context"] == "coincidencia_la_nina_costera"  # Moche, marzo 2018
    assert ev["92871"]["display_class"] == "fuera_de_el_nino"


def test_mixed_date_formats_resolved_with_official_month():
    ev = {e["sinpad_code"]: e for e in trujillo.events(year_from=2025)}
    assert ev["217169"]["date"] == "2025-01-09" and ev["217169"]["date_raw"] == "01/09/25"


def test_filter_by_district_and_unknown_geo():
    r = c.get("/api/v1/cases/trujillo-el-nino/events?geo_id=pe-ign2020:130111&year_from=2017").json()
    assert r["count"] == 6 and {e["district"] for e in r["items"]} == {"Victor Larco Herrera"}
    assert c.get("/api/v1/cases/trujillo-el-nino/events?geo_id=pe-ign2020:1501").status_code == 422
    assert c.get("/api/v1/cases/otro-caso").status_code == 404


def test_enfen_series_and_episodes():
    r = c.get("/api/v1/cases/trujillo-el-nino/enfen?year_from=2017&year_to=2017").json()
    assert len(r["series"]) == 12
    ids = {e["id"] for e in r["episodes"]}
    assert "EN-COSTERO-2017" in ids and all(e["derived"] for e in r["episodes"])


def test_association_endpoint_with_simulated_series(tmp_path):
    """Panel con series simuladas (sin EE) y eventos oficiales: estructura, avisos y política de familia."""
    import json as _json

    from app.api.v1 import routes
    from app.services.analyses.runner import RunStore
    from tests.contract.test_analyses_api import FakeIMERG
    from tests.contract.test_geographies import SQ

    root = tmp_path / "pe"
    (root / "geoms").mkdir(parents=True)
    units = [{"ubigeo": "1301", "name": "Trujillo", "admin_level": "ADM2", "parent_ubigeo": None, "area_km2": 1769.0}] + [
        {"ubigeo": u, "name": n, "admin_level": "ADM3", "parent_ubigeo": "1301", "area_km2": 50.0}
        for u, n in [("130111", "Victor Larco Herrera"), ("130104", "Huanchaco"), ("130110", "Simbal")]]
    for u in units:
        (root / "geoms" / f"{u['ubigeo']}.json").write_text(_json.dumps(SQ), encoding="utf-8")
    (root / "index.json").write_text(_json.dumps({"source": {}, "units": units}), encoding="utf-8")
    from app.services.geographies import geoboundaries as gb
    from app.services.geographies import peru_ign as pe
    from app.services.geographies.registry import GeographyRegistry

    reg = GeographyRegistry(gb.GeoBoundariesIndex(tmp_path), pe.PeruIGNIndex(root))
    app.dependency_overrides.update({routes.get_geographies: lambda: reg,
                                     routes.get_store: lambda: RunStore(tmp_path / "s"),
                                     routes.get_adapters: lambda: {"nasa-gpm-imerg-monthly-v07": FakeIMERG()}})
    try:
        r = c.post("/api/v1/cases/trujillo-el-nino/association", json={"resamples": 199, "lags": [0, 1]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["n_units"] == 3 and len(body["results"]) == 2
        assert body["results"][0]["n_event_months"] > 0 and "q_value" in body["results"][0]
        assert body["events_excluded_no_geometry"] > 0  # eventos de distritos fuera del panel (p. ej. Alto Trujillo)
        assert any("no capacidad de anticipación" in w for w in body["warnings"])
        assert c.post("/api/v1/cases/trujillo-el-nino/association", json={"lags": [20]}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_backtest_is_out_of_sample_and_counts_false_alarms():
    """Escena 5: regla principal declarada, umbrales de 2017–2021, prueba 2022–2025, tabla completa (no solo aciertos)."""
    r = c.get("/api/v1/cases/trujillo-el-nino/backtest")
    assert r.status_code == 200
    b = r.json()
    assert b["primary_declared_before_results"] is True
    rule = b["primary"]["rule"]
    assert (rule["percentile"], rule["window_days"], rule["horizon_days"]) == trujillo.BACKTEST_PRIMARY
    assert b["periods"] == {"calibration": list(trujillo.BACKTEST_TRAIN), "test": list(trujillo.BACKTEST_TEST)}
    t = b["primary"]["test_out_of_sample"]
    k = t["contingency"]
    assert k["tp"] + k["fp"] + k["fn"] + k["tn"] == t["unit_days_evaluated"] > 10000  # 11 distritos × 4 años
    assert all(e["date"] >= "2022-01-01" for e in t["events_detail"])
    # Los registros 2022–2025 con polígono IGN: Simbal 2023, Moche 2024, Víctor Larco Herrera 2025 (control v12)
    assert {(e["date"], e["unit"]) for e in t["events_detail"]} == {("2023-04-07", "130110"), ("2024-07-14", "130107"),
                                                                    ("2025-01-09", "130111")}
    assert any(e["district"] == "Alto Trujillo" and e["reason"] == "sin polígono IGN" for e in b["events_excluded"])
    assert len(b["grid"]) == 27
    assert any("POTENCIAL retrospectiva" in w for w in b["warnings"])
    assert any("Solo 3 registros" in w for w in b["warnings"])
