"""Motor de evaluación retrospectiva de alertas (escena 5): casos sintéticos con respuesta conocida."""

from datetime import date, timedelta

import numpy as np
import pytest

from app.services.cases.backtest import Panel, backtest, evaluate, wilson

D0 = date(2020, 1, 1)
TRAIN = (date(2020, 1, 1), date(2020, 12, 31))
TEST = (date(2021, 1, 1), date(2021, 12, 31))


def panel(values: dict[str, list[float | None]], nh: int = 48) -> Panel:
    return Panel({u: [(D0 + timedelta(i), v, nh) for i, v in enumerate(vs)] for u, vs in values.items()})


def test_signal_uses_only_previous_days():
    p = panel({"a": [1.0, 2.0, 4.0, 8.0, 16.0]})
    s = p.signal(2)
    assert np.isnan(s[0, 0]) and np.isnan(s[0, 1])
    assert s[0, 2] == 3.0 and s[0, 3] == 6.0 and s[0, 4] == 12.0  # el día t no entra en S(t)


def test_incomplete_days_are_excluded_not_zero():
    p = Panel({"a": [(D0, 5.0, 48), (D0 + timedelta(1), 5.0, 40), (D0 + timedelta(2), 5.0, 48), (D0 + timedelta(3), 1.0, 48)]})
    s = p.signal(1)
    assert np.isnan(s[0, 2])  # el día previo tenía 40/48 semihoras
    assert s[0, 3] == 5.0


def test_perfect_rule_detects_all_and_no_false_alarm():
    rng = np.random.default_rng(1)
    n = 731
    x = list(rng.uniform(0, 1, n))
    ev_days = [400, 500, 600]
    for t in ev_days:
        x[t - 1] = 100.0  # lluvia fuerte el día anterior a cada registro
    for t in [100, 200]:
        x[t - 1] = 100.0  # calibración: define el umbral sin tocar la prueba
    p = panel({"a": x})
    evs = [{"unit": "a", "date": D0 + timedelta(t)} for t in ev_days]
    r = evaluate(p, evs, percentile=99.5, window=1, horizon=1, train=TRAIN, test=TEST)
    t = r["test_out_of_sample"]
    assert t["events_anticipated"] == 3 and t["pod"] == 1.0
    assert t["contingency"]["fp"] == 0 and t["far"] == 0.0
    assert all(d["lead_days"] == 0 for d in t["events_detail"])


def test_rule_never_alerts_gives_pod_zero_not_null():
    p = panel({"a": [5.0] * 365 + [0.0] * 366})
    evs = [{"unit": "a", "date": date(2021, 6, 1)}]
    r = evaluate(p, evs, percentile=90, window=1, horizon=3, train=TRAIN, test=TEST)
    t = r["test_out_of_sample"]
    assert t["pod"] == 0.0 and t["events_evaluable"] == 1 and t["far"] is None  # sin alertas: FAR indefinido, no 0


def test_threshold_from_calibration_only():
    # Prueba con lluvia 10× mayor: si el umbral usara la prueba, no alertaría siempre.
    p = panel({"a": [1.0 + (i % 10) for i in range(366)] + [100.0] * 365})
    r = evaluate(p, [], percentile=90, window=1, horizon=1, train=TRAIN, test=TEST)
    assert r["thresholds_mm"]["a"] <= 10.0
    assert r["test_out_of_sample"]["alert_rate"] == pytest.approx(1.0, abs=0.01)


def test_lead_time_and_horizon():
    x = [0.0] * 731
    x[449] = 50.0  # S(450) alto → alerta el día 450
    for t in [50, 150, 250]:
        x[t] = 50.0
    p = panel({"a": x})
    evs = [{"unit": "a", "date": D0 + timedelta(452)}]
    r1 = evaluate(p, evs, percentile=99, window=1, horizon=1, train=TRAIN, test=TEST)
    r3 = evaluate(p, evs, percentile=99, window=1, horizon=3, train=TRAIN, test=TEST)
    assert r1["test_out_of_sample"]["events_anticipated"] == 0
    d = r3["test_out_of_sample"]["events_detail"][0]
    assert d["anticipated"] and d["lead_days"] == 2


def test_random_expectation_and_wilson():
    lo, hi = wilson(0, 3)
    assert lo == 0.0 and 0.5 < hi < 0.6
    lo, hi = wilson(3, 3)
    assert hi == 1.0 and 0.4 < lo < 0.5
    assert wilson(0, 0) == (None, None)


def test_backtest_primary_and_warnings():
    rng = np.random.default_rng(2)
    p = panel({"a": list(rng.gamma(0.3, 5, 731)), "b": list(rng.gamma(0.3, 5, 731))})
    evs = [{"unit": "a", "date": date(2021, 3, 1)}]
    out = backtest(p, evs, train=TRAIN, test=TEST, percentiles=[90, 95], windows=[1, 3], horizons=[1, 3],
                   primary=(95, 3, 3), events_excluded=[{"date": "2021-04-04", "district": "X"}])
    assert len(out["grid"]) == 8
    assert out["primary"]["rule"] == {**out["primary"]["rule"], "percentile": 95, "window_days": 3, "horizon_days": 3}
    assert any("Solo 1 registros" in w for w in out["warnings"])
    assert any("sin polígono" in w for w in out["warnings"])


def test_dry_coast_threshold_never_zero():
    # 95 % de días secos: el P90 es 0 mm; sin mínimo, todos los días serían alerta.
    x = [0.0] * 731
    for t in range(0, 731, 20):
        x[t] = 3.0
    r = evaluate(panel({"a": x}), [], percentile=90, window=1, horizon=1, train=TRAIN, test=TEST)
    assert r["thresholds_mm"]["a"] == 1.0
    assert r["test_out_of_sample"]["alert_rate"] < 0.1
