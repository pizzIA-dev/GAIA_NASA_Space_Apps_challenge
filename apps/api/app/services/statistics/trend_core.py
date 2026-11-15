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

ALGORITHM_VERSION = "trend_core/0.2.0"  # 0.2: n efectivo AR(1) por defecto; bootstrap por pares (ADR-0012)

Estimator = Literal["ols", "theil_sen"]
IntervalMethod = Literal["ols_classic", "hac_newey_west", "ar1_effective_n", "theil_sen_analytic", "theil_sen_ar1",
                         "moving_block_bootstrap"]
SignificanceTest = Literal["ols_t", "ols_hac_t", "ols_ar1_t", "mann_kendall", "mann_kendall_ar1", "none"]

# Combinaciones válidas estimador → métodos de IC / pruebas (plan §7.3–7.5).
COMPATIBILITY: dict[str, dict[str, tuple[str, ...]]] = {
    "ols": {
        "interval_methods": ("ar1_effective_n", "hac_newey_west", "ols_classic", "moving_block_bootstrap"),
        "significance_tests": ("ols_ar1_t", "ols_hac_t", "ols_t", "none"),
    },
    "theil_sen": {
        "interval_methods": ("theil_sen_ar1", "theil_sen_analytic", "moving_block_bootstrap"),
        "significance_tests": ("mann_kendall_ar1", "mann_kendall", "none"),
    },
}

SECONDS_PER_YEAR = 365.2425 * 86400.0


class IncompatibleMethodError(ValueError):
    """Combinación estimador/IC/prueba no válida (API → 409 incompatible_method)."""


@dataclass
class TrendSettings:
    estimator: Estimator = "theil_sen"
    interval_method: IntervalMethod = "theil_sen_ar1"
    significance_test: SignificanceTest = "mann_kendall_ar1"
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


def ar1_effective(residuals: np.ndarray) -> tuple[float, float]:
    """ρ AR(1) de los residuos con corrección de sesgo (≈ (1 + 4ρ)/n para residuos de una recta), acotado a
    [0; 0,95], y el tamaño muestral efectivo n_ef = n (1 − ρ) / (1 + ρ) (Santer et al., 2000).

    Medido (scientific/reports/cobertura_ic.md): con n = 22 y AR(1) φ ≤ 0,6, el IC OLS con n_ef cubre 92–96 % y la t
    rechaza 3,8–9 % con pendiente nula; HAC Newey–West cubrió 68–85 % y rechazó 13–31 %."""
    n = residuals.size
    r = lag1_autocorrelation(residuals)
    r = 0.0 if r is None else r
    rho = float(np.clip(r + (1.0 + 4.0 * r) / n, 0.0, 0.95))
    return rho, n * (1.0 - rho) / (1.0 + rho)


def ols_ar1(t: np.ndarray, y: np.ndarray, level: float) -> tuple[float, float, float, float, float]:
    """OLS con varianza y grados de libertad corregidos por n efectivo AR(1). Devuelve (lo, hi, p, ρ, n_ef)."""
    tc = t - t.mean()
    slope = float(np.sum(tc * (y - y.mean())) / np.sum(tc * tc))
    res = y - (y.mean() + slope * tc)
    rho, neff = ar1_effective(res)
    df = max(neff - 2.0, 1.0)
    s2 = float(np.sum(res**2)) / df
    se = np.sqrt(s2 / float(np.sum(tc * tc)))
    q = stats.t.ppf(0.5 + level / 2.0, df)
    p = float(2.0 * stats.t.sf(abs(slope / se), df)) if se > 0 else 1.0
    return slope - q * se, slope + q * se, p, rho, neff


def mann_kendall_ar1(t: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """Mann–Kendall con varianza inflada por (1 + ρ)/(1 − ρ), ρ AR(1) corregido de los residuos de Theil–Sen.
    Devuelve (S, Z, p, ρ). Con n = 22: rechazo 3,8–9 % (vs 4,7–28 % del MK clásico) para φ ≤ 0,6."""
    s, _, _ = mann_kendall(y)
    n = y.size
    _, counts = np.unique(y, return_counts=True)
    ties = counts[counts > 1]
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(ties * (ties - 1) * (2 * ties + 5))) / 18.0
    res = stats.theilslopes(y, t)
    rho, _ = ar1_effective(y - (res.intercept + res.slope * t))
    var_s *= (1.0 + rho) / (1.0 - rho)
    if var_s <= 0 or s == 0:
        return s, 0.0, 1.0, rho
    z = (s - np.sign(s)) / np.sqrt(var_s)
    return s, float(z), float(2.0 * stats.norm.sf(abs(z))), rho


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


def _slopes_rows(estimator: str, T: np.ndarray, Y: np.ndarray, chunk: int = 200) -> np.ndarray:
    """Pendiente por fila (réplica), vectorizada. Theil–Sen excluye pares con el mismo instante (repetidos)."""
    if estimator == "ols":
        tc = T - T.mean(axis=1, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.sum(tc * (Y - Y.mean(axis=1, keepdims=True)), axis=1) / np.sum(tc * tc, axis=1)
    n = T.shape[1]
    i, j = np.triu_indices(n, 1)
    out = np.empty(T.shape[0])
    for c in range(0, T.shape[0], chunk):
        dt = T[c:c + chunk, j] - T[c:c + chunk, i]
        with np.errstate(divide="ignore", invalid="ignore"):
            sl = (Y[c:c + chunk, j] - Y[c:c + chunk, i]) / dt
        sl[dt == 0] = np.nan
        out[c:c + chunk] = np.nanmedian(sl, axis=1)
    return out


def moving_block_bootstrap_ci(
    t: np.ndarray, y: np.ndarray, estimator: str, level: float, resamples: int, block_length: int, seed: int
) -> tuple[float, float]:
    """IC percentil por bootstrap de bloques móviles sobre PARES (t, y).

    La versión 0.1 remuestreaba residuos alrededor de la recta ajustada: medido, cubría 84 % (φ = 0) y 66 % (φ = 0,6)
    con n = 22. Remuestrear pares de periodos conserva la autocorrelación dentro de cada bloque y la variabilidad de
    la pendiente (ADR-0012, scientific/reports/cobertura_ic.md)."""
    rng = np.random.default_rng(seed)
    n = y.size
    b = min(block_length, n)
    n_blocks = int(np.ceil(n / b))
    starts = rng.integers(0, n - b + 1, size=(resamples, n_blocks))
    idx = (starts[:, :, None] + np.arange(b)).reshape(resamples, -1)[:, :n]
    boots = _slopes_rows(estimator, t[idx], y[idx])
    boots = boots[np.isfinite(boots)]
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
        if s.interval_method == "ar1_effective_n" or s.significance_test == "ols_ar1_t":
            lo_a, hi_a, p_a, rho_a, neff = ols_ar1(t, y, s.confidence_level)
            adjustment = f"n efectivo AR(1) (ρ corregido = {rho_a:.2f}, n_ef = {neff:.1f})"
            if s.interval_method == "ar1_effective_n":
                ci_lo, ci_hi = lo_a, hi_a
            if s.significance_test == "ols_ar1_t":
                p = p_a
            if rho_a > 0.5:
                warnings.append(f"Autocorrelación alta (ρ ≈ {rho_a:.2f}): aun corregida, con series cortas la prueba "
                                "puede rechazar algo más del 5 % nominal (medido ≈ 9 % con φ = 0,6 y n = 22)")
        if s.interval_method == "hac_newey_west" and n < 50:
            warnings.append(f"IC HAC con solo {n} observaciones: medido, cubre bastante menos del nominal; "
                            "preferir el IC con n efectivo AR(1)")
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
        if s.interval_method == "theil_sen_ar1":
            res = stats.theilslopes(y, t, alpha=s.confidence_level)
            rho_t, neff_t = ar1_effective(y - (res.intercept + res.slope * t))
            f = float(np.sqrt((1.0 + rho_t) / (1.0 - rho_t)))
            ci_lo = res.slope - (res.slope - res.low_slope) * f
            ci_hi = res.slope + (res.high_slope - res.slope) * f
            adjustment = f"IC Theil–Sen ensanchado por n efectivo AR(1) (ρ corregido = {rho_t:.2f}, n_ef = {neff_t:.1f})"
        if s.interval_method == "theil_sen_analytic":
            res = stats.theilslopes(y, t, alpha=s.confidence_level)
            ci_lo, ci_hi = float(res.low_slope), float(res.high_slope)
            if autocorrelated:
                warnings.append("IC analítico Theil–Sen asume independencia; considerar bootstrap por bloques")
        if s.significance_test == "mann_kendall":
            _, _, p = mann_kendall(y)
            if autocorrelated:
                warnings.append("Mann–Kendall sin corrección con autocorrelación: p-valor puede ser optimista")
        elif s.significance_test == "mann_kendall_ar1":
            _, _, p, rho_m = mann_kendall_ar1(t, y)
            mk_note = f"Mann–Kendall con n efectivo AR(1) (ρ corregido = {rho_m:.2f})"
            adjustment = mk_note if adjustment == "none" else f"{adjustment}; {mk_note}"
            if rho_m > 0.5:
                warnings.append(f"Autocorrelación alta (ρ ≈ {rho_m:.2f}): aun corregida, con series cortas la prueba "
                                "puede rechazar algo más del 5 % nominal (medido ≈ 9 % con φ = 0,6 y n = 22)")

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
