"""Orquestador de análisis: spec → extracción (con caché) → transformaciones → estadística → run persistido.

Mismo código para web, REST y SDK (plan §12A). Caché de extracción separada de la estadística (§11.5):
cambiar IC o método reutiliza la serie ya extraída sin volver a Earth Engine.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.schemas.analysis import AnalysisSpec, extraction_key, geometry_hash, sha256_of, spec_hash
from app.services.earth_engine.adapters import ADAPTERS, DatasetAdapter
from app.services.geographies.geoboundaries import GeographyNotFound
from app.services.geographies.peru_ign import BoundariesNotIngested
from app.services.geographies.registry import GeographyRegistry
from app.services.geographies.registry import registry as default_registry
from app.services.statistics.trend_core import ALGORITHM_VERSION, TrendSettings, estimate_trend


class AnalysisError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail


class RunStore:
    def __init__(self, root: Path):
        self.root = root

    def _p(self, kind: str, key: str) -> Path:
        safe = key.replace("sha256:", "")
        return self.root / kind / f"{safe}.json"

    def get(self, kind: str, key: str) -> dict | None:
        p = self._p(kind, key)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def put(self, kind: str, key: str, obj: dict) -> None:
        p = self._p(kind, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        tmp.replace(p)


@dataclass
class ResolvedGeography:
    geometry: Any  # GeoJSON dict (ROI libre) o referencia con .to_ee(ee) (frontera versionada)
    geometry_hash: str
    info: dict


def resolve_geometry(spec: AnalysisSpec, geographies: GeographyRegistry | None = None) -> ResolvedGeography:
    g = spec.geography
    if g.custom_geometry is not None:
        return ResolvedGeography(g.custom_geometry, geometry_hash(g.custom_geometry),
                                 {"kind": "custom_roi", "area_km2": None})
    reg = geographies or default_registry
    try:
        geo = reg.get(g.geo_ids[0])
    except GeographyNotFound as exc:
        raise AnalysisError(404, "unknown_geography", f"geo_id no encontrado: {g.geo_ids[0]}") from exc
    except BoundariesNotIngested as exc:
        raise AnalysisError(503, "source_unavailable", str(exc)) from exc
    if g.boundary_set_id not in (None, geo.boundary_set_id):
        raise AnalysisError(422, "boundary_set_mismatch",
                            f"{g.geo_ids[0]} pertenece a {geo.boundary_set_id}, no a {g.boundary_set_id}")
    ref = reg.ref(geo)
    try:
        identity = ref.identity()
    except BoundariesNotIngested as exc:
        raise AnalysisError(503, "source_unavailable", str(exc)) from exc
    return ResolvedGeography(ref, sha256_of(identity),
                             {"kind": "boundary", **geo.to_dict(), "attribution": reg.attribution(geo.boundary_set_id)})


def to_granularity(rows: list[dict], spec: AnalysisSpec) -> tuple[pd.DataFrame, list[str]]:
    df = pd.DataFrame(rows)[["time_start_utc", "value", "unit"]]
    df["time_start_utc"] = pd.to_datetime(df["time_start_utc"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    warnings: list[str] = []

    if spec.transforms.seasonality == "monthly_anomaly":
        if spec.time.granularity != "month":
            raise AnalysisError(409, "incompatible_method", "monthly_anomaly requiere granularity=month")
        b0 = pd.Timestamp(spec.transforms.baseline_start or spec.time.start)
        b1 = pd.Timestamp(spec.transforms.baseline_end_exclusive or spec.time.end_exclusive)
        base = df[(df.time_start_utc >= b0) & (df.time_start_utc < b1)]
        clim = base.groupby(base.time_start_utc.dt.month)["value"].mean()
        if clim.isna().any() or len(clim) < 12:
            warnings.append("Climatología base incompleta para algún mes: esas anomalías quedan nulas")
        df["value"] = df["value"] - df.time_start_utc.dt.month.map(clim)
        warnings.append(f"Anomalía mensual respecto a climatología {b0.date()}–{b1.date()} (exclusivo)")

    if spec.time.granularity == "year":
        g = df.groupby(df.time_start_utc.dt.year)
        agg = g["value"].sum(min_count=1) if spec.time.temporal_aggregation == "total" else g["value"].mean()
        complete = g["value"].apply(lambda s: s.notna().sum() == 12)
        n_incomplete = int((~complete).sum())
        agg[~complete] = float("nan")
        if n_incomplete:
            warnings.append(f"{n_incomplete} año(s) incompletos excluidos del total/medio anual (no se rellenan)")
        df = pd.DataFrame({
            "time_start_utc": pd.to_datetime([f"{y}-01-01" for y in agg.index]),
            "value": agg.to_numpy(),
            "unit": rows[0]["unit"] if rows else "",
        })
    return df, warnings


@dataclass
class PreparedRun:
    """Análisis validado y normalizado, listo para ejecutarse. Permite decidir cuotas/costes antes de tocar EE."""

    spec: AnalysisSpec
    adapter: DatasetAdapter
    var: Any
    s_hash: str
    run_id: str
    store: RunStore
    cached_run: dict | None
    geo: ResolvedGeography | None = None
    x_key: str | None = None
    extraction_cached: bool = False

    @property
    def needs_extraction(self) -> bool:
        return self.cached_run is None and not self.extraction_cached


def prepare(spec: AnalysisSpec, store: RunStore | None = None,
            adapters: dict[str, DatasetAdapter] | None = None,
            geographies: GeographyRegistry | None = None) -> PreparedRun:
    store = store or RunStore(settings.cache_dir)
    adapters = adapters if adapters is not None else ADAPTERS
    adapter = adapters.get(spec.data.dataset_id)
    if adapter is None:
        raise AnalysisError(404, "unknown_dataset", f"Dataset no disponible: {spec.data.dataset_id}")
    var = adapter.info.variable(spec.data.variable_id)
    if var is None:
        raise AnalysisError(404, "unknown_variable", f"Variable no disponible: {spec.data.variable_id}")
    if spec.time.temporal_aggregation is None:
        # Normalizar ANTES del hash: omitirla y declarar la agregación por defecto producen el mismo run_id.
        spec = spec.model_copy(update={
            "time": spec.time.model_copy(update={"temporal_aggregation": var.temporal_aggregations[0]})
        })
    if spec.time.temporal_aggregation not in var.temporal_aggregations:
        raise AnalysisError(409, "incompatible_method",
                            f"Agregación '{spec.time.temporal_aggregation}' no válida para {var.variable_id}")
    if spec.time.start < date.fromisoformat(adapter.info.temporal_coverage_start):
        raise AnalysisError(422, "insufficient_coverage",
                            f"El producto empieza en {adapter.info.temporal_coverage_start}")

    s_hash = spec_hash(spec, ALGORITHM_VERSION)
    run_id = "run_" + s_hash.split(":")[1][:20]
    p = PreparedRun(spec, adapter, var, s_hash, run_id, store, store.get("runs", run_id))
    if p.cached_run is None:
        p.geo = resolve_geometry(spec, geographies)
        p.x_key = extraction_key(spec, adapter.info.version)
        p.extraction_cached = store.get("extractions", p.x_key) is not None
    return p


def execute(p: PreparedRun, extraction_gate=None) -> dict:
    """Ejecuta un PreparedRun. `extraction_gate` (context manager) limita extracciones concurrentes en EE."""
    if p.cached_run is not None:
        return {**p.cached_run, "cache_hit": True}
    spec, adapter, var, geo, store, x_key = p.spec, p.adapter, p.var, p.geo, p.store, p.x_key
    extraction = store.get("extractions", x_key)
    extraction_cache_hit = extraction is not None
    if extraction is None:
        with extraction_gate or nullcontext():
            rows = adapter.extract(var.variable_id, geo.geometry, spec.time.start, spec.time.end_exclusive)
        extraction = {"key": x_key, "rows": rows, "geometry_hash": geo.geometry_hash}
        store.put("extractions", x_key, extraction)
    rows = extraction["rows"]
    if not rows or all(r["value"] is None for r in rows):
        area = geo.info.get("area_km2")
        pixel_km2 = (adapter.info.native_scale_m / 1000.0) ** 2
        cause = (
            f" El territorio ({area:.0f} km²) es mucho menor que una celda de {adapter.info.nominal_resolution} "
            f"(~{pixel_km2:.0f} km²) o cae en una celda enmascarada (p. ej., océano en productos terrestres). "
            "Prueba con la unidad administrativa superior o un ROI mayor; no se extrapola desde celdas vecinas."
            if area is not None and area < pixel_km2
            else " Revisa que el producto cubra este territorio (p. ej., SST solo sobre océano)."
        )
        raise AnalysisError(422, "insufficient_coverage",
                            "Sin píxeles válidos en el territorio para el periodo: cobertura insuficiente." + cause)

    series, transform_warnings = to_granularity(rows, spec)
    st = spec.statistics
    settings_ = TrendSettings(
        estimator=st.estimator, interval_method=st.interval_method, significance_test=st.significance_test,
        confidence_level=st.confidence_level, time_unit=st.time_unit, resamples=st.resamples,
        block_length=st.block_length if spec.time.granularity == "month" else max(1, min(st.block_length, 3)),
        seed=st.seed,
    )
    values = [None if pd.isna(v) else float(v) for v in series["value"]]
    result = estimate_trend(series["time_start_utc"], values, settings_, value_unit=series["unit"].iloc[0])
    stats = result.to_dict()
    support_warnings = []
    area = geo.info.get("area_km2")
    pixel_km2 = (adapter.info.native_scale_m / 1000.0) ** 2
    if area is not None and area < pixel_km2:
        support_warnings.append(
            f"El territorio ({area:.0f} km²) es menor que un píxel nativo (~{pixel_km2:.0f} km²): el valor representa "
            "una celda que excede el territorio, no una medición interna"
        )
    stats["warnings"] = support_warnings + transform_warnings + stats["warnings"]

    run = {
        "run_id": p.run_id,
        "status": "succeeded",
        "cache_hit": False,
        "extraction_cache_hit": extraction_cache_hit,
        "analysis_spec_hash": p.s_hash,
        "request": spec.model_dump(mode="json"),
        "statistics": stats,
        "series": [
            {"time_start_utc": t.date().isoformat(), "value": v}
            for t, v in zip(series["time_start_utc"], values, strict=True)
        ],
        "quality": {
            "coverage": stats["coverage_fraction"],
            "n_observations": stats["n_observations"],
            "spatial_support": f"resolución nativa {adapter.info.nominal_resolution}",
            "warnings": stats["warnings"],
        },
        "source_versions": [{
            "dataset_id": adapter.info.dataset_id,
            "ee_collection_id": adapter.info.ee_collection_id,
            "version": adapter.info.version,
            "band": var.band,
            "native_scale_m": adapter.info.native_scale_m,
        }],
        "geography": geo.info,
        "provenance": {"geometry_hash": extraction["geometry_hash"], "extraction_key": x_key,
                       "extracted_at": rows[0].get("extracted_at")},
        "compute": {"engine": "earth_engine", "algorithm_version": ALGORITHM_VERSION,
                    "completed_at": datetime.now(UTC).isoformat()},
    }
    store.put("runs", p.run_id, run)
    return run


def run_analysis(spec: AnalysisSpec, store: RunStore | None = None,
                 adapters: dict[str, DatasetAdapter] | None = None,
                 geographies: GeographyRegistry | None = None) -> dict:
    """Atajo sin políticas de cuota (scripts, pruebas, SDK local)."""
    return execute(prepare(spec, store, adapters, geographies))
