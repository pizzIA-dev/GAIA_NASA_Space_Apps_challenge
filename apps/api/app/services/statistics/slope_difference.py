"""Diferencia de pendientes entre dos series (plan §7: «comparación territorial … con inferencia compatible»; §12A.1).

Territorios vecinos comparten el clima: sus series están correlacionadas. Por eso NO se combinan los IC por separado
(ni se juzga por solapamiento de IC): se estima la diferencia con su propio IC, conservando la dependencia.

- Estimación: TS(A) − TS(B) (Theil–Sen, el estimador por defecto de la plataforma).
- IC por bootstrap de bloques móviles sobre PARES de periodos: en cada réplica se remuestrean los MISMOS bloques
  (t, A, B) (preserva autocorrelación y correlación cruzada). Cobertura simulada (n = 22 años, AR(1) ≤ 0,5,
  correlación cruzada 0–0,9, b = 3): 96–98,5 % para un IC nominal del 95 % (algo conservador).
  p-valor aproximado por inversión del IC percentil (2·min(P*(Δ ≤ 0), P*(Δ ≥ 0))), etiquetado como tal.
- OLS NO se ofrece: con n = 22 el IC HAC Newey–West de A − B cubrió 73–85 % y el bootstrap por pares 83–92 %.
  Un IC más estrecho de lo que debe sería peor que no dar ninguno (→ IncompatibleMethodError / 409).
Solo se usan los periodos con dato en ambas series.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.services.statistics.trend_core import IncompatibleMethodError, _fit, decimal_years

ALGORITHM = "slope_difference/0.1.0"


def _pair(times_a, values_a, times_b, values_b) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a = {str(t)[:10]: v for t, v in zip(times_a, values_a, strict=True) if v is not None and np.isfinite(v)}
    b = {str(t)[:10]: v for t, v in zip(times_b, values_b, strict=True) if v is not None and np.isfinite(v)}
    common = sorted(set(a) & set(b))
    t = decimal_years(common) if common else np.array([])
    return t, np.array([a[k] for k in common], dtype=float), np.array([b[k] for k in common], dtype=float)


def _theil_sen_rows(T: np.ndarray, Y: np.ndarray, chunk: int = 200) -> np.ndarray:
    """Theil–Sen por fila (réplica), vectorizado; pares con el mismo instante (años repetidos) se excluyen."""
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


def _ols_rows(T: np.ndarray, Y: np.ndarray) -> np.ndarray:
    tc = T - T.mean(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.sum(tc * (Y - Y.mean(axis=1, keepdims=True)), axis=1) / np.sum(tc * tc, axis=1)


def paired_block_bootstrap(t: np.ndarray, ya: np.ndarray, yb: np.ndarray, resamples: int, block_length: int,
                           seed: int, estimator: str = "theil_sen") -> np.ndarray:
    """Bootstrap de bloques móviles sobre PARES: cada réplica toma los mismos bloques de periodos (t, A, B) para ambas
    series y recalcula TS(A*) − TS(B*). Conserva autocorrelación y correlación cruzada. (El bootstrap sobre residuos
    se descartó: cobertura simulada ≈ 85 % con n = 22; este, 95–97 %.)"""
    rng = np.random.default_rng(seed)
    n = t.size
    b = min(block_length, n)
    n_blocks = int(np.ceil(n / b))
    starts = rng.integers(0, n - b + 1, size=(resamples, n_blocks))
    idx = (starts[:, :, None] + np.arange(b)).reshape(resamples, -1)[:, :n]
    T = t[idx]
    f = _ols_rows if estimator == "ols" else _theil_sen_rows
    return f(T, ya[idx]) - f(T, yb[idx])


def slope_difference(times_a: Sequence, values_a: Sequence[float | None], times_b: Sequence,
                     values_b: Sequence[float | None], *, estimator: str = "theil_sen", confidence_level: float = 0.95,
                     time_unit: str = "decade", value_unit: str = "unit", resamples: int = 2000,
                     block_length: int = 3, seed: int = 2026, min_observations: int = 10) -> dict:
    if estimator != "theil_sen":
        raise IncompatibleMethodError(
            "La diferencia de pendientes solo se ofrece con Theil–Sen: con series anuales cortas, los IC de OLS "
            "(HAC o bootstrap) cubren bastante menos del 95 % declarado (simulación: 73–92 %).")
    t, ya, yb = _pair(times_a, values_a, times_b, values_b)
    n = int(t.size)
    factor = 10.0 if time_unit == "decade" else 1.0
    base = {"algorithm_version": ALGORITHM, "estimator": estimator, "estimate_unit": f"{value_unit}/{time_unit}",
            "confidence_level": confidence_level, "n_paired_observations": n, "q_value": None}
    if n < min_observations:
        return base | {"status": "insufficient_evidence", "estimate": None, "ci_lower": None, "ci_upper": None,
                       "p_value": None, "ci_method": None, "test_method": None, "residual_correlation": None,
                       "warnings": [f"Solo {n} periodos con dato en ambas series (mínimo {min_observations})"]}
    sa, ia = _fit(estimator, t, ya)
    sb, ib = _fit(estimator, t, yb)
    ra, rb = ya - (ia + sa * t), yb - (ib + sb * t)
    rho = float(np.corrcoef(ra, rb)[0, 1]) if np.std(ra) > 0 and np.std(rb) > 0 else None
    warnings: list[str] = []
    alpha = 1 - confidence_level
    est = sa - sb  # en OLS coincide exactamente con la pendiente OLS de la serie A − B
    boots = paired_block_bootstrap(t, ya, yb, resamples, block_length, seed, estimator)
    boots = boots[np.isfinite(boots)]
    lo, hi = (float(x) for x in np.quantile(boots, [alpha / 2, 1 - alpha / 2]))
    if np.allclose(boots, 0.0):
        p = 1.0
    else:
        p = float(min(1.0, 2 * min(np.mean(boots <= 0), np.mean(boots >= 0))))
        p = max(p, 1.0 / (resamples + 1))
    ci_method = (f"bootstrap de bloques móviles sobre pares de periodos (b={block_length}, R={resamples}, "
                 f"semilla={seed})")
    test = "p aproximado por inversión del IC bootstrap percentil"
    if n < 15:
        warnings.append(f"Solo {n} periodos: el IC bootstrap es poco fiable con series tan cortas")
    if rho is not None and rho > 0.5:
        warnings.append(f"Los residuos de A y B están correlacionados (r = {rho:.2f}): comparar sus IC por separado "
                        "sería engañoso; por eso la diferencia lleva su propio IC.")
    warnings.append("Una diferencia de pendientes describe cuánto más cambia A que B en el periodo; no explica por qué.")
    return base | {"status": "ok", "estimate": est * factor, "ci_lower": lo * factor, "ci_upper": hi * factor,
                   "p_value": p, "ci_method": ci_method, "test_method": test,
                   "residual_correlation": rho, "warnings": warnings}
