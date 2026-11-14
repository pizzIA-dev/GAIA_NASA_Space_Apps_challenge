"""Adaptadores de datasets NASA en Earth Engine (plan §13.1 `DatasetAdapter`).

Cada adaptador declara metadatos verificables y extrae una serie mensual reducida en el servidor de EE.
Un mes sin imagen o sin píxeles válidos produce `value=None` (faltante), nunca 0.
"""

from __future__ import annotations

import calendar
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from app.services.earth_engine.client import get_ee


@dataclass(frozen=True)
class VariableInfo:
    variable_id: str
    band: str
    physical_quantity: str
    unit_native: str
    unit_display: str
    temporal_aggregations: tuple[str, ...]  # agregaciones anuales válidas: total/mean


@dataclass(frozen=True)
class DatasetInfo:
    dataset_id: str
    ee_collection_id: str
    title: str
    provider: str
    version: str
    nominal_resolution: str
    native_scale_m: float
    temporal_coverage_start: str
    native_granularity: str
    citation_url: str
    license: str
    variables: tuple[VariableInfo, ...]
    status: str = "available"  # available | planned
    notes: tuple[str, ...] = field(default_factory=tuple)

    def variable(self, variable_id: str) -> VariableInfo | None:
        return next((v for v in self.variables if v.variable_id == variable_id), None)


def month_starts(start: date, end_exclusive: date) -> list[date]:
    out, y, m = [], start.year, start.month
    if start.day != 1:
        m += 1
    while True:
        if m > 12:
            y, m = y + 1, 1
        d = date(y, m, 1)
        if d >= end_exclusive:
            return out
        out.append(d)
        m += 1


def hours_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1] * 24


class DatasetAdapter(ABC):
    info: DatasetInfo

    @abstractmethod
    def extract(self, variable_id: str, geometry: dict[str, Any], start: date, end_exclusive: date) -> list[dict]:
        """Devuelve filas (§11.4) mensuales, una por mes esperado, con value=None si falta."""

    def availability(self) -> dict:
        return {"start": self.info.temporal_coverage_start, "end": "ver catálogo GEE (latencia del producto)"}


class IMERGMonthly(DatasetAdapter):
    """GPM IMERG V07 mensual: banda `precipitation` en mm/h (tasa media) → total mensual en mm."""

    info = DatasetInfo(
        dataset_id="nasa-gpm-imerg-monthly-v07",
        ee_collection_id="NASA/GPM_L3/IMERG_MONTHLY_V07",
        title="GPM IMERG Final Precipitation L3 Monthly V07",
        provider="NASA GES DISC / GPM",
        version="V07",
        nominal_resolution="0.1° (~11 km en el ecuador)",
        native_scale_m=11132.0,
        temporal_coverage_start="1998-01-01",
        native_granularity="month",
        citation_url="https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07",
        license="NASA Earth Science data: uso abierto con atribución",
        variables=(
            VariableInfo(
                variable_id="precipitation_mm_month",
                band="precipitation",
                physical_quantity="precipitación total",
                unit_native="mm/h",
                unit_display="mm",
                temporal_aggregations=("total", "mean"),
            ),
        ),
        notes=("Útil para lluvia regional; no resuelve microcuencas ni calles.",),
    )

    def extract(self, variable_id: str, geometry: dict[str, Any], start: date, end_exclusive: date) -> list[dict]:
        var = self.info.variable(variable_id)
        if var is None:
            raise KeyError(variable_id)
        ee = get_ee()
        geom = ee.Geometry(geometry)
        band = var.band
        reducer = ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True)
        col = ee.ImageCollection(self.info.ee_collection_id).filterDate(
            start.isoformat(), end_exclusive.isoformat()
        ).select(band)

        def per_image(img):
            st = img.reduceRegion(
                reducer=reducer, geometry=geom, scale=self.info.native_scale_m, maxPixels=1e9, tileScale=2
            )
            return ee.Feature(None, {
                "t": img.date().format("YYYY-MM-dd"),
                "mean": st.get(f"{band}_mean"),
                "count": st.get(f"{band}_count"),
            })

        feats = col.map(per_image).getInfo()["features"]
        by_month = {f["properties"]["t"][:7]: f["properties"] for f in feats}
        extracted_at = datetime.now(UTC).isoformat()
        rows = []
        for d in month_starts(start, end_exclusive):
            p = by_month.get(d.strftime("%Y-%m"))
            rate = p.get("mean") if p else None
            count = (p.get("count") if p else 0) or 0
            value = None if rate is None else float(rate) * hours_in_month(d)
            flags = [] if p else ["no_image"]
            if p and rate is None:
                flags.append("no_valid_pixels")
            rows.append({
                "time_start_utc": d.isoformat(),
                "period_label": d.strftime("%Y-%m"),
                "variable_id": variable_id,
                "value": value,
                "unit": var.unit_display,
                "valid_pixel_count": count,
                "native_scale_m": self.info.native_scale_m,
                "extraction_scale_m": self.info.native_scale_m,
                "source_dataset_id": self.info.dataset_id,
                "ee_collection_id": self.info.ee_collection_id,
                "product_version": self.info.version,
                "extracted_at": extracted_at,
                "quality_flags": flags,
            })
        return rows


def _planned(dataset_id, ee_id, title, version, res, scale, start, gran, url, variables, notes=()):
    return DatasetInfo(
        dataset_id=dataset_id, ee_collection_id=ee_id, title=title, provider="NASA", version=version,
        nominal_resolution=res, native_scale_m=scale, temporal_coverage_start=start, native_granularity=gran,
        citation_url=url, license="NASA Earth Science data: uso abierto con atribución", variables=variables,
        status="planned", notes=notes,
    )


# Datasets del registro inicial (plan §14.2). IDs verificados contra la procedencia del estudio previo; su
# adaptador está pendiente (requieren composición mensual en EE de colecciones sub-mensuales).
PLANNED: tuple[DatasetInfo, ...] = (
    _planned("nasa-gldas-noah-v21-3h", "NASA/GLDAS/V021/NOAH/G025/T3H", "GLDAS Noah 2.1 3-horario", "2.1",
             "0.25° (~28 km)", 27830.0, "2000-01-01", "3h",
             "https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H",
             (VariableInfo("soil_moisture_0_10cm_kgm2", "SoilMoi0_10cm_inst", "humedad del suelo 0–10 cm",
                           "kg/m²", "kg/m²", ("mean",)),
              VariableInfo("air_temperature_c", "Tair_f_inst", "temperatura del aire", "K", "°C", ("mean",))),
             ("Malla gruesa: varios distritos pueden compartir celda.",)),
    _planned("nasa-merra2-slv", "NASA/GSFC/MERRA/slv/2", "MERRA-2 single-level diagnostics", "M2T1NXSLV",
             "0.5° × 0.625°", 55000.0, "1980-01-01", "1h",
             "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_slv_2",
             (VariableInfo("air_temperature_2m_c", "T2M", "temperatura a 2 m", "K", "°C", ("mean",)),
              VariableInfo("total_precipitable_water_kgm2", "TQV", "vapor de agua total", "kg/m²", "kg/m²",
                           ("mean",)))),
    _planned("nasa-modis-mod13q1-061", "MODIS/061/MOD13Q1", "MODIS Terra NDVI 16 días 250 m", "061",
             "250 m", 250.0, "2000-02-18", "16d",
             "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1",
             (VariableInfo("ndvi", "NDVI", "índice de vegetación", "escala ×0.0001", "adimensional", ("mean",)),)),
    _planned("nasa-modis-aqua-sst-l3smi", "NASA/OCEANDATA/MODIS-Aqua/L3SMI", "MODIS-Aqua SST L3 (no MUR)", "L3SMI",
             "4 km", 4616.0, "2002-07-04", "1d",
             "https://developers.google.com/earth-engine/datasets/catalog/NASA_OCEANDATA_MODIS-Aqua_L3SMI",
             (VariableInfo("sst_c", "sst", "temperatura superficial del mar", "°C", "°C", ("mean",)),),
             ("Usar región oceánica real, no el polígono terrestre.",)),
)

ADAPTERS: dict[str, DatasetAdapter] = {a.info.dataset_id: a for a in (IMERGMonthly(),)}


def catalog() -> list[DatasetInfo]:
    return [a.info for a in ADAPTERS.values()] + list(PLANNED)
