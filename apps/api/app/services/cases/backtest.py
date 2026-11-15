"""Evaluación retrospectiva de reglas de alerta por lluvia (plan §9.2 escena 5, §9.3, §7.7).

Unidad: distrito-día. Para el día t (emitida al inicio del día, solo con información PASADA):
  S(d, t) = lluvia acumulada en los `window` días t−window … t−1 (día local de Lima).
  Alerta(d, t) = S(d, t) ≥ umbral(d), con umbral(d) = percentil p de S(d, ·) en el periodo de CALIBRACIÓN.
  Desenlace(d, t) = hay al menos un registro SINPAD focal en el distrito d entre t y t+horizon−1.
Los umbrales se fijan solo con calibración y se aplican sin cambios al periodo de PRUEBA (fuera de muestra).

Se informan, por separado:
  - tabla de contingencia distrito-día (VP, FP, FN, VN), falsas alarmas FAR = FP/(VP+FP), días de alerta por año;
  - nivel evento: un registro está «anticipado» si hubo alerta en alguno de los `horizon` días previos o el mismo día
    (t ∈ [fecha−horizon+1, fecha]); POD con IC de Wilson y anticipación (días entre la primera alerta y el registro);
  - referencia de azar: POD esperado con alertas aleatorias de la misma frecuencia, 1 − (1 − tasa)^horizon.
Días con datos incompletos (lluvia nula o < 48 semihoras en la ventana) no se evalúan y se cuentan.
Con IMERG Final (reprocesado) el resultado es «anticipación potencial retrospectiva», no desempeño operativo.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

ALGORITHM = "case_backtest/0.1.0"


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def _ratio(a: int, b: int) -> float | None:
    return a / b if b else None


class Panel:
    """Lluvia diaria por unidad, en arreglos alineados a un calendario común (NaN = sin dato o día incompleto)."""

    def __init__(self, rain: dict[str, list[tuple[date, float | None, int]]]):
        all_days = sorted({d for rows in rain.values() for d, _, _ in rows})
        self.start, self.end = all_days[0], all_days[-1]
        n = (self.end - self.start).days + 1
        self.days = [self.start + timedelta(i) for i in range(n)]
        self.units = sorted(rain)
        self.x = np.full((len(self.units), n), np.nan)
        for i, u in enumerate(self.units):
            for d, v, nh in rain[u]:
                if v is not None and nh >= 48:
                    self.x[i, (d - self.start).days] = max(0.0, v)

    def index(self, d: date) -> int:
        return (d - self.start).days

    def signal(self, window: int) -> np.ndarray:
        """S[:, t] = suma de x[:, t−window … t−1]; NaN si falta algún día de la ventana o no hay historia."""
        s = np.full_like(self.x, np.nan)
        c = np.concatenate([np.zeros((self.x.shape[0], 1)), np.cumsum(np.nan_to_num(self.x), axis=1)], axis=1)
        bad = np.concatenate([np.zeros((self.x.shape[0], 1)), np.cumsum(np.isnan(self.x), axis=1)], axis=1)
        t = np.arange(window, self.x.shape[1])
        s[:, t] = c[:, t] - c[:, t - window]
        miss = bad[:, t] - bad[:, t - window]
        s[:, t] = np.where(miss > 0, np.nan, s[:, t])
        return s


def evaluate(panel: Panel, events: list[dict], *, percentile: float, window: int, horizon: int,
             train: tuple[date, date], test: tuple[date, date], min_signal_mm: float = 1.0) -> dict:
    """Una regla (percentil, ventana, horizonte). `events`: dicts con unit, date (date) y label."""
    S = panel.signal(window)
    nu, nt = S.shape
    ev = np.zeros((nu, nt), dtype=bool)
    unit_ix = {u: i for i, u in enumerate(panel.units)}
    evs = [e for e in events if e["unit"] in unit_ix and panel.start <= e["date"] <= panel.end]
    for e in evs:
        ev[unit_ix[e["unit"]], panel.index(e["date"])] = True
    # Desenlace(d, t): evento en [t, t+horizon−1]
    out = np.zeros_like(ev)
    for k in range(horizon):
        out[:, : nt - k] |= ev[:, k:]

    def span(p: tuple[date, date]) -> slice:
        return slice(max(0, panel.index(p[0])), min(nt, panel.index(p[1]) + 1))

    tr, te = span(train), span(test)
    # En la costa árida el percentil de días secos puede ser 0 mm: el umbral nunca baja de `min_signal_mm`.
    thr = np.array([max(min_signal_mm, float(np.nanpercentile(S[i, tr], percentile))) if np.isfinite(S[i, tr]).any()
                    else np.nan for i in range(nu)])
    alert = S >= thr[:, None]  # NaN → False; los NaN se excluyen abajo con `valid`
    valid = np.isfinite(S) & np.isfinite(thr)[:, None]

    def period(sl: slice, p: tuple[date, date], label: str) -> dict:
        v, a, o = valid[:, sl], alert[:, sl], out[:, sl]
        tp = int(np.sum(v & a & o)); fp = int(np.sum(v & a & ~o)); fn = int(np.sum(v & ~a & o)); tn = int(np.sum(v & ~a & ~o))
        n_valid = int(v.sum())
        years = ((p[1] - p[0]).days + 1) / 365.25
        rate = _ratio(tp + fp, n_valid)
        pe = [e for e in evs if p[0] <= e["date"] <= p[1]]
        detail = []
        for e in sorted(pe, key=lambda e: (e["date"], e["unit"])):
            i, t = unit_ix[e["unit"]], panel.index(e["date"])
            lo = max(0, t - horizon + 1)
            ks = [k for k in range(lo, t + 1) if valid[i, k] and alert[i, k]]
            evaluable = bool(valid[i, lo:t + 1].any())
            detail.append({"date": e["date"].isoformat(), "unit": e["unit"], "label": e.get("label"),
                           "evaluable": evaluable, "anticipated": bool(ks) if evaluable else None,
                           "lead_days": (t - ks[0]) if ks else None,
                           "signal_mm": None if not np.isfinite(S[i, t]) else round(float(S[i, t]), 1),
                           "threshold_mm": None if not np.isfinite(thr[i]) else round(float(thr[i]), 1)})
        ne = sum(1 for d in detail if d["evaluable"])
        hits = sum(1 for d in detail if d["anticipated"])
        lo_ci, hi_ci = wilson(hits, ne)
        far = _ratio(fp, tp + fp)
        far_ci = wilson(fp, tp + fp)
        return {
            "label": label, "start": p[0].isoformat(), "end": p[1].isoformat(),
            "unit_days_evaluated": n_valid, "unit_days_excluded_incomplete": int((~v).sum()),
            "contingency": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "far": far, "far_ci95": list(far_ci), "alert_rate": rate,
            "alert_unit_days_per_year": round((tp + fp) / years, 1) if years > 0 else None,
            "alerts_per_unit_per_year": round((tp + fp) / years / nu, 1) if years > 0 else None,
            "events": len(detail), "events_evaluable": ne, "events_anticipated": hits,
            "pod": _ratio(hits, ne), "pod_ci95": [lo_ci, hi_ci],
            "pod_random_expected": None if rate is None else 1 - (1 - rate) ** horizon,
            "events_detail": detail,
        }

    return {
        "rule": {"signal": f"lluvia acumulada de los {window} días previos", "window_days": window,
                 "percentile": percentile, "horizon_days": horizon,
                 "threshold_basis": f"percentil {percentile:g} por distrito, solo periodo de calibración, "
                                    f"mínimo {min_signal_mm:g} mm", "min_signal_mm": min_signal_mm},
        "thresholds_mm": {u: (None if not np.isfinite(thr[i]) else round(float(thr[i]), 1))
                          for i, u in enumerate(panel.units)},
        "calibration_in_sample": period(tr, train, "calibración (en muestra: optimista)"),
        "test_out_of_sample": period(te, test, "prueba (fuera de muestra)"),
    }


def backtest(panel: Panel, events: list[dict], *, train: tuple[date, date], test: tuple[date, date],
             percentiles: list[float], windows: list[int], horizons: list[int], primary: tuple[float, int, int],
             events_excluded: list[dict]) -> dict:
    rules = [evaluate(panel, events, percentile=p, window=w, horizon=h, train=train, test=test)
             for p in percentiles for w in windows for h in horizons]
    prim = next(r for r in rules if (r["rule"]["percentile"], r["rule"]["window_days"], r["rule"]["horizon_days"])
                == primary)
    t = prim["test_out_of_sample"]
    warnings = []
    if t["events_evaluable"] < 10:
        warnings.append(f"Solo {t['events_evaluable']} registros evaluables en el periodo de prueba: cualquier POD tiene un "
                        "intervalo enorme; no permite validar ni descartar una regla.")
    cal = prim["calibration_in_sample"]["events_detail"]
    if cal:
        years = [d["date"][:4] for d in cal]
        top = max(set(years), key=years.count)
        if years.count(top) / len(years) > 0.5:
            warnings.append(f"{years.count(top)} de los {len(years)} registros de calibración son de {top} (un mismo episodio "
                            "de lluvias): el buen desempeño en muestra no es independiente ni generalizable.")
    if events_excluded:
        warnings.append(f"{len(events_excluded)} registro(s) sin polígono distrital IGN quedan fuera de la evaluación: "
                        + ", ".join(f"{e['date']} ({e['district']})" for e in events_excluded) + ".")
    warnings += [
        ("IMERG Final es un producto reprocesado publicado meses después: esto mide anticipación POTENCIAL "
         "retrospectiva, no lo que se habría sabido en tiempo real (requeriría IMERG Early/Late)."),
        (f"Se evaluaron {len(rules)} combinaciones de regla; la regla principal se declaró antes de ver los resultados. "
         "Elegir a posteriori la mejor combinación sobreestimaría el desempeño."),
        ("Un registro SINPAD es un reporte administrativo: un día sin registro no demuestra que no hubo huaico, así que "
         "parte de las «falsas alarmas» pueden ser eventos no registrados."),
        "Esto no es un sistema de alerta ni sustituye los avisos oficiales de SENAMHI/INDECI.",
    ]
    return {"algorithm_version": ALGORITHM, "unit": "distrito-día",
            "periods": {"calibration": [train[0].isoformat(), train[1].isoformat()],
                        "test": [test[0].isoformat(), test[1].isoformat()]},
            "primary": prim, "grid": [_compact(r) for r in rules], "warnings": warnings,
            "events_excluded": events_excluded}


def _compact(r: dict) -> dict:
    t, c = r["test_out_of_sample"], r["calibration_in_sample"]
    return {**{k: r["rule"][k] for k in ("percentile", "window_days", "horizon_days")},
            "test": {k: t[k] for k in ("pod", "pod_ci95", "events_evaluable", "events_anticipated", "far",
                                         "alerts_per_unit_per_year", "pod_random_expected", "contingency")},
            "calibration": {k: c[k] for k in ("pod", "events_evaluable", "events_anticipated", "far",
                                                "alerts_per_unit_per_year")}}
