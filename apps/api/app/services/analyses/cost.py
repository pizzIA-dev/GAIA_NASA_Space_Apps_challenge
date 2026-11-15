"""Estimación de complejidad de un análisis (plan §12.2): NO es una factura de Earth Engine.

Dos factores dominan el tiempo observado (sesión 2):
- imágenes fuente a componer (MERRA-2 horario ≈ 730/mes → minutos aunque el ROI sea pequeño);
- píxel-imágenes = imágenes × píxeles del ROI a la escala de extracción (NDVI 500 m sobre áreas grandes).
Coeficientes calibrados con mediciones reales; se informan como orientativos.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from app.core.config import settings
from app.services.analyses.runner import PreparedRun
from app.services.earth_engine.adapters import month_starts

IMAGES_PER_MONTH = {"month": 1, "3h": 243, "1h": 730, "16d": 2, "1d": 30}
# Calibración (s): MERRA-2 22 años ≈ 1,9e5 imágenes → 100–210 s; GLDAS ≈ 6,4e4 → ~60 s; NDVI provincia ≈ 9 s.
SEC_OVERHEAD, SEC_PER_IMAGE, SEC_PER_PIXEL_IMAGE = 3.0, 8e-4, 2e-7


@dataclass(frozen=True)
class CostEstimate:
    tier: str  # cached | light | heavy | too_large
    cache: str  # run | extraction | none
    months: int
    source_images: int
    roi_area_km2: float | None
    pixels_at_extraction_scale: float
    pixel_images: float
    extraction_scale_m: float
    estimated_seconds: float
    reason: str
    note: str = "Estimación orientativa de complejidad, no facturación de Earth Engine ni tiempo garantizado."

    def to_dict(self) -> dict:
        return asdict(self)


def polygon_area_km2(geojson: dict) -> float:
    """Área aproximada de un Polygon/MultiPolygon EPSG:4326 (proyección equivalente local por coseno de latitud)."""
    from shapely.geometry import shape

    g = shape(geojson)
    lat = g.centroid.y
    km_per_deg = 111.32
    return abs(g.area) * km_per_deg * km_per_deg * math.cos(math.radians(lat))


def estimate(p: PreparedRun) -> CostEstimate:
    info = p.adapter.info
    scale_m = float(getattr(p.adapter, "extraction_scale_m", info.native_scale_m))
    months = len(month_starts(p.spec.time.start, p.spec.time.end_exclusive))
    images = months * IMAGES_PER_MONTH.get(info.native_granularity, 30)

    area = None
    if p.geo is not None:
        area = p.geo.info.get("area_km2")
        if area is None and p.spec.geography.custom_geometry is not None:
            area = round(polygon_area_km2(p.spec.geography.custom_geometry), 2)
    pixels = max(1.0, (area or 0.0) / (scale_m / 1000.0) ** 2)
    pixel_images = images * pixels
    seconds = SEC_OVERHEAD + SEC_PER_IMAGE * images + SEC_PER_PIXEL_IMAGE * pixel_images

    common = {"months": months, "source_images": images, "roi_area_km2": area, "pixels_at_extraction_scale": round(pixels, 1),
                  "pixel_images": float(f"{pixel_images:.3g}"), "extraction_scale_m": scale_m}
    if p.cached_run is not None:
        return CostEstimate("cached", "run", estimated_seconds=0.1, reason="Resultado ya calculado", **common)
    if p.extraction_cached:
        return CostEstimate("cached", "extraction", estimated_seconds=1.0,
                            reason="Serie NASA en caché; solo se recalcula la estadística", **common)
    s = settings
    if area is not None and area > s.max_roi_area_km2:
        return CostEstimate("too_large", "none", estimated_seconds=round(seconds, 1),
                            reason=f"ROI de {area:,.0f} km² supera el máximo de {s.max_roi_area_km2:,.0f} km²", **common)
    if images > s.heavy_max_images or pixel_images > s.heavy_max_pixel_images:
        return CostEstimate("too_large", "none", estimated_seconds=round(seconds, 1),
                            reason="Supera el límite por análisis: reduce el periodo, el área o usa granularidad anual "
                                   "de un producto mensual", **common)
    if images > s.light_max_images or pixel_images > s.light_max_pixel_images:
        return CostEstimate("heavy", "none", estimated_seconds=round(seconds, 1),
                            reason="Extracción pesada en Earth Engine (requiere token de API)", **common)
    return CostEstimate("light", "none", estimated_seconds=round(seconds, 1), reason="Extracción ligera", **common)
