"""Asociación exploratoria entre anomalías ambientales y meses con registros de emergencia (plan §7.7, §9.3).

Panel lugar × mes que incluye meses CON y SIN reportes (nunca solo positivos). Para cada desfase h:
  X(t − h) = anomalía mensual (respecto al mismo mes calendario) del distrito h meses antes del mes t.
  Estadístico = media, sobre los distrito-mes con evento, de [X − media de X en los distrito-mes SIN evento del mismo
  mes calendario]. Solo cuentan los meses calendario con al menos un evento y un control.
  Prueba: permutación de las etiquetas de evento DENTRO de cada mes calendario (preserva la estacionalidad), bilateral.
Multiplicidad: BH-FDR sobre la familia de desfases. Es asociación temporal, NO causalidad ni capacidad de alerta.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

from app.services.statistics.trend_core import benjamini_hochberg

ALGORITHM = "case_association/0.1.0"


def _shift(y: int, m: int, h: int) -> tuple[int, int]:
    k = y * 12 + (m - 1) - h
    return k // 12, k % 12 + 1


def episodes_of(keys: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Agrupa meses con evento consecutivos (en cualquier distrito) en episodios: no son observaciones independientes."""
    out: list[list[tuple[int, int]]] = []
    for y, m in sorted(set(keys)):
        if out and (y * 12 + m) - (out[-1][-1][0] * 12 + out[-1][-1][1]) <= 1:
            out[-1].append((y, m))
        else:
            out.append([(y, m)])
    return out


def association(series: dict[str, list[dict]], events: list[dict], year_from: int, year_to: int,
                lags: list[int], resamples: int = 2000, seed: int = 2026, unit: str = "") -> dict:
    anom: dict[tuple[str, int, int], float] = {}
    for geo, rows in series.items():
        for r in rows:
            if r.get("value") is None:
                continue
            d = date.fromisoformat(r["time_start_utc"][:10])
            anom[(geo, d.year, d.month)] = float(r["value"])
    ev_count: dict[tuple[str, int, int], int] = defaultdict(int)
    for e in events:
        if e.get("geo_id") in series and e.get("date"):
            d = date.fromisoformat(e["date"])
            if year_from <= d.year <= year_to:
                ev_count[(e["geo_id"], d.year, d.month)] += 1

    rng = np.random.default_rng(seed)
    results, warnings = [], []
    for h in lags:
        rows = []  # (calendar_month, x, is_event)
        for geo in series:
            for y in range(year_from, year_to + 1):
                for m in range(1, 13):
                    x = anom.get((geo, *_shift(y, m, h)))
                    if x is not None and (geo, y, m) in anom:
                        rows.append((m, x, ev_count.get((geo, y, m), 0) > 0, (y, m)))
        strata = defaultdict(list)
        for m, x, ev, ym in rows:
            strata[m].append((x, ev, ym))
        usable = {m: v for m, v in strata.items() if any(e for _, e, _ in v) and not all(e for _, e, _ in v)}
        n_ev = sum(1 for v in usable.values() for _, e, _ in v if e)
        if n_ev == 0:
            results.append({"lag_months": h, "status": "insufficient_evidence", "effect": None, "p_value": None,
                            "n_event_months": 0, "n_control_months": 0})
            continue
        xs = {m: np.array([x for x, _, _ in v]) for m, v in usable.items()}
        labels = {m: np.array([e for _, e, _ in v]) for m, v in usable.items()}

        def stat(lbl: dict[int, np.ndarray], xs: dict[int, np.ndarray] = xs) -> float:
            diffs = []
            for m, x in xs.items():
                e = lbl[m]
                diffs.extend(x[e] - x[~e].mean())
            return float(np.mean(diffs))

        obs = stat(labels)
        perm = np.empty(resamples)
        for r in range(resamples):
            perm[r] = stat({m: rng.permutation(lbl) for m, lbl in labels.items()})
        p = float((1 + np.sum(np.abs(perm) >= abs(obs))) / (1 + resamples))
        ev_keys = [ym for v in usable.values() for _, e, ym in v if e]
        eps = episodes_of(ev_keys)
        biggest = max(eps, key=lambda c: sum(1 for k in ev_keys if k in c))
        share = sum(1 for k in ev_keys if k in biggest) / len(ev_keys)
        results.append({
            "lag_months": h, "status": "ok", "effect": obs, "effect_unit": unit, "p_value": p,
            "n_event_months": n_ev, "n_control_months": sum(len(v) for v in usable.values()) - n_ev,
            "n_independent_episodes": len(eps),
            "dominant_episode": f"{biggest[0][0]}-{biggest[0][1]:02d}" + (
                f" a {biggest[-1][0]}-{biggest[-1][1]:02d}" if len(biggest) > 1 else ""),
            "dominant_episode_share": round(share, 3),
            "calendar_months_used": sorted(usable),
        })
    ok = [r for r in results if r["status"] == "ok"]
    for r, q in zip(ok, benjamini_hochberg([r["p_value"] for r in ok]), strict=True):
        r["q_value"] = q
    if ok:
        n_eps = min(r["n_independent_episodes"] for r in ok)
        if n_eps < 5:
            warnings.append(f"Solo {n_eps} episodios independientes con eventos: potencia estadística muy baja; "
                            "los registros del mismo episodio no son observaciones independientes.")
        top = max(ok, key=lambda r: r["dominant_episode_share"])
        if top["dominant_episode_share"] > 0.5:
            warnings.append(f"Más del {int(top['dominant_episode_share'] * 100)} % de los meses con evento pertenecen a un "
                            f"solo episodio ({top['dominant_episode']}): el resultado depende de ese episodio.")
    if 0 in lags:
        warnings.append("El desfase 0 compara el mismo mes: describe simultaneidad, no capacidad de anticipación.")
    warnings.append("Asociación temporal exploratoria: no demuestra causalidad ni valida un sistema de alerta.")
    return {"algorithm_version": ALGORITHM, "method": "diferencia estratificada por mes calendario + permutación "
            "dentro de cada mes calendario; BH-FDR sobre desfases", "resamples": resamples, "seed": seed,
            "n_units": len(series), "results": results, "warnings": warnings}
