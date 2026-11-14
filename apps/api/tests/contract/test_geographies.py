"""Geografías (geoBoundaries + IGN Perú) con índices precargados, sin Earth Engine.
IDs, áreas y geometrías son ILUSTRATIVOS de prueba."""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import routes
from app.main import app
from app.services.analyses.runner import RunStore
from app.services.geographies import geoboundaries as gb
from app.services.geographies import peru_ign as pe
from app.services.geographies.registry import GeographyRegistry
from tests.contract.test_analyses_api import FakeIMERG, make_spec

PER = "gb6:PER"
LL = "gb6:PER:ADM1:T1"
TRU = "gb6:PER:ADM2:T2"
TINY = "gb6:PER:ADM2:T3"


def row(geo_id, name, level, parent, area):
    return gb.Geography(geo_id, name, level, "PER", parent, area).to_dict()


@pytest.fixture
def geos(tmp_path):
    d = tmp_path / "geographies"
    d.mkdir()
    pre = f"{gb.BOUNDARY_SET_ID}_v{gb.INDEX_VERSION}_"
    (d / f"{pre}ADM0.json").write_text(json.dumps([row(PER, "Peru", "ADM0", None, None),
                                                   gb.Geography("gb6:CHL", "Chile", "ADM0", "CHL", None, None)
                                                   .to_dict()]), encoding="utf-8")
    (d / f"{pre}PER.json").write_text(json.dumps([
        row(PER, "Peru", "ADM0", None, 1285000.0),
        row(LL, "La Libertad", "ADM1", PER, 25338.1),
        row(TRU, "Trujillo", "ADM2", LL, 1782.0),
        row(TINY, "Ancón Chico", "ADM2", LL, 40.0),
    ]), encoding="utf-8")
    return GeographyRegistry(gb.GeoBoundariesIndex(tmp_path), pe.PeruIGNIndex(tmp_path / "no-ingestado"))


SQ = {"type": "Polygon", "coordinates": [[[-79.05, -8.12], [-79.0, -8.12], [-79.0, -8.08], [-79.05, -8.12]]]}


@pytest.fixture
def pe_geos(tmp_path, geos):
    root = tmp_path / "pe"
    (root / "geoms").mkdir(parents=True)
    units = [
        {"ubigeo": "13", "name": "La Libertad", "admin_level": "ADM1", "parent_ubigeo": None, "area_km2": 25500.0},
        {"ubigeo": "1301", "name": "Trujillo", "admin_level": "ADM2", "parent_ubigeo": "13", "area_km2": 1769.0},
        {"ubigeo": "130101", "name": "Trujillo", "admin_level": "ADM3", "parent_ubigeo": "1301", "area_km2": 38.2},
        {"ubigeo": "130111", "name": "Victor Larco Herrera", "admin_level": "ADM3", "parent_ubigeo": "1301",
         "area_km2": 11.8},
    ]
    for u in units:
        (root / "geoms" / f"{u['ubigeo']}.json").write_text(json.dumps(SQ), encoding="utf-8")
    (root / "index.json").write_text(json.dumps({"source": {"boundary_set_id": pe.BOUNDARY_SET_ID}, "units": units}),
                                     encoding="utf-8")
    return GeographyRegistry(geos.gb, pe.PeruIGNIndex(root))


@pytest.fixture
def client(tmp_path, geos):
    fake = FakeIMERG()
    app.dependency_overrides[routes.get_geographies] = lambda: geos
    app.dependency_overrides[routes.get_store] = lambda: RunStore(tmp_path / "runs")
    app.dependency_overrides[routes.get_adapters] = lambda: {"nasa-gpm-imerg-monthly-v07": fake}
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def test_geo_id_roundtrip():
    assert gb.parse_geo_id(gb.make_geo_id("PER", "ADM2", "X1")) == ("PER", "ADM2", "X1")
    assert gb.parse_geo_id("gb6:PER") == ("PER", "ADM0", None)
    with pytest.raises(gb.GeographyNotFound):
        gb.parse_geo_id("PER-130101")


def test_search_accent_insensitive_with_path(geos):
    res = geos.gb.search("ancon", country="PER")
    assert res[0]["geo_id"] == TINY and res[0]["path"] == ["Peru", "La Libertad"]
    assert geos.gb.search("TRUJ", country="per")[0]["geo_id"] == TRU


def test_search_without_country_only_countries(geos):
    assert [r["geo_id"] for r in geos.gb.search("peru")] == [PER]


def test_endpoints_search_and_detail(client):
    c, _ = client
    r = c.get("/api/v1/geographies/search", params={"q": "trujillo", "country": "PER"}).json()
    assert r["items"][0]["geo_id"] == TRU and "CC BY 4.0" in r["attribution"]
    d = c.get(f"/api/v1/geographies/{LL}").json()
    assert {ch["geo_id"] for ch in d["children"]} == {TRU, TINY}
    assert c.get("/api/v1/geographies/gb6:PER:ADM2:NOPE").status_code == 404
    assert c.get("/api/v1/geographies/search", params={"q": "x", "country": "PER"}).status_code == 422


def test_analysis_by_geo_id_uses_ee_reference(client):
    c, _fake = client
    spec = make_spec()
    spec["geography"] = {"geo_ids": [TRU]}
    run = c.post("/api/v1/analyses", json=spec).json()
    assert run["status"] == "succeeded"
    assert run["geography"]["geo_id"] == TRU and run["geography"]["kind"] == "boundary"
    assert run["provenance"]["geometry_hash"].startswith("sha256:")
    assert not any("píxel nativo" in w for w in run["statistics"]["warnings"])


def test_tiny_territory_warns_about_native_pixel(client):
    c, _ = client
    spec = make_spec()
    spec["geography"] = {"geo_ids": [TINY]}
    run = c.post("/api/v1/analyses", json=spec).json()
    assert any("menor que un píxel nativo" in w for w in run["statistics"]["warnings"])


def test_unknown_geo_and_boundary_set(client):
    c, _ = client
    spec = make_spec()
    spec["geography"] = {"geo_ids": ["gb6:PER:ADM2:NOPE"]}
    assert c.post("/api/v1/analyses", json=spec).status_code == 404
    spec["geography"] = {"geo_ids": [TRU], "boundary_set_id": "inei-2017"}
    assert c.post("/api/v1/analyses", json=spec).status_code == 422


# ---------------------------------------------------------------- IGN Perú (fuente oficial por defecto)


def test_pe_geo_id_parse():
    assert pe.parse_geo_id("pe-ign2020:130101") == "130101"
    for bad in ("pe-ign2020:1301011", "pe-ign2020:13A", "gb6:PER"):
        with pytest.raises(gb.GeographyNotFound):
            pe.parse_geo_id(bad)


def test_peru_defaults_to_official_and_gb_on_request(pe_geos):
    used, items = pe_geos.search("trujillo", country="PER")
    assert used == pe.BOUNDARY_SET_ID
    assert [i["admin_level"] for i in items] == ["ADM2", "ADM3"]
    assert items[1]["path"] == ["Perú", "La Libertad", "Trujillo"] and items[1]["ubigeo"] == "130101"
    used, items = pe_geos.search("trujillo", country="PER", boundary_set_id=gb.BOUNDARY_SET_ID)
    assert used == gb.BOUNDARY_SET_ID and items[0]["geo_id"] == TRU


def test_search_by_ubigeo(pe_geos):
    _, items = pe_geos.search("130111", country="PER")
    assert items[0]["name"] == "Victor Larco Herrera"


def test_peru_falls_back_visibly_when_not_ingested(geos):
    used, _ = geos.search("trujillo", country="PER")
    assert used == gb.BOUNDARY_SET_ID


def test_pe_ref_sends_original_geometry_and_hashes_it(pe_geos):
    ref = pe_geos.ref(pe_geos.get("pe-ign2020:130101"))
    assert ref.geojson() == SQ
    assert ref.identity()["geometry_sha256"].startswith("sha256:")


def test_analysis_by_district_warns_small_support(tmp_path, pe_geos):
    fake = FakeIMERG()
    app.dependency_overrides[routes.get_geographies] = lambda: pe_geos
    app.dependency_overrides[routes.get_store] = lambda: RunStore(tmp_path / "runs")
    app.dependency_overrides[routes.get_adapters] = lambda: {"nasa-gpm-imerg-monthly-v07": fake}
    try:
        c = TestClient(app)
        spec = make_spec()
        spec["geography"] = {"geo_ids": ["pe-ign2020:130101"]}
        run = c.post("/api/v1/analyses", json=spec).json()
        assert run["geography"]["boundary_set_id"] == pe.BOUNDARY_SET_ID and "IGN" in run["geography"]["attribution"]
        assert any("menor que un píxel nativo" in w for w in run["statistics"]["warnings"])
        spec["geography"]["boundary_set_id"] = gb.BOUNDARY_SET_ID
        assert c.post("/api/v1/analyses", json=spec).status_code == 422
        d = c.get("/api/v1/geographies/pe-ign2020:1301", params={"geometry": "simplified"}).json()
        assert {ch["geo_id"] for ch in d["children"]} == {"pe-ign2020:130101", "pe-ign2020:130111"}
        assert d["geometry"]["type"] == "Polygon"
    finally:
        app.dependency_overrides.clear()
