"""Estudio de simulación: cobertura de los IC 95 % y error tipo I de las pruebas del motor (plan §16, pruebas científicas).

Usa `estimate_trend` tal cual (lo mismo que API, web y SDK). La versión 0.1 del motor (bootstrap sobre residuos,
IC analítico y MK sin corregir, HAC) se midió con este mismo script: ver ADR-0012 para la tabla «antes». Series sintéticas con tendencia lineal conocida y ruido
AR(1) gaussiano. Escenarios por defecto = los de la plataforma: anual n = 22 (2003–2024) y anomalía mensual n = 264.

    apps/api/.venv/Scripts/python scripts/coverage_study.py [repeticiones] > scientific/reports/cobertura_ic.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.services.statistics.trend_core import TrendSettings, estimate_trend

METHODS = {
    "OLS + IC clásico + t": {"estimator": "ols", "interval_method": "ols_classic", "significance_test": "ols_t"},
    "OLS + IC HAC + t HAC": {"estimator": "ols", "interval_method": "hac_newey_west", "significance_test": "ols_hac_t"},
    "Theil–Sen + IC analítico + MK": {"estimator": "theil_sen", "interval_method": "theil_sen_analytic",
                                          "significance_test": "mann_kendall"},
    "OLS + IC n efectivo AR(1) + t AR(1) [nuevo]": {"estimator": "ols", "interval_method": "ar1_effective_n",
                                                         "significance_test": "ols_ar1_t"},
    "Theil–Sen + IC n efectivo + MK AR(1) [nuevo, defecto]": {"estimator": "theil_sen", "interval_method": "theil_sen_ar1",
                                                                 "significance_test": "mann_kendall_ar1"},
    "Theil–Sen + bootstrap bloques (pares) + MK AR(1) [corregido]": {
        "estimator": "theil_sen", "interval_method": "moving_block_bootstrap", "significance_test": "mann_kendall_ar1"},
}


def simulate(n: int, monthly: bool, phi: float, slope_per_step: float, rng: np.random.Generator) -> tuple[list, list]:
    e = np.zeros(n)
    e[0] = rng.normal(0, 1 / np.sqrt(1 - phi**2)) if phi < 1 else 0
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal()
    if monthly:
        times = [f"{2003 + i // 12}-{i % 12 + 1:02d}-01" for i in range(n)]
    else:
        times = [f"{2003 + i}-01-01" for i in range(n)]
    return times, list(slope_per_step * np.arange(n) + 3 * e)


def run(n: int, monthly: bool, phis: list[float], reps: int, boot_reps: int) -> list[dict]:
    steps_per_decade = 120 if monthly else 10
    true_slope = 0.5  # por paso
    out = []
    for name, m in METHODS.items():
        boot = m["interval_method"] == "moving_block_bootstrap"
        if boot and monthly and n > 200:
            continue  # Theil–Sen bootstrap mensual: coste prohibitivo en simulación; se informa como no medido
        r = boot_reps if boot else reps
        for phi in phis:
            s = TrendSettings(**m, resamples=500, block_length=12 if monthly else 3, min_coverage_fraction=0.0)
            rng = np.random.default_rng(int(phi * 100) + 7)
            hits = rej = 0
            for k in range(r):
                s.seed = k
                t, y = simulate(n, monthly, phi, true_slope, rng)
                res = estimate_trend(t, y, s)
                hits += res.ci_lower <= true_slope * steps_per_decade <= res.ci_upper
                t0, y0 = simulate(n, monthly, phi, 0.0, rng)
                p = estimate_trend(t0, y0, s).p_value
                rej += p is not None and p < 0.05
            out.append({"method": name, "phi": phi, "n": n, "monthly": monthly, "reps": r,
                        "coverage": hits / r, "type1": rej / r})
    return out


def main(reps: int = 1000) -> None:
    t0 = time.time()
    rows = run(22, False, [0.0, 0.3, 0.6], reps, max(200, reps // 4))
    rows += run(264, True, [0.0, 0.5], max(200, reps // 4), 0)
    print("# Cobertura de IC 95 % y error tipo I (α = 0,05) del motor `trend_core`\n")
    print(f"Generado por `scripts/coverage_study.py` ({reps} repeticiones base; {time.time() - t0:.0f} s). Ruido AR(1)"
          " gaussiano con coeficiente φ. Nominal: cobertura 95 %, error tipo I 5 %. Error de Monte Carlo ≈ ±1,4 pp con"
          " 1000 repeticiones y ±3 pp con 200.\n")
    print("| Serie | Método | φ | Repeticiones | Cobertura IC 95 % | Error tipo I |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        serie = f"mensual n={r['n']}" if r["monthly"] else f"anual n={r['n']}"
        flag_c = " ⚠" if r["coverage"] < 0.92 else ""
        flag_t = " ⚠" if r["type1"] > 0.08 else ""
        print(f"| {serie} | {r['method']} | {r['phi']} | {r['reps']} | {r['coverage']:.1%}{flag_c} | {r['type1']:.1%}{flag_t} |")
    print("\n⚠ = cobertura < 92 % o error tipo I > 8 %. Theil–Sen + bootstrap en series mensuales no se midió (coste).")


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
