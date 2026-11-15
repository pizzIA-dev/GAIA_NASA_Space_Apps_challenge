"""Contrato canónico `analysis_spec` (plan §11.2) y hashes reproducibles (§11.5)."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataSpec(_Strict):
    dataset_id: str
    variable_id: str
    quality_policy: Literal["valid_only"] = "valid_only"


class GeographySpec(_Strict):
    geo_ids: list[str] = Field(default_factory=list)
    boundary_set_id: str | None = None
    custom_geometry: dict[str, Any] | None = Field(
        default=None, description="GeoJSON Polygon/MultiPolygon en EPSG:4326 (ROI libre)"
    )
    spatial_reducer: Literal["mean_area_weighted"] = "mean_area_weighted"

    @model_validator(mode="after")
    def _one_source(self) -> GeographySpec:
        if bool(self.geo_ids) == bool(self.custom_geometry):
            raise ValueError("Indica exactamente uno: geo_ids o custom_geometry")
        if len(self.geo_ids) > 1:
            raise ValueError("Un análisis de tendencia usa un solo territorio; usa /analyses/compare para varios")
        if self.custom_geometry is not None and self.custom_geometry.get("type") not in ("Polygon", "MultiPolygon"):
                raise ValueError("custom_geometry debe ser GeoJSON Polygon o MultiPolygon")
        return self


class TimeSpec(_Strict):
    start: date
    end_exclusive: date
    granularity: Literal["month", "year"] = "month"
    temporal_aggregation: Literal["total", "mean"] | None = Field(
        None, description="None = la agregación por defecto de la variable (total para precipitación, media para el resto)"
    )

    @model_validator(mode="after")
    def _order(self) -> TimeSpec:
        if self.end_exclusive <= self.start:
            raise ValueError("end_exclusive debe ser posterior a start")
        return self


class TransformSpec(_Strict):
    seasonality: Literal["none", "monthly_anomaly"] = "none"
    baseline_start: date | None = None
    baseline_end_exclusive: date | None = None
    missing_values: Literal["preserve_null"] = "preserve_null"


class StatisticsSpec(_Strict):
    estimator: Literal["ols", "theil_sen"] = "theil_sen"
    interval_method: Literal[
        "ols_classic", "hac_newey_west", "theil_sen_analytic", "moving_block_bootstrap"
    ] = "theil_sen_analytic"
    confidence_level: float = Field(0.95, gt=0.5, lt=1.0)
    significance_test: Literal["ols_t", "ols_hac_t", "mann_kendall", "none"] = "mann_kendall"
    time_unit: Literal["year", "decade"] = "decade"
    resamples: int = Field(1000, ge=100, le=5000)
    block_length: int = Field(12, ge=1, le=120)
    seed: int = 2026
    multiple_testing: Literal["none", "BH_FDR"] = "none"
    family_id: str | None = None


class AnalysisSpec(_Strict):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    analysis_type: Literal["trend"] = "trend"
    data: DataSpec
    geography: GeographySpec
    time: TimeSpec
    transforms: TransformSpec = Field(default_factory=TransformSpec)
    statistics: StatisticsSpec = Field(default_factory=StatisticsSpec)
    presentation: dict[str, Any] = Field(default_factory=dict)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_of(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def geometry_hash(geometry: dict[str, Any]) -> str:
    return sha256_of(geometry)


def extraction_key(spec: AnalysisSpec, source_version: str) -> str:
    """Caché raster: solo lo que cambia la extracción (no IC, no método)."""
    d = spec.model_dump(mode="json")
    return sha256_of({
        "data": d["data"],
        "source_version": source_version,
        "geography": d["geography"],
        "time": {"start": d["time"]["start"], "end_exclusive": d["time"]["end_exclusive"]},
    })


def spec_hash(spec: AnalysisSpec, algorithm_version: str) -> str:
    """Hash completo del análisis (excluye `presentation`, que no altera números)."""
    d = spec.model_dump(mode="json")
    d.pop("presentation", None)
    d["algorithm_version"] = algorithm_version
    return sha256_of(d)
