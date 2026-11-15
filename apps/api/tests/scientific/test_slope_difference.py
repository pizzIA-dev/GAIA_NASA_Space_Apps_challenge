"""Diferencia de pendientes con IC propio: equivalencias exactas, series correlacionadas y cobertura simulada."""

import numpy as np
import pytest

from app.services.statistics.slope_difference import slope_difference
from app.services.statistics.trend_core import IncompatibleMethodError, estimate_trend

YEARS = [f"{y}-01-01" for y in range(2003, 2025)]


def series(slope, noise, base=100.0):
    return [base + slope * i + e for i, e in enumerate(noise)]


def test_ols_is_refused_because_its_ci_undercovers():
    with pytest.raises(IncompatibleMethodError, match="Theil–Sen"):
        slope_difference(YEARS, list(range(22)), YEARS, list(range(22)), estimator="ols")


def test_identical_series_give_zero_difference():
    rng = np.random.default_rng(2)
    a = series(2.0, rng.normal(0, 4, 22))
    d = slope_difference(YEARS, a, YEARS, a, resamples=300)
    assert d["estimate"] == 0 and d["ci_lower"] == 0 and d["ci_upper"] == 0 and d["p_value"] == 1.0


def test_correlated_neighbours_paired_ci_detects_difference_hidden_by_overlapping_cis():
    # Clima común fuerte + diferencia real pequeña: los IC individuales se solapan, la diferencia no incluye 0.
    rng = np.random.default_rng(3)
    common = rng.normal(0, 20, 22)
    a = series(2.0, common + rng.normal(0, 1, 22))
    b = series(1.0, common + rng.normal(0, 1, 22))
    ia, ib = estimate_trend(YEARS, a), estimate_trend(YEARS, b)
    assert ia.ci_lower < ib.ci_upper  # solapan
    d = slope_difference(YEARS, a, YEARS, b, resamples=1000)
    assert d["residual_correlation"] > 0.9
    assert d["ci_lower"] > 0 and d["p_value"] < 0.05
    assert d["estimate"] == pytest.approx(10.0, abs=4.0)  # 1 unidad/año = 10 por década
    assert any("correlacionados" in w for w in d["warnings"])


def test_only_common_periods_and_insufficient_evidence():
    a = [1.0 + i for i in range(22)]
    b = [None] * 15 + [float(i) for i in range(7)]
    d = slope_difference(YEARS, a, YEARS, b)
    assert d["status"] == "insufficient_evidence" and d["n_paired_observations"] == 7 and d["estimate"] is None


@pytest.mark.parametrize(("phi", "rho"), [(0.3, 0.7), (0.0, 0.0)])
def test_paired_bootstrap_coverage_close_to_nominal(phi, rho):
    """Simulación: diferencia real 0,5/año (5/década), ruido AR(1) con correlación cruzada. IC 95 % → cobertura ≈ 95 %."""
    rng = np.random.default_rng(7)
    hits, reps = 0, 300
    cov = [[1, rho], [rho, 1]]
    for k in range(reps):
        e = np.zeros((22, 2))
        for i in range(1, 22):
            e[i] = phi * e[i - 1] + rng.multivariate_normal([0, 0], cov) * 3
        a, b = series(1.5, e[:, 0]), series(1.0, e[:, 1])
        d = slope_difference(YEARS, a, YEARS, b, resamples=400, seed=k)
        hits += d["ci_lower"] <= 5.0 <= d["ci_upper"]
    assert 0.91 <= hits / reps <= 0.995
