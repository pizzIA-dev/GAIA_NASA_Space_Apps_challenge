"""Orquestador de análisis: spec → extracción (con caché) → transformaciones → estadística → run persistido.

Mismo código para web, REST y SDK (plan §12A). Caché de extracción separada de la estadística (§11.5):
cambiar IC o método reutiliza la serie ya extraída sin volver a Earth Engine.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.schemas.analysis import AnalysisSpec, extraction_key, geometry_hash, spec_hash
from app.services.earth_engine.adapters import ADAPTERS, DatasetAdapter
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


def resolve_geometry(spec: AnalysisSpec) -> dict:
    if spec.geography.custom_geometry is not None:
        return spec.geography.custom_geometry
    raise AnalysisError(
        422, "unknown_geography",
        "Búsqueda por geo_ids aún no implementada (F2: geoBoundaries/INEI). Usa custom_geometry.",
    )


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


def run_analysis(spec: AnalysisSpec, store: RunStore | None = None,
                 adapters: dict[str, DatasetAdapter] | None = None) -> dict:
    store = store or RunStore(settings.cache_dir)
    adapters = adapters if adapters is not None else ADAPTERS
    adapter = adapters.get(spec.data.dataset_id)
    if adapter is None:
        raise AnalysisError(404, "unknown_dataset", f"Dataset no disponible: {spec.data.dataset_id}")
    var = adapter.info.variable(spec.data.variable_id)
    if var is None:
        raise AnalysisError(404, "unknown_variable", f"Variable no disponible: {spec.data.variable_id}")
    if spec.time.temporal_aggregation not in var.temporal_aggregations:
        raise AnalysisError(409, "incompatible_method",
                            f"Agregación '{spec.time.temporal_aggregation}' no válida para {var.variable_id}")
    if spec.time.start < date.fromisoformat(adapter.info.temporal_coverage_start):
        raise AnalysisError(422, "insufficient_coverage",
                            f"El producto empieza en {adapter.info.temporal_coverage_start}")

    s_hash = spec_hash(spec, ALGORITHM_VERSION)
    run_id = "run_" + s_hash.split(":")[1][:20]
    cached = store.get("runs", run_id)
    if cached:
        cached["cache_hit"] = True
        return cached

    geometry = resolve_geometry(spec)
    x_key = extraction_key(spec, adapter.info.version)
    extraction = store.get("extractions", x_key)
    extraction_cache_hit = extraction is not None
    if extraction is None:
        rows = adapter.extract(var.variable_id, geometry, spec.time.start, spec.time.end_exclusive)
        extraction = {"key": x_key, "rows": rows, "geometry_hash": geometry_hash(geometry)}
        store.put("extractions", x_key, extraction)
    rows = extraction["rows"]
    if not rows or all(r["value"] is None for r in rows):
        raise AnalysisError(422, "insufficient_coverage",
                            "Sin píxeles válidos en el ROI para el periodo: cobertura insuficiente")

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
    stats["warnings"] = transform_warnings + stats["warnings"]

    run = {
        "run_id": run_id,
        "status": "succeeded",
        "cache_hit": False,
        "extraction_cache_hit": extraction_cache_hit,
        "analysis_spec_hash": s_hash,
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
        "provenance": {"geometry_hash": extraction["geometry_hash"], "extraction_key": x_key,
                       "extracted_at": rows[0].get("extracted_at")},
        "compute": {"engine": "earth_engine", "algorithm_version": ALGORITHM_VERSION,
                    "completed_at": datetime.now(UTC).isoformat()},
    }
    store.put("runs", run_id, run)
    return run
