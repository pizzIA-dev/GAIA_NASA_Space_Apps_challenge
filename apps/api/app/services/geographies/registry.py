"""Registro de conjuntos de fronteras: enruta cada geo_id a su fuente versionada.

Política (plan §3.1): para Perú se usa por defecto la fuente oficial (IGN, ADM1–ADM3); geoBoundaries sigue disponible
pidiéndolo explícitamente con `boundary_set_id`. Nunca se sustituye una por otra en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.geographies import geoboundaries as gb
from app.services.geographies import peru_ign as pe
from app.services.geographies.geoboundaries import Geography, GeographyNotFound

OFFICIAL_DEFAULT = {"PER": pe.BOUNDARY_SET_ID}


@dataclass
class BoundarySetInfo:
    boundary_set_id: str
    attribution: str
    levels: tuple[str, ...]
    countries: str


class GeographyRegistry:
    def __init__(self, gb_index: gb.GeoBoundariesIndex | None = None, pe_index: pe.PeruIGNIndex | None = None):
        self.gb = gb_index or gb.index
        self.pe = pe_index or pe.index

    def boundary_sets(self) -> list[dict]:
        out = [BoundarySetInfo(gb.BOUNDARY_SET_ID, gb.ATTRIBUTION, gb.LEVELS, "global").__dict__]
        if self.pe.available:
            out.append(BoundarySetInfo(pe.BOUNDARY_SET_ID, pe.ATTRIBUTION, pe.LEVELS, "PER").__dict__)
        return out

    def attribution(self, boundary_set_id: str) -> str:
        return pe.ATTRIBUTION if boundary_set_id == pe.BOUNDARY_SET_ID else gb.ATTRIBUTION

    def _is_pe(self, geo_id: str) -> bool:
        return geo_id.startswith(pe.PREFIX + ":")

    def countries(self) -> list[Geography]:
        return self.gb.countries()

    def get(self, geo_id: str) -> Geography:
        return self.pe.get(geo_id) if self._is_pe(geo_id) else self.gb.get(geo_id)

    def ref(self, geo: Geography):
        return self.pe.ref(geo) if geo.boundary_set_id == pe.BOUNDARY_SET_ID else gb.GeoBoundariesRef(geo)

    def children(self, geo: Geography) -> list[Geography]:
        if geo.boundary_set_id == pe.BOUNDARY_SET_ID:
            return [g for g in self.pe.all() if g.parent_id == geo.geo_id]
        kids = [g for g in self.gb.country(geo.iso3) if g.parent_id == geo.geo_id]
        if geo.admin_level == "ADM0" and geo.iso3 in OFFICIAL_DEFAULT and self.pe.available:
            kids = [g for g in self.pe.all() if g.admin_level == "ADM1"]
        return kids

    def search(self, q: str, country: str | None = None, level: str | None = None,
               boundary_set_id: str | None = None, limit: int = 20) -> tuple[str, list[dict]]:
        """Devuelve (boundary_set_id usado, resultados)."""
        iso = country.upper() if country else None
        chosen = boundary_set_id or (OFFICIAL_DEFAULT.get(iso) if iso else None) or gb.BOUNDARY_SET_ID
        if chosen == pe.BOUNDARY_SET_ID:
            if iso not in (None, "PER"):
                raise GeographyNotFound(f"{chosen} solo cubre PER")
            if not self.pe.available:
                chosen = gb.BOUNDARY_SET_ID  # se informa en la respuesta, no se oculta
            else:
                return chosen, self.pe.search(q, level=level, limit=limit)
        if chosen != gb.BOUNDARY_SET_ID:
            raise GeographyNotFound(chosen)
        return chosen, self.gb.search(q, country=iso, level=level, limit=limit)

    def path(self, geo: Geography) -> list[str]:
        """Ancestros legibles (sin incluir el propio territorio), p. ej. ["Perú", "La Libertad"]."""
        if geo.boundary_set_id == pe.BOUNDARY_SET_ID:
            return self.pe.path(geo)
        by_id = {g.geo_id: g for g in self.gb.country(geo.iso3)}
        out, cur = [], by_id.get(geo.parent_id) if geo.parent_id else None
        while cur is not None:
            out.append(cur.name)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return list(reversed(out))

    def geometry_geojson(self, geo_id: str) -> dict:
        return self.pe.geometry_geojson(geo_id) if self._is_pe(geo_id) else self.gb.geometry_geojson(geo_id)


registry = GeographyRegistry()
