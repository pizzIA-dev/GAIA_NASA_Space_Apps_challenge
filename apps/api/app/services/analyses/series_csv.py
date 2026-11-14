"""Análisis de una serie ya materializada (CSV con columnas del plan §11.4), sin Earth Engine ni UI.

Criterio de aceptación F0: abrir un CSV, calcular una pendiente de control y explicar fuente, estimador e IC.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.statistics.trend_core import TrendResult, TrendSettings, estimate_trend

REQUIRED_COLUMNS = ("time_start_utc", "value", "unit", "source_dataset_id")
PROVENANCE_COLUMNS = ("variable_id", "geo_id", "product_version", "extracted_at", "native_scale_m")


def load_series_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, keep_default_na=True)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV sin columnas obligatorias: {missing}")
    df["time_start_utc"] = pd.to_datetime(df["time_start_utc"], utc=True)
    return df.sort_values("time_start_utc").reset_index(drop=True)


def _single(df: pd.DataFrame, col: str) -> str | None:
    if col not in df.columns:
        return None
    vals = df[col].dropna().astype(str).unique()
    if len(vals) > 1:
        raise ValueError(f"La serie mezcla varios valores de '{col}': {list(vals)[:5]}")
    return vals[0] if len(vals) else None


def analyze_series_csv(path: str | Path, settings: TrendSettings | None = None) -> dict:
    df = load_series_csv(path)
    unit = _single(df, "unit") or "unit"
    values = [None if pd.isna(v) else float(v) for v in df["value"]]
    result: TrendResult = estimate_trend(df["time_start_utc"], values, settings, value_unit=unit)
    provenance = {"source_dataset_id": _single(df, "source_dataset_id")}
    provenance.update({c: _single(df, c) for c in PROVENANCE_COLUMNS if c in df.columns})
    provenance["period"] = [df["time_start_utc"].min().isoformat(), df["time_start_utc"].max().isoformat()]
    return {
        "statistics": result.to_dict(),
        "provenance": provenance,
        "explanation": explain(result, provenance),
    }


def explain(r: TrendResult, provenance: dict) -> str:
    src = provenance.get("source_dataset_id") or "fuente no declarada"
    if r.status == "insufficient_evidence":
        return f"Fuente: {src}. No se estima tendencia: {'; '.join(r.warnings)}."
    est_name = {"ols": "regresión OLS", "theil_sen": "pendiente de Theil–Sen"}[r.estimator]
    ci = (
        f"IC del {r.confidence_level:.0%} calculado mediante {r.ci_method}: "
        f"[{r.ci_lower:.4g}, {r.ci_upper:.4g}] {r.estimate_unit}"
        if r.ci_lower is not None
        else "sin IC solicitado"
    )
    p = f"p = {r.p_value:.3g} ({r.test_method})" if r.p_value is not None else "sin prueba de significancia"
    tag = " [EXPLORATORIO]" if r.status == "exploratory" else ""
    return (
        f"Fuente: {src}. Estimador: {est_name} = {r.estimate:.4g} {r.estimate_unit}; {ci}; {p}; "
        f"N = {r.n_observations}, faltantes = {r.n_missing}.{tag}"
    )
