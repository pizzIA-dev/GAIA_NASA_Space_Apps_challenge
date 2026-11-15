"""Asociación eventos ↔ anomalías: casos SINTÉTICOS con respuesta conocida (plan §16.2)."""

from datetime import date

import numpy as np
import pytest

from app.services.cases.association import association, episodes_of


def make(n_geo=4, years=(2003, 2020), seed=0, signal=0.0, lag=0, events_at=()):
    rng = np.random.default_rng(seed)
    series = {}
    for g in range(n_geo):
        rows = []
        for y in range(years[0] - 1, years[1] + 1):
            for m in range(1, 13):
                rows.append({"time_start_utc": date(y, m, 1).isoformat(), "value": float(rng.normal(0, 1))})
        series[f"g{g}"] = rows
    events = [{"geo_id": g, "date": date(y, m, 15).isoformat()} for g, y, m in events_at]
    # Inyectar señal: anomalía alta `lag` meses antes de cada evento.
    for g, y, m in events_at:
        k = y * 12 + (m - 1) - lag
        key = date(k // 12, k % 12 + 1, 1).isoformat()
        for r in series[g]:
            if r["time_start_utc"] == key:
                r["value"] += signal
    return series, events


EVENTS = [(f"g{i % 4}", 2004 + i, 1 + (i * 5) % 12) for i in range(14)]  # 14 episodios en años distintos


def test_detects_known_signal_at_the_right_lag():
    s, e = make(signal=3.0, lag=1, events_at=EVENTS)
    r = {x["lag_months"]: x for x in association(s, e, 2004, 2020, [0, 1, 2], resamples=999)["results"]}
    assert r[1]["effect"] == pytest.approx(3.0, abs=0.8) and r[1]["q_value"] < 0.01
    assert r[0]["p_value"] > 0.01 and r[2]["p_value"] > 0.01


def test_no_signal_is_not_significant_and_reproducible():
    s, e = make(signal=0.0, events_at=EVENTS, seed=3)
    a = association(s, e, 2004, 2020, [0, 1], resamples=999, seed=7)
    b = association(s, e, 2004, 2020, [0, 1], resamples=999, seed=7)
    assert a == b
    assert all(x["p_value"] > 0.05 for x in a["results"])


def test_clustered_events_trigger_episode_warnings():
    s, e = make(signal=2.0, events_at=[("g0", 2017, 3), ("g1", 2017, 3), ("g2", 2017, 3), ("g3", 2017, 2), ("g0", 2010, 6)])
    out = association(s, e, 2004, 2020, [0], resamples=499)
    r = out["results"][0]
    assert r["n_event_months"] == 5 and r["n_independent_episodes"] == 2
    assert r["dominant_episode"] == "2017-02 a 2017-03" and r["dominant_episode_share"] == pytest.approx(0.8)
    joined = " ".join(out["warnings"])
    assert "potencia estadística muy baja" in joined and "depende de ese episodio" in joined and "no capacidad de anticipación" in joined


def test_missing_anomalies_are_skipped_not_zero():
    s, e = make(events_at=EVENTS)
    for r in s["g0"]:
        r["value"] = None
    out = association(s, e, 2004, 2020, [0], resamples=199)["results"][0]
    assert out["n_event_months"] == sum(1 for g, *_ in EVENTS if g != "g0")


def test_episodes_merge_consecutive_months():
    assert episodes_of([(2017, 2), (2017, 3), (2017, 3), (2018, 3)]) == [[(2017, 2), (2017, 3)], [(2018, 3)]]
