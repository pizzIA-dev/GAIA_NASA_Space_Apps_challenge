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
