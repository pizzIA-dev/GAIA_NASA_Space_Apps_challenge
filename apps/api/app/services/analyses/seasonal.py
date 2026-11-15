"""Ciclo estacional (plan §8: heatmap año × mes, climatología, meses extremos). Funciones puras sobre filas mensuales.

La climatología describe el periodo elegido (no es pronóstico). Faltantes se conservan como null y se cuentan.
"""

from __future__ import annotations

from datetime import date

import numpy as np

MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def seasonal_summary(rows: list[dict], unit: str, top_n: int = 5) -> dict:
    by_ym: dict[tuple[int, int], float | None] = {}
    for r in rows:
        d = date.fromisoformat(r["time_start_utc"][:10])
        by_ym[(d.year, d.month)] = None if r.get("value") is None else float(r["value"])
    if not by_ym:
        return {"unit": unit, "years": [], "matrix": [], "climatology": [], "extremes": [], "n_months": 0}
    years = list(range(min(y for y, _ in by_ym), max(y for y, _ in by_ym) + 1))
    matrix = [[by_ym.get((y, m)) for m in range(1, 13)] for y in years]

    climatology = []
    for m in range(1, 13):
        vals = np.array([v for (y, mm), v in by_ym.items() if mm == m and v is not None], dtype=float)
        n_years = sum(1 for (_, mm) in by_ym if mm == m)
        if vals.size == 0:
            climatology.append({"month": m, "label": MONTHS_ES[m - 1], "n_valid": 0, "n_years": n_years,
                                "mean": None, "median": None, "p25": None, "p75": None, "min": None, "max": None})
            continue
        climatology.append({
            "month": m, "label": MONTHS_ES[m - 1], "n_valid": int(vals.size), "n_years": n_years,
            "mean": float(vals.mean()), "median": float(np.median(vals)),
            "p25": float(np.percentile(vals, 25)), "p75": float(np.percentile(vals, 75)),
            "min": float(vals.min()), "max": float(vals.max()),
        })

    valid = [((y, m), v) for (y, m), v in by_ym.items() if v is not None]
    extremes = [{"year": y, "month": m, "label": f"{MONTHS_ES[m - 1]} {y}", "value": v,
                 "anomaly": v - next(c["mean"] for c in climatology if c["month"] == m)}
                for (y, m), v in sorted(valid, key=lambda kv: kv[1], reverse=True)[:top_n]]
    means = [c for c in climatology if c["mean"] is not None]
    return {
        "unit": unit,
        "years": years,
        "months": MONTHS_ES,
        "matrix": matrix,
        "climatology": climatology,
        "peak_month": max(means, key=lambda c: c["mean"])["label"] if means else None,
        "low_month": min(means, key=lambda c: c["mean"])["label"] if means else None,
        "extremes": extremes,
        "n_months": len(by_ym),
        "n_missing": sum(1 for v in by_ym.values() if v is None),
        "note": "Climatología descriptiva del periodo extraído (media, mediana y rango intercuartílico P25–P75 por "
                "mes calendario). Los meses sin dato no se rellenan. No es un pronóstico.",
    }
