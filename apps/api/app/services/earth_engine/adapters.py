"""Adaptadores de datasets NASA en Earth Engine (plan §13.1 `DatasetAdapter`).

Cada adaptador declara metadatos verificables y extrae una serie mensual reducida en el servidor de EE.
Un mes sin imagen o sin píxeles válidos produce `value=None` (faltante), nunca 0.
"""

from __future__ import annotations

import calendar
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, ClassVar

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
    def extract(self, variable_id: str, geometry: Any, start: date, end_exclusive: date) -> list[dict]:
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

    def extract(self, variable_id: str, geometry: Any, start: date, end_exclusive: date) -> list[dict]:
        var = self.info.variable(variable_id)
        if var is None:
            raise KeyError(variable_id)
        ee = get_ee()
        geom = geometry.to_ee(ee) if hasattr(geometry, "to_ee") else ee.Geometry(geometry)
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


@dataclass(frozen=True)
class BandRecipe:
    """Cómo convertir una banda nativa en la variable publicada (todo dentro de Earth Engine)."""

    band: str
    scale_factor: float = 1.0  # p. ej. NDVI ×0.0001
    offset: float = 0.0  # p. ej. K → °C: −273.15 (se aplica después del factor)
    qa_band: str | None = None
    qa_max: int | None = None  # conservar píxeles con qa_band <= qa_max


class MonthlyCompositeAdapter(DatasetAdapter):
    """Colección sub-mensual → media mensual por píxel en EE → reducción espacial ponderada por área.

    Procesa en bloques de `block_years` (una llamada getInfo por bloque) para no reiniciar 20 años si falla uno.
    Registra el número de imágenes fuente por mes (`source_image_count`) y píxeles válidos (`valid_pixel_count`).
    """

    recipes: ClassVar[dict[str, BandRecipe]]
    extraction_scale_m: float
    block_years: int = 4

    def _month_image(self, ee, recipe: BandRecipe, d: date):
        start = ee.Date(d.isoformat())
        end = start.advance(1, "month")
        col = ee.ImageCollection(self.info.ee_collection_id).filterDate(start, end)

        def prep(img):
            out = img.select(recipe.band).multiply(recipe.scale_factor).add(recipe.offset)
            if recipe.qa_band is not None:
                out = out.updateMask(img.select(recipe.qa_band).lte(recipe.qa_max))
            return out.rename("v")

        n = col.size()
        composite = ee.Image(ee.Algorithms.If(
            n.gt(0), col.map(prep).mean().rename("v"), ee.Image.constant(0).updateMask(0).rename("v")
        ))
        return composite.set({"t": d.isoformat(), "n": n})

    def extract(self, variable_id: str, geometry: Any, start: date, end_exclusive: date) -> list[dict]:
        var = self.info.variable(variable_id)
        if var is None:
            raise KeyError(variable_id)
        recipe = self.recipes[variable_id]
        ee = get_ee()
        geom = geometry.to_ee(ee) if hasattr(geometry, "to_ee") else ee.Geometry(geometry)
        reducer = ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True)
        months = month_starts(start, end_exclusive)
        props: dict[str, dict] = {}
        for b in range(0, len(months), 12 * self.block_years):
            block = months[b:b + 12 * self.block_years]
            imgs = ee.ImageCollection.fromImages([self._month_image(ee, recipe, d) for d in block])

            def per_image(img):
                st = img.reduceRegion(reducer=reducer, geometry=geom, scale=self.extraction_scale_m,
                                      maxPixels=1e10, tileScale=4)
                return ee.Feature(None, {"t": img.get("t"), "n": img.get("n"),
                                         "mean": st.get("v_mean"), "count": st.get("v_count")})

            for f in imgs.map(per_image).getInfo()["features"]:
                props[f["properties"]["t"]] = f["properties"]
        return self.rows_from_props(variable_id, months, props)

    def rows_from_props(self, variable_id: str, months: list[date], props: dict[str, dict]) -> list[dict]:
        """Convierte resultados de EE en filas §11.4 (separado para poder probarlo sin red)."""
        var = self.info.variable(variable_id)
        product_start = date.fromisoformat(self.info.temporal_coverage_start)
        extracted_at = datetime.now(UTC).isoformat()
        rows = []
        for d in months:
            p = props.get(d.isoformat(), {})
            n_src = int(p.get("n") or 0)
            mean = p.get("mean")
            flags = []
            if n_src == 0:
                flags.append("no_image")
            elif mean is None:
                flags.append("no_valid_pixels")
            if d < product_start < (d.replace(year=d.year + 1, month=1) if d.month == 12
                                    else d.replace(month=d.month + 1)):
                flags.append("partial_month_product_start")
            rows.append({
                "time_start_utc": d.isoformat(), "period_label": d.strftime("%Y-%m"), "variable_id": variable_id,
                "value": None if mean is None else float(mean), "unit": var.unit_display,
                "source_image_count": n_src, "valid_pixel_count": p.get("count") or 0,
                "native_scale_m": self.info.native_scale_m, "extraction_scale_m": self.extraction_scale_m,
                "source_dataset_id": self.info.dataset_id, "ee_collection_id": self.info.ee_collection_id,
                "product_version": self.info.version, "extracted_at": extracted_at, "quality_flags": flags,
            })
        return rows


_NASA_LICENSE = "NASA Earth Science data: uso abierto con atribución"
_CAT = "https://developers.google.com/earth-engine/datasets/catalog/"


class GLDASMonthly(MonthlyCompositeAdapter):
    info = DatasetInfo(
        dataset_id="nasa-gldas-noah-v21-3h", ee_collection_id="NASA/GLDAS/V021/NOAH/G025/T3H",
        title="GLDAS Noah Land Surface Model L4 3-hourly 0.25° V2.1 (media mensual)", provider="NASA GES DISC",
        version="2.1", nominal_resolution="0.25° (~28 km)", native_scale_m=27830.0,
        temporal_coverage_start="2000-01-01", native_granularity="3h",
        citation_url=_CAT + "NASA_GLDAS_V021_NOAH_G025_T3H", license=_NASA_LICENSE,
        variables=(
            VariableInfo("soil_moisture_0_10cm_kgm2", "SoilMoi0_10cm_inst", "humedad del suelo 0–10 cm (modelo)",
                         "kg/m²", "kg/m²", ("mean",)),
            VariableInfo("air_temperature_c", "Tair_f_inst", "temperatura del aire (forzante del modelo)",
                         "K", "°C", ("mean",)),
        ),
        notes=("Producto modelado, no observación directa.", "Malla gruesa: varios distritos pueden compartir celda.",
               "Celdas costeras pueden quedar enmascaradas (océano)."),
    )
    recipes: ClassVar[dict[str, BandRecipe]] = {"soil_moisture_0_10cm_kgm2": BandRecipe("SoilMoi0_10cm_inst"),
               "air_temperature_c": BandRecipe("Tair_f_inst", offset=-273.15)}
    extraction_scale_m = 27830.0
    block_years = 4


class MERRA2Monthly(MonthlyCompositeAdapter):
    info = DatasetInfo(
        dataset_id="nasa-merra2-slv", ee_collection_id="NASA/GSFC/MERRA/slv/2",
        title="MERRA-2 M2T1NXSLV single-level diagnostics horario (media mensual)", provider="NASA GMAO",
        version="M2T1NXSLV", nominal_resolution="0.5° × 0.625° (~55 × 69 km)", native_scale_m=69500.0,
        temporal_coverage_start="1980-01-01", native_granularity="1h",
        citation_url=_CAT + "NASA_GSFC_MERRA_slv_2", license=_NASA_LICENSE,
        variables=(
            VariableInfo("air_temperature_2m_c", "T2M", "temperatura del aire a 2 m (reanálisis)", "K", "°C",
                         ("mean",)),
            VariableInfo("total_precipitable_water_kgm2", "TQV", "vapor de agua precipitable total", "kg/m²",
                         "kg/m²", ("mean",)),
            VariableInfo("wind_u_10m_ms", "U10M", "viento zonal a 10 m", "m/s", "m/s", ("mean",)),
            VariableInfo("wind_v_10m_ms", "V10M", "viento meridional a 10 m", "m/s", "m/s", ("mean",)),
        ),
        notes=("Reanálisis atmosférico de gran escala; no caracteriza microcuencas.",),
    )
    recipes: ClassVar[dict[str, BandRecipe]] = {"air_temperature_2m_c": BandRecipe("T2M", offset=-273.15),
               "total_precipitable_water_kgm2": BandRecipe("TQV"),
               "wind_u_10m_ms": BandRecipe("U10M"), "wind_v_10m_ms": BandRecipe("V10M")}
    extraction_scale_m = 69500.0
    block_years = 4


class MODISNDVIMonthly(MonthlyCompositeAdapter):
    info = DatasetInfo(
        dataset_id="nasa-modis-mod13q1-061", ee_collection_id="MODIS/061/MOD13Q1",
        title="MODIS Terra Vegetation Indices 16-Day 250 m (media mensual)", provider="NASA LP DAAC",
        version="061", nominal_resolution="250 m", native_scale_m=250.0,
        temporal_coverage_start="2000-02-18", native_granularity="16d",
        citation_url=_CAT + "MODIS_061_MOD13Q1", license=_NASA_LICENSE,
        variables=(VariableInfo("ndvi", "NDVI", "índice de vegetación de diferencia normalizada",
                                "entero ×0.0001", "adimensional", ("mean",)),),
        notes=("QA: solo píxeles con SummaryQA ≤ 1 (bueno o marginal).",
               "Extracción a 500 m para controlar coste; resolución nativa 250 m."),
    )
    recipes: ClassVar[dict[str, BandRecipe]] = {"ndvi": BandRecipe("NDVI", scale_factor=0.0001, qa_band="SummaryQA", qa_max=1)}
    extraction_scale_m = 500.0
    block_years = 6


class MODISAquaSSTMonthly(MonthlyCompositeAdapter):
    info = DatasetInfo(
        dataset_id="nasa-modis-aqua-sst-l3smi", ee_collection_id="NASA/OCEANDATA/MODIS-Aqua/L3SMI",
        title="MODIS-Aqua Ocean L3 SMI SST diaria 4 km (media mensual; no MUR)", provider="NASA OB.DAAC",
        version="L3SMI", nominal_resolution="4 km", native_scale_m=4616.0,
        temporal_coverage_start="2002-07-04", native_granularity="1d",
        citation_url=_CAT + "NASA_OCEANDATA_MODIS-Aqua_L3SMI", license=_NASA_LICENSE,
        variables=(VariableInfo("sst_c", "sst", "temperatura superficial del mar", "°C", "°C", ("mean",)),),
        notes=("Usar una región oceánica real; sobre tierra no hay datos (cobertura insuficiente).",
               "Nubes reducen píxeles válidos: revisar valid_pixel_count."),
    )
    recipes: ClassVar[dict[str, BandRecipe]] = {"sst_c": BandRecipe("sst")}
    extraction_scale_m = 4616.0
    block_years = 6


ADAPTERS: dict[str, DatasetAdapter] = {
    a.info.dataset_id: a
    for a in (IMERGMonthly(), GLDASMonthly(), MERRA2Monthly(), MODISNDVIMonthly(), MODISAquaSSTMonthly())
}


def catalog() -> list[DatasetInfo]:
    return [a.info for a in ADAPTERS.values()]
