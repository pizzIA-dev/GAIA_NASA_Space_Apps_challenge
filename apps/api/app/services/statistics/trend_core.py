"""Núcleo estadístico de tendencias: funciones puras, sin I/O ni Earth Engine.

Reglas (plan §7):
- El IC pertenece al mismo estimador que la estimación puntual.
- Valores faltantes se conservan como NaN y se cuentan; nunca se rellenan con 0.
- Si N es insuficiente se devuelve status="insufficient_evidence" con estimaciones None.
- Mann–Kendall sin corrección no es robusto a autocorrelación: se diagnostica y se advierte.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

ALGORITHM_VERSION = "trend_core/0.1.0"

Estimator = Literal["ols", "theil_sen"]
IntervalMethod = Literal["ols_classic", "hac_newey_west", "theil_sen_analytic", "moving_block_bootstrap"]
SignificanceTest = Literal["ols_t", "ols_hac_t", "mann_kendall", "none"]

# Combinaciones válidas estimador → métodos de IC / pruebas (plan §7.3–7.5).
COMPATIBILITY: dict[str, dict[str, tuple[str, ...]]] = {
    "ols": {
        "interval_methods": ("hac_newey_west", "ols_classic", "moving_block_bootstrap"),
        "significance_tests": ("ols_hac_t", "ols_t", "none"),
    },
    "theil_sen": {
        "interval_methods": ("theil_sen_analytic", "moving_block_bootstrap"),
        "significance_tests": ("mann_kendall", "none"),
    },
}

SECONDS_PER_YEAR = 365.2425 * 86400.0


class IncompatibleMethodError(ValueError):
    """Combinación estimador/IC/prueba no válida (API → 409 incompatible_method)."""


@dataclass
class TrendSettings:
    estimator: Estimator = "theil_sen"
    interval_method: IntervalMethod = "theil_sen_analytic"
    significance_test: SignificanceTest = "mann_kendall"
    confidence_level: float = 0.95
    time_unit: Literal["year", "decade"] = "decade"
    min_observations: int = 10
    min_coverage_fraction: float = 0.8
    hac_maxlags: int | None = None  # None → regla de Newey–West: floor(4 (n/100)^(2/9))
    resamples: int = 1000
    block_length: int = 12
    seed: int = 2026

    def validate(self) -> None:
        combo = COMPATIBILITY.get(self.estimator)
        if combo is None:
            raise IncompatibleMethodError(f"Estimador desconocido: {self.estimator}")
        if self.interval_method not in combo["interval_methods"]:
            raise IncompatibleMethodError(
                f"El método de IC '{self.interval_method}' no es compatible con '{self.estimator}'. "
                f"Permitidos: {combo['interval_methods']}"
            )
        if self.significance_test not in combo["significance_tests"]:
            raise IncompatibleMethodError(
                f"La prueba '{self.significance_test}' no es compatible con '{self.estimator}'. "
                f"Permitidas: {combo['significance_tests']}"
            )
        if not 0.5 < self.confidence_level < 1.0:
            raise ValueError("confidence_level debe estar en (0.5, 1)")
        if self.resamples < 100 or self.block_length < 1:
            raise ValueError("resamples >= 100 y block_length >= 1")


@dataclass
class TrendResult:
    status: Literal["ok", "exploratory", "insufficient_evidence"]
    estimator: str
    estimate: float | None
    estimate_unit: str
    ci_lower: float | None
    ci_upper: float | None
    ci_method: str
    confidence_level: float
    p_value: float | None
    q_value: float | None
    test_method: str
    n_observations: int
    n_missing: int
    coverage_fraction: float
    autocorrelation_lag1: float | None
    autocorrelation_adjustment: str
    intercept: float | None = None
    warnings: list[str] = field(default_factory=list)
    algorithm_version: str = ALGORITHM_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- utilidades


def decimal_years(times: Sequence | pd.DatetimeIndex) -> np.ndarray:
    """Convierte fechas a años decimales desde la época (UTC)."""
    idx = pd.DatetimeIndex(pd.to_datetime(times, utc=True))
    secs = (idx - pd.Timestamp("1970-01-01", tz="UTC")).total_seconds().to_numpy()
    return 1970.0 + secs / SECONDS_PER_YEAR


def lag1_autocorrelation(x: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=float)
    if x.size < 3 or np.allclose(x, x[0]):
        return None
    xc = x - x.mean()
    return float(np.sum(xc[1:] * xc[:-1]) / np.sum(xc * xc))


def newey_west_lags(n: int) -> int:
    return int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def mann_kendall(y: np.ndarray) -> tuple[float, float, float]:
    """Mann–Kendall clásico con corrección por empates. Devuelve (S, Z, p bilateral)."""
    y = np.asarray(y, dtype=float)
    n = y.size
    diffs = np.sign(y[None, :] - y[:, None])
    s = float(np.sum(np.triu(diffs, k=1)))
    _, counts = np.unique(y, return_counts=True)
    ties = counts[counts > 1]
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(ties * (ties - 1) * (2 * ties + 5))) / 18.0
    if var_s <= 0:
        return s, 0.0, 1.0
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    p = 2.0 * stats.norm.sf(abs(z))
    return s, float(z), float(p)


def benjamini_hochberg(p_values: Sequence[float | None]) -> list[float | None]:
    """q-valores BH-FDR; los None se conservan como None y no cuentan en la familia."""
    idx = [i for i, p in enumerate(p_values) if p is not None and not np.isnan(p)]
    out: list[float | None] = [None] * len(p_values)
    if not idx:
        return out
    p = np.array([p_values[i] for i in idx], dtype=float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(q_sorted, 1.0)
    for k, i in enumerate(idx):
        out[i] = float(q[k])
    return out


def _fit(estimator: str, t: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if estimator == "ols":
        slope, intercept = np.polyfit(t, y, 1)
        return float(slope), float(intercept)
    res = stats.theilslopes(y, t)
    return float(res.slope), float(res.intercept)


def moving_block_bootstrap_ci(
    t: np.ndarray, y: np.ndarray, estimator: str, level: float, resamples: int, block_length: int, seed: int
) -> tuple[float, float]:
    """IC percentil por bootstrap de bloques móviles sobre residuos de la tendencia ajustada."""
    rng = np.random.default_rng(seed)
    slope, intercept = _fit(estimator, t, y)
    fitted = intercept + slope * t
    resid = y - fitted
    n = y.size
    b = min(block_length, n)
    n_blocks = int(np.ceil(n / b))
    starts_max = n - b + 1
    boots = np.empty(resamples)
    for r in range(resamples):
        starts = rng.integers(0, starts_max, size=n_blocks)
        sample = np.concatenate([resid[s : s + b] for s in starts])[:n]
        boots[r] = _fit(estimator, t, fitted + sample)[0]
    alpha = 1.0 - level
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


# ---------------------------------------------------------------- API pública


def estimate_trend(
    times: Sequence,
    values: Sequence[float | None],
    settings: TrendSettings | None = None,
    value_unit: str = "unit",
    expected_observations: int | None = None,
) -> TrendResult:
    """Estima una tendencia lineal con IC e inferencia compatibles con el estimador.

    `values` puede contener None/NaN (faltantes); se excluyen del ajuste y se reportan.
    `expected_observations` permite calcular cobertura cuando faltan periodos completos.
    """
    s = settings or TrendSettings()
    s.validate()

    t_all = decimal_years(times)
    y_all = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    if t_all.size != y_all.size:
        raise ValueError("times y values deben tener la misma longitud")
    mask = np.isfinite(y_all)
    t, y = t_all[mask], y_all[mask]
    n = int(y.size)
    expected = expected_observations or int(y_all.size)
    n_missing = int(expected - n)
    coverage = n / expected if expected else 0.0
    factor = 10.0 if s.time_unit == "decade" else 1.0
    unit = f"{value_unit}/{s.time_unit}"
    warnings: list[str] = []

    base = {
        "estimator": s.estimator,
        "estimate_unit": unit,
        "ci_method": s.interval_method,
        "confidence_level": s.confidence_level,
        "test_method": s.significance_test,
        "n_observations": n,
        "n_missing": n_missing,
        "coverage_fraction": round(coverage, 4),
        "q_value": None,
    }

    if n < s.min_observations or (n >= 2 and np.allclose(y, y[0])):
        reason = (
            f"N={n} menor al mínimo {s.min_observations} para inferencia"
            if n < s.min_observations
            else "Serie constante: no hay variación para estimar tendencia"
        )
        return TrendResult(
            status="insufficient_evidence",
            estimate=None,
            ci_lower=None,
            ci_upper=None,
            p_value=None,
            autocorrelation_lag1=None,
            autocorrelation_adjustment="not_evaluated",
            warnings=[reason],
            **base,
        )

    status: Literal["ok", "exploratory"] = "ok"
    if coverage < s.min_coverage_fraction:
        status = "exploratory"
        warnings.append(
            f"Cobertura {coverage:.0%} inferior al umbral {s.min_coverage_fraction:.0%}: resultado exploratorio"
        )

    slope, intercept = _fit(s.estimator, t, y)
    ci_lo = ci_hi = p = None
    adjustment = "none"

    # Autocorrelación de residuos (diagnóstico común a todos los métodos).
    rho1 = lag1_autocorrelation(y - (intercept + slope * t))
    rho_threshold = 1.96 / np.sqrt(n)
    autocorrelated = rho1 is not None and abs(rho1) > rho_threshold

    if s.estimator == "ols":
        X = sm.add_constant(t)
        if s.interval_method == "hac_newey_west" or s.significance_test == "ols_hac_t":
            maxlags = s.hac_maxlags if s.hac_maxlags is not None else newey_west_lags(n)
            hac = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
            adjustment = f"HAC Newey-West (maxlags={maxlags})"
        classic = sm.OLS(y, X).fit()
        if s.interval_method == "hac_newey_west":
            ci_lo, ci_hi = hac.conf_int(alpha=1 - s.confidence_level)[1]
        elif s.interval_method == "ols_classic":
            ci_lo, ci_hi = classic.conf_int(alpha=1 - s.confidence_level)[1]
            if autocorrelated:
                warnings.append("IC OLS clásico con residuos autocorrelacionados: preferir HAC o bootstrap por bloques")
        if s.significance_test == "ols_hac_t":
            p = float(hac.pvalues[1])
        elif s.significance_test == "ols_t":
            p = float(classic.pvalues[1])
            if autocorrelated:
                warnings.append("Prueba t iid con autocorrelación sustancial: p-valor no fiable")
    else:  # theil_sen
        if s.interval_method == "theil_sen_analytic":
            res = stats.theilslopes(y, t, alpha=s.confidence_level)
            ci_lo, ci_hi = float(res.low_slope), float(res.high_slope)
            if autocorrelated:
                warnings.append("IC analítico Theil–Sen asume independencia; considerar bootstrap por bloques")
        if s.significance_test == "mann_kendall":
            _, _, p = mann_kendall(y)
            if autocorrelated:
                warnings.append("Mann–Kendall sin corrección con autocorrelación: p-valor puede ser optimista")

    if s.interval_method == "moving_block_bootstrap":
        ci_lo, ci_hi = moving_block_bootstrap_ci(
            t, y, s.estimator, s.confidence_level, s.resamples, s.block_length, s.seed
        )
        adjustment = (
            f"moving block bootstrap (b={s.block_length}, R={s.resamples}, seed={s.seed})"
            if adjustment == "none"
            else adjustment
        )

    return TrendResult(
        status=status,
        estimate=slope * factor,
        intercept=intercept,
        ci_lower=None if ci_lo is None else float(ci_lo) * factor,
        ci_upper=None if ci_hi is None else float(ci_hi) * factor,
        p_value=p,
        autocorrelation_lag1=rho1,
        autocorrelation_adjustment=adjustment,
        warnings=warnings,
        **base,
    )
