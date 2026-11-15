"""Pruebas científicas del motor de tendencias (plan §16.2). Datos SINTÉTICOS, solo para tests."""

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

from app.services.statistics.trend_core import (
    IncompatibleMethodError,
    TrendSettings,
    benjamini_hochberg,
    decimal_years,
    estimate_trend,
    mann_kendall,
)


def monthly_series(n=264, slope_per_year=0.5, noise=1.0, seed=0, ar=0.0):
    rng = np.random.default_rng(seed)
    times = pd.date_range("2003-01-01", periods=n, freq="MS", tz="UTC")
    t = decimal_years(times)
    e = np.zeros(n)
    eps = rng.normal(0, noise, n)
    for i in range(n):
        e[i] = (ar * e[i - 1] if i else 0.0) + eps[i]
    return times, 10.0 + slope_per_year * (t - t[0]) + e


def test_mann_kendall_strictly_increasing_analytic():
    s, z, p = mann_kendall(np.arange(10.0))
    assert s == 45
    assert z == pytest.approx(44 / np.sqrt(125))  # var = n(n-1)(2n+5)/18 = 125
    assert p == pytest.approx(2 * stats.norm.sf(44 / np.sqrt(125)))


def test_mann_kendall_with_ties_reduces_variance():
    s, z, _ = mann_kendall(np.array([1, 2, 2, 3, 4, 4, 4, 5, 6, 7], dtype=float))
    var_no_ties = 10 * 9 * 25 / 18
    assert abs(z) > (s - 1) / np.sqrt(var_no_ties)


def test_theil_sen_matches_scipy():
    times, y = monthly_series(seed=1)
    r = estimate_trend(times, y, TrendSettings(time_unit="year"), value_unit="mm")
    ref = stats.theilslopes(y, decimal_years(times), alpha=0.95)
    assert r.estimate == pytest.approx(ref.slope)
    assert (r.ci_lower, r.ci_upper) == pytest.approx((ref.low_slope, ref.high_slope))
    assert r.estimate_unit == "mm/year"


def test_ols_hac_matches_statsmodels_and_covers_true_slope():
    times, y = monthly_series(seed=2, ar=0.5)
    s = TrendSettings(estimator="ols", interval_method="hac_newey_west", significance_test="ols_hac_t",
                      time_unit="year")
    r = estimate_trend(times, y, s)
    t = decimal_years(times)
    fit = sm.OLS(y, sm.add_constant(t)).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    assert r.estimate == pytest.approx(fit.params[1])
    assert r.p_value == pytest.approx(fit.pvalues[1])
    assert r.ci_lower < 0.5 < r.ci_upper
    assert "HAC" in r.autocorrelation_adjustment


def test_decade_unit_scales_estimate_and_ci():
    times, y = monthly_series(seed=3)
    yr = estimate_trend(times, y, TrendSettings(time_unit="year"))
    dec = estimate_trend(times, y, TrendSettings(time_unit="decade"))
    assert dec.estimate == pytest.approx(10 * yr.estimate)
    assert dec.ci_upper == pytest.approx(10 * yr.ci_upper)


def test_incompatible_combination_rejected():
    with pytest.raises(IncompatibleMethodError):
        estimate_trend(*monthly_series(), TrendSettings(estimator="theil_sen", interval_method="hac_newey_west"))
    with pytest.raises(IncompatibleMethodError):
        estimate_trend(*monthly_series(), TrendSettings(estimator="ols", interval_method="hac_newey_west",
                                                        significance_test="mann_kendall"))


def test_insufficient_n_returns_nulls_not_zeros():
    times, y = monthly_series(n=6)
    r = estimate_trend(times, y)
    assert r.status == "insufficient_evidence"
    assert r.estimate is None and r.p_value is None and r.ci_lower is None


def test_constant_series_is_not_inferable():
    times = pd.date_range("2003-01-01", periods=24, freq="MS")
    r = estimate_trend(times, [5.0] * 24)
    assert r.status == "insufficient_evidence" and r.estimate is None


def test_missing_values_preserved_and_flag_low_coverage():
    times, y = monthly_series(n=120, seed=4)
    vals = [None if i % 3 == 0 else v for i, v in enumerate(y)]  # 1/3 faltante
    r = estimate_trend(times, vals)
    assert r.n_missing == 40 and r.n_observations == 80
    assert r.status == "exploratory"
    assert any("Cobertura" in w for w in r.warnings)


def test_block_bootstrap_reproducible_with_seed():
    times, y = monthly_series(seed=5, ar=0.4)
    s = TrendSettings(interval_method="moving_block_bootstrap", resamples=300, seed=7)
    a, b = estimate_trend(times, y, s), estimate_trend(times, y, s)
    assert (a.ci_lower, a.ci_upper) == (b.ci_lower, b.ci_upper)
    assert a.ci_lower < a.estimate < a.ci_upper


def test_null_trend_is_usually_not_significant():
    times, y = monthly_series(slope_per_year=0.0, seed=6)
    r = estimate_trend(times, y)
    assert r.p_value > 0.05  # semilla fija: sin tendencia real


def test_autocorrelation_warning_for_uncorrected_mk():
    times, y = monthly_series(seed=8, ar=0.8)
    r = estimate_trend(times, y, TrendSettings(interval_method="theil_sen_analytic", significance_test="mann_kendall"))
    assert r.autocorrelation_lag1 > 0.5
    assert any("Mann–Kendall" in w for w in r.warnings)


def test_default_corrects_for_autocorrelation_and_is_less_confident():
    """Con autocorrelación fuerte, el valor por defecto (n efectivo AR(1)) da un IC más ancho y un p mayor que el
    método clásico, y lo dice en `autocorrelation_adjustment`."""
    times, y = monthly_series(seed=8, ar=0.8)
    classic = estimate_trend(times, y, TrendSettings(interval_method="theil_sen_analytic", significance_test="mann_kendall"))
    default = estimate_trend(times, y)
    assert default.estimate == pytest.approx(classic.estimate)
    assert (default.ci_upper - default.ci_lower) > 1.5 * (classic.ci_upper - classic.ci_lower)
    assert default.p_value > classic.p_value
    assert "n efectivo AR(1)" in default.autocorrelation_adjustment


@pytest.mark.parametrize("method", [
    {"estimator": "theil_sen", "interval_method": "theil_sen_ar1", "significance_test": "mann_kendall_ar1"},
    {"estimator": "ols", "interval_method": "ar1_effective_n", "significance_test": "ols_ar1_t"},
    {"estimator": "theil_sen", "interval_method": "moving_block_bootstrap", "significance_test": "mann_kendall_ar1"},
])
def test_short_annual_series_coverage_and_type1_near_nominal(method):
    """Simulación (plan §16): n = 22 años, AR(1) φ = 0,3. Antes de ADR-0012: cobertura 80–89 %, error tipo I 13–21 %."""
    rng = np.random.default_rng(11)
    years = [f"{y}-01-01" for y in range(2003, 2025)]
    s = TrendSettings(**method, time_unit="year", resamples=400, block_length=3, min_coverage_fraction=0.0)
    hits = rej = 0
    reps = 300
    for k in range(reps):
        def ar1(slope):
            e = np.zeros(22)
            e[0] = rng.normal(0, 1 / np.sqrt(1 - 0.09))
            for i in range(1, 22):
                e[i] = 0.3 * e[i - 1] + rng.normal()
            return list(slope * np.arange(22) + 3 * e)
        s.seed = k
        r = estimate_trend(years, ar1(0.5), s)
        hits += r.ci_lower <= 0.5 <= r.ci_upper
        p = estimate_trend(years, ar1(0.0), s).p_value
        rej += p < 0.05
    assert hits / reps >= 0.90
    assert rej / reps <= 0.095


def test_benjamini_hochberg_matches_statsmodels_and_keeps_none():
    p = [0.01, 0.04, None, 0.03, 0.2]
    q = benjamini_hochberg(p)
    ref = multipletests([0.01, 0.04, 0.03, 0.2], method="fdr_bh")[1]
    assert q[2] is None
    assert [q[0], q[1], q[3], q[4]] == pytest.approx(list(ref))
