"""Geografías administrativas globales ADM0–ADM2 desde geoBoundaries gbOpen v6.0.0 publicado en Earth Engine.

- Fuente: https://www.geoboundaries.org (CC BY 4.0, atribución obligatoria). Colecciones `WM/geoLab/geoBoundaries/600/ADMn`.
- La colección no trae jerarquía: el padre se calcula una vez por país (unidad ADM superior que contiene el punto
  interior de la geometría) y se guarda en un índice local `.cache/geographies/` (solo atributos, sin geometrías).
- El análisis NO descarga la geometría: se filtra la colección por `shapeID` dentro de Earth Engine.
- `geo_id` estable y versionado: `gb6:<ISO3>` (ADM0) o `gb6:<ISO3>:<ADMn>:<shapeID>`. Nunca se une solo por nombre.
"""

from __future__ import annotations

import json
import threading
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings
from app.services.earth_engine.client import get_ee

BOUNDARY_SET_ID = "geoboundaries-gbopen-6.0.0"
EE_ROOT = "WM/geoLab/geoBoundaries/600"
LEVELS = ("ADM0", "ADM1", "ADM2")
ATTRIBUTION = "Límites: geoBoundaries gbOpen v6.0.0 (Runfola et al. 2020), CC BY 4.0"
INDEX_VERSION = 1


class GeographyNotFound(KeyError):
    pass


@dataclass(frozen=True)
class Geography:
    geo_id: str
    name: str
    admin_level: str
    iso3: str
    parent_id: str | None
    area_km2: float | None
    boundary_set_id: str = BOUNDARY_SET_ID

    def to_dict(self) -> dict:
        return asdict(self)


def make_geo_id(iso3: str, level: str, shape_id: str | None = None) -> str:
    return f"gb6:{iso3}" if level == "ADM0" else f"gb6:{iso3}:{level}:{shape_id}"


def parse_geo_id(geo_id: str) -> tuple[str, str, str | None]:
    parts = geo_id.split(":")
    if parts[0] != "gb6" or len(parts) not in (2, 4):
        raise GeographyNotFound(geo_id)
    if len(parts) == 2:
        return parts[1], "ADM0", None
    if parts[2] not in LEVELS[1:]:
        raise GeographyNotFound(geo_id)
    return parts[1], parts[2], parts[3]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(t.replace("-", " ").split())


class GeoBoundariesRef:
    """Referencia perezosa a la geometría en Earth Engine (usada por los adaptadores)."""

    def __init__(self, geo: Geography):
        self.geo = geo

    def to_ee(self, ee):
        iso3, level, shape_id = parse_geo_id(self.geo.geo_id)
        fc = ee.FeatureCollection(f"{EE_ROOT}/{level}").filter(ee.Filter.eq("shapeGroup", iso3))
        if shape_id:
            fc = fc.filter(ee.Filter.eq("shapeID", shape_id))
        return fc.geometry()

    def identity(self) -> dict:
        return {"geo_id": self.geo.geo_id, "boundary_set_id": self.geo.boundary_set_id}


class GeoBoundariesIndex:
    def __init__(self, cache_dir: Path | None = None):
        self.dir = (cache_dir or settings.cache_dir) / "geographies"
        self._lock = threading.Lock()
        self._mem: dict[str, list[Geography]] = {}

    # ------------------------------------------------------------ construcción (Earth Engine)

    def _path(self, key: str) -> Path:
        return self.dir / f"{BOUNDARY_SET_ID}_v{INDEX_VERSION}_{key}.json"

    def _load(self, key: str, builder) -> list[Geography]:
        if key in self._mem:
            return self._mem[key]
        with self._lock:
            p = self._path(key)
            if p.is_file():
                rows = json.loads(p.read_text(encoding="utf-8"))
            else:
                rows = builder()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            self._mem[key] = [Geography(**r) for r in rows]
        return self._mem[key]

    def countries(self) -> list[Geography]:
        def build():
            ee = get_ee()
            fc = ee.FeatureCollection(f"{EE_ROOT}/ADM0")
            info = fc.reduceColumns(ee.Reducer.toList(2), ["shapeGroup", "shapeName"]).get("list").getInfo()
            return [Geography(make_geo_id(iso, "ADM0"), name, "ADM0", iso, None, None).to_dict()
                    for iso, name in sorted(info)]
        return self._load("ADM0", build)

    def country(self, iso3: str) -> list[Geography]:
        iso3 = iso3.upper()
        if not any(c.iso3 == iso3 for c in self.countries()):
            raise GeographyNotFound(iso3)

        def build():
            ee = get_ee()
            rows: list[dict] = []
            adm0 = ee.FeatureCollection(f"{EE_ROOT}/ADM0").filter(ee.Filter.eq("shapeGroup", iso3))
            area0 = adm0.geometry().area(maxError=1000).divide(1e6).getInfo()
            name0 = next(c.name for c in self.countries() if c.iso3 == iso3)
            rows.append(Geography(make_geo_id(iso3, "ADM0"), name0, "ADM0", iso3, None, round(area0, 1)).to_dict())
            parent_fc = None
            for level in ("ADM1", "ADM2"):
                fc = ee.FeatureCollection(f"{EE_ROOT}/{level}").filter(ee.Filter.eq("shapeGroup", iso3))

                def attrs(f, parent_fc=parent_fc):
                    g = f.geometry()
                    props = {"area_km2": g.area(maxError=100).divide(1e6)}
                    if parent_fc is not None:
                        # Punto interior robusto (el centroide puede caer fuera en polígonos cóncavos).
                        pt = g.centroid(maxError=100)
                        pt = ee.Geometry(ee.Algorithms.If(g.contains(pt, 100), pt, g.buffer(-100, 100).centroid(100)))
                        by_point = parent_fc.filterBounds(pt)
                        # Respaldo si los bordes ADM1/ADM2 no coinciden: mayor área de intersección.
                        by_overlap = parent_fc.filterBounds(g).map(
                            lambda par, g=g: par.set("_ov", par.geometry().intersection(g, 100).area(100))
                        ).sort("_ov", False)
                        best = ee.Algorithms.If(by_point.size().gt(0), by_point.first(), by_overlap.first())
                        props["parent_shapeID"] = ee.Algorithms.If(
                            best, ee.Feature(best).get("shapeID"), None
                        )
                    return ee.Feature(None, props).copyProperties(f, ["shapeID", "shapeName"])

                feats = fc.map(attrs).getInfo()["features"]
                for ft in feats:
                    p = ft["properties"]
                    parent = (make_geo_id(iso3, "ADM1", p["parent_shapeID"]) if level == "ADM2"
                              and p.get("parent_shapeID") else make_geo_id(iso3, "ADM0"))
                    rows.append(Geography(make_geo_id(iso3, level, p["shapeID"]), p["shapeName"], level, iso3,
                                          parent, round(p["area_km2"], 2)).to_dict())
                parent_fc = fc
            return rows

        return self._load(iso3, build)

    # ------------------------------------------------------------ consulta

    def get(self, geo_id: str) -> Geography:
        iso3, _, _ = parse_geo_id(geo_id)
        for g in self.country(iso3):
            if g.geo_id == geo_id:
                return g
        raise GeographyNotFound(geo_id)

    def search(self, q: str, country: str | None = None, level: str | None = None, limit: int = 20) -> list[dict]:
        nq = normalize(q)
        pool = self.country(country) if country else self.countries()
        by_id = {g.geo_id: g for g in pool}
        out = []
        for g in pool:
            if level and g.admin_level != level:
                continue
            ng = normalize(g.name)
            if nq not in ng:
                continue
            rank = 0 if ng == nq else 1 if ng.startswith(nq) else 2
            path, cur = [], by_id.get(g.parent_id) if g.parent_id else None
            while cur is not None:
                path.append(cur.name)
                cur = by_id.get(cur.parent_id) if cur.parent_id else None
            out.append((rank, LEVELS.index(g.admin_level), g.name, {**g.to_dict(), "path": list(reversed(path))}))
        out.sort(key=lambda r: r[:3])
        return [r[3] for r in out[:limit]]

    def geometry_geojson(self, geo_id: str, max_error_m: float = 500.0) -> dict:
        ee = get_ee()
        geom = GeoBoundariesRef(self.get(geo_id)).to_ee(ee).simplify(maxError=max_error_m)
        return geom.getInfo()


index = GeoBoundariesIndex()
