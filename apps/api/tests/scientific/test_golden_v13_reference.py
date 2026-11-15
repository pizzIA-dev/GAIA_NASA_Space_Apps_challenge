"""Golden test opcional contra los resultados históricos NinoDetect v13.1 (plan §14.2).

Usa `data/_local_reference/` (extraído del ZIP del usuario, NO versionado). Si no existe, se omite:
el producto no depende de estos artefactos; solo sirven para validar regresión numérica.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.services.statistics.trend_core import TrendSettings, estimate_trend

REF = Path(__file__).resolve().parents[4] / "data" / "_local_reference"
SERIES = REF / "NinoDetect_Entradas_NASA_Procesadas_v12" / "03_NASA_Series_Mensuales_Trujillo_Formato_Largo.csv"
TRENDS = REF / "NinoDetect_v13_1_Resultados_Corregidos_Verificados" / "tablas" / \
    "03_Tendencias_2003_2024_TheilSen_HAC_FDR.csv"

pytestmark = pytest.mark.skipif(not (SERIES.is_file() and TRENDS.is_file()), reason="referencia local ausente")

DISTRICTS = ["130101", "130104", "130106", "130107", "130108", "130110", "130111", "130112"]


@pytest.fixture(scope="module")
def data():
    s = pd.read_csv(SERIES, encoding="utf-8-sig", dtype={"ubigeo": str})
    t = pd.read_csv(TRENDS, encoding="utf-8-sig", dtype={"ubigeo": str})
    return s, t


@pytest.mark.parametrize("ubigeo", DISTRICTS)
def test_annual_precip_trend_matches_v13(data, ubigeo):
    s, t = data
    d = s[(s.ubigeo == ubigeo) & (s.variable == "precip_mm")]
    annual = d.groupby("anio").valor.sum()
    times = [f"{y}-01-01" for y in annual.index]
    ref = t[(t.ubigeo == ubigeo) & (t.variable == "precip_mm")].iloc[0]

    # Reproducción del método del estudio previo (IC analítico + MK clásico), no del valor por defecto actual.
    sen = estimate_trend(times, annual.tolist(), TrendSettings(
        interval_method="theil_sen_analytic", significance_test="mann_kendall", time_unit="year"))
    hac = estimate_trend(times, annual.tolist(), TrendSettings(
        estimator="ols", interval_method="hac_newey_west", significance_test="ols_hac_t", time_unit="year"))

    # Tolerancia documentada: el estudio usó años enteros; aquí años decimales UTC (365.2425 d) → ~1e-4 relativo.
    tol = {"rel": 2e-3, "abs": 2e-3}
    assert sen.estimate == pytest.approx(ref.pendiente_sen, **tol)
    assert (sen.ci_lower, sen.ci_upper) == pytest.approx((ref.sen_ic95_inf, ref.sen_ic95_sup), **tol)
    assert hac.estimate == pytest.approx(ref.pendiente_hac, **tol)
    assert (hac.ci_lower, hac.ci_upper) == pytest.approx((ref.ic95_inf, ref.ic95_sup), **tol)
    assert hac.p_value == pytest.approx(ref.p_hac, **tol)
