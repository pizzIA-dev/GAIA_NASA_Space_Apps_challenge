"""Fronteras oficiales del Perú ADM1–ADM3 (IGN, vía OCHA HDX COD-AB), con UBIGEO.

Generadas por `scripts/ingest_pe_boundaries.py` en `.cache/boundaries/pe-ign2020/`. Las geometrías se envían a Earth
Engine sin simplificar (máx. ~1,1 MB por unidad). `geo_id = pe-ign2020:<UBIGEO>` (2, 4 o 6 dígitos).
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.schemas.analysis import sha256_of
from app.services.geographies.geoboundaries import Geography, GeographyNotFound, normalize

BOUNDARY_SET_ID = "pe-ign-cod-ab-2020"
PREFIX = "pe-ign2020"
ATTRIBUTION = ("Límites: Instituto Geográfico Nacional (IGN) del Perú, vía OCHA HDX COD-AB (v01, válido desde "
               "2020-07-14), CC BY-IGO")
LEVELS = ("ADM1", "ADM2", "ADM3")


class BoundariesNotIngested(RuntimeError):
    """Falta ejecutar scripts/ingest_pe_boundaries.py."""


def make_geo_id(ubigeo: str) -> str:
    return f"{PREFIX}:{ubigeo}"


def parse_geo_id(geo_id: str) -> str:
    prefix, _, code = geo_id.partition(":")
    if prefix != PREFIX or not code.isdigit() or len(code) not in (2, 4, 6):
        raise GeographyNotFound(geo_id)
    return code


class PeruGeomRef:
    """Geometría oficial enviada a Earth Engine tal cual (sin simplificar)."""

    def __init__(self, geo: Geography, geoms_dir: Path):
        self.geo = geo
        self._path = geoms_dir / f"{parse_geo_id(geo.geo_id)}.json"

    def geojson(self) -> dict:
        if not self._path.is_file():
            raise BoundariesNotIngested(f"Geometría de {self.geo.geo_id} no ingerida: ejecuta scripts/ingest_pe_boundaries.py")
        return json.loads(self._path.read_text(encoding="utf-8"))

    def to_ee(self, ee):
        return ee.Geometry(self.geojson(), proj="EPSG:4326", geodesic=False)

    def identity(self) -> dict:
        return {"geo_id": self.geo.geo_id, "boundary_set_id": self.geo.boundary_set_id,
                "geometry_sha256": sha256_of(self.geojson())}


class PeruIGNIndex:
    def __init__(self, root: Path | None = None):
        self.root = root or (settings.cache_dir / "boundaries" / "pe-ign2020")
        self._lock = threading.Lock()
        self._units: dict[str, Geography] | None = None
        self.source: dict = {}

    @property
    def available(self) -> bool:
        return (self.root / "index.json").is_file()

    def _load(self) -> dict[str, Geography]:
        if self._units is None:
            with self._lock:
                if self._units is None:
                    if not self.available:
                        raise BoundariesNotIngested("Ejecuta scripts/ingest_pe_boundaries.py")
                    data = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
                    self.source = data["source"]
                    self._units = {
                        make_geo_id(u["ubigeo"]): Geography(
                            make_geo_id(u["ubigeo"]), u["name"], u["admin_level"], "PER",
                            make_geo_id(u["parent_ubigeo"]) if u["parent_ubigeo"] else None,
                            u["area_km2"], BOUNDARY_SET_ID,
                        )
                        for u in data["units"]
                    }
        return self._units

    def all(self) -> list[Geography]:
        return list(self._load().values())

    def get(self, geo_id: str) -> Geography:
        parse_geo_id(geo_id)
        try:
            return self._load()[geo_id]
        except KeyError as exc:
            raise GeographyNotFound(geo_id) from exc

    def path(self, g: Geography) -> list[str]:
        units, out, cur = self._load(), [], g.parent_id
        while cur:
            p = units[cur]
            out.append(p.name)
            cur = p.parent_id
        return ["Perú", *reversed(out)]

    def search(self, q: str, level: str | None = None, limit: int = 20) -> list[dict]:
        nq = normalize(q)
        hits = []
        for g in self._load().values():
            if level and g.admin_level != level:
                continue
            ng = normalize(g.name)
            code = parse_geo_id(g.geo_id)
            if nq in ng or q.strip() == code:
                rank = 0 if (ng == nq or q.strip() == code) else 1 if ng.startswith(nq) else 2
                hits.append((rank, LEVELS.index(g.admin_level), g.name, g))
        hits.sort(key=lambda h: h[:3])
        return [{**g.to_dict(), "ubigeo": parse_geo_id(g.geo_id), "path": self.path(g)} for *_, g in hits[:limit]]

    def ref(self, g: Geography) -> PeruGeomRef:
        return PeruGeomRef(g, self.root / "geoms")

    def geometry_geojson(self, geo_id: str, tolerance_deg: float = 0.002) -> dict:
        """Geometría simplificada (~200 m) SOLO para visualización; el análisis usa la original."""
        return _simplified(str(self.ref(self.get(geo_id))._path), tolerance_deg)


@lru_cache(maxsize=256)
def _simplified(path: str, tolerance_deg: float) -> dict:
    from shapely.geometry import mapping, shape

    if not Path(path).is_file():
        raise BoundariesNotIngested(f"Geometría no ingerida ({Path(path).name}): ejecuta scripts/ingest_pe_boundaries.py")
    geom = json.loads(Path(path).read_text(encoding="utf-8"))
    return mapping(shape(geom).simplify(tolerance_deg, preserve_topology=True))


index = PeruIGNIndex()
