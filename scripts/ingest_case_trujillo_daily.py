"""Lluvia diaria IMERG V07 por distrito (provincia de Trujillo, fronteras IGN) para la escena 5 del caso (plan §9.2).

- Fuente: NASA/GPM_L3/IMERG_V07 (Final, semihoraria, banda `precipitation` en mm/h). Total diario = Σ tasa × 0,5 h.
- Día hidrometeorológico LOCAL de Lima (UTC−5): 00:00–24:00 hora de Lima = 05:00–05:00 UTC (plan §11.4).
- Se registra cuántas de las 48 semihoras existen; un día incompleto queda marcado, no se trata como completo.
- Media ponderada por área (reducer mean) a 11 132 m. Mismas geometrías IGN que el resto de la plataforma.
- Checkpoint por mes en data/_downloads/imerg_daily/ (reanudable). Salida versionada:
  data/case-trujillo/imerg_daily_districts.csv.gz
- IMERG Final es un producto REPROCESADO con latencia de meses: cualquier evaluación con él es «anticipación potencial
  retrospectiva», no prueba de lo que se habría sabido en tiempo real (plan §9.3).

Uso:  apps/api/.venv/Scripts/python scripts/ingest_case_trujillo_daily.py [AAAA-MM-inicio] [AAAA-MM-fin]
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.earth_engine.client import get_ee
from app.services.geographies.registry import registry

COLLECTION = "NASA/GPM_L3/IMERG_V07"
SCALE_M = 11132
LIMA_OFFSET_H = 5
CKPT = ROOT / "data" / "_downloads" / "imerg_daily"
OUT = ROOT / "data" / "case-trujillo" / "imerg_daily_districts.csv.gz"


def months(a: str, b: str) -> list[date]:
    y, m = map(int, a.split("-"))
    y2, m2 = map(int, b.split("-"))
    out = []
    while (y, m) <= (y2, m2):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def extract_month(ee, fc, first: date) -> list[dict]:
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    days = [(first + timedelta(d)) for d in range((nxt - first).days)]
    col = ee.ImageCollection(COLLECTION).select("precipitation")
    off = timedelta(hours=LIMA_OFFSET_H)
    t0 = datetime(first.year, first.month, first.day, tzinfo=UTC) + off
    t1 = datetime(nxt.year, nxt.month, nxt.day, tzinfo=UTC) + off
    # Una sola agregación por mes (EE limita las agregaciones concurrentes): imagen de 28–31 bandas, una por día local.
    bands = []
    for d in days:
        s = datetime(d.year, d.month, d.day, tzinfo=UTC) + off
        bands.append(col.filterDate(ee.Date(s.isoformat()), ee.Date((s + timedelta(days=1)).isoformat()))
                     .sum().multiply(0.5).rename(f"d{d:%Y%m%d}"))
    img = ee.Image.cat(bands)
    stats = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_M, tileScale=2).getInfo()
    # Semihoras disponibles por día local (completitud explícita, no se asume 48).
    times = col.filterDate(ee.Date(t0.isoformat()), ee.Date(t1.isoformat())).aggregate_array("system:time_start").getInfo()
    n: dict[str, int] = {}
    for ms in times:
        k = (datetime.fromtimestamp(ms / 1000, UTC) - off).date().isoformat()
        n[k] = n.get(k, 0) + 1
    rows = []
    for f in stats["features"]:
        p = f["properties"]
        for d in days:
            rows.append({"ubigeo": p["ubigeo"], "date": d.isoformat(), "rain_mm": p.get(f"d{d:%Y%m%d}"),
                         "n_halfhours": n.get(d.isoformat(), 0)})
    return rows


def main(a: str = "2017-01", b: str = "2025-12") -> int:
    ee = get_ee()
    prov = registry.get("pe-ign2020:1301")
    units = registry.children(prov)
    feats = [ee.Feature(ee.Geometry(registry.ref(u).geojson(), proj="EPSG:4326", geodesic=False),
                        {"ubigeo": u.geo_id.split(":")[1]}) for u in units]
    fc = ee.FeatureCollection(feats)
    CKPT.mkdir(parents=True, exist_ok=True)
    for first in months(a, b):
        ck = CKPT / f"{first:%Y-%m}.json"
        if ck.is_file():
            continue
        for attempt in range(4):
            try:
                t0 = time.time()
                rows = extract_month(ee, fc, first)
                ck.write_text(json.dumps(rows), encoding="utf-8")
                print(f"{first:%Y-%m}: {len(rows)} filas ({time.time() - t0:.0f} s)", flush=True)
                break
            except Exception as e:  # noqa: BLE001 — reintento con espera ante cuotas/transitorios de EE
                wait = 10 * 2 ** attempt
                print(f"{first:%Y-%m}: error {type(e).__name__}: {str(e)[:120]} → reintento en {wait} s", flush=True)
                time.sleep(wait)
        else:
            print(f"{first:%Y-%m}: FALLÓ tras reintentos; se reanudará en la próxima ejecución", flush=True)
            return 1
    rows = []
    for first in months(a, b):
        rows.extend(json.loads((CKPT / f"{first:%Y-%m}.json").read_text(encoding="utf-8")))
    rows.sort(key=lambda r: (r["ubigeo"], r["date"]))
    with gzip.open(OUT, "wt", encoding="utf-8", newline="") as fh:
        fh.write(f"# NASA {COLLECTION} (Final, semihoraria) suma diaria x 0.5 h; dia local Lima UTC-5; "
                 f"media ponderada por area a {SCALE_M} m; fronteras IGN Peru (HDX COD-AB v01); "
                 f"generado {datetime.now(UTC).isoformat()} por scripts/ingest_case_trujillo_daily.py\n")
        fh.write("ubigeo,date,rain_mm,n_halfhours\n")
        for r in rows:
            v = "" if r.get("rain_mm") is None else f"{r['rain_mm']:.4f}"
            fh.write(f"{r['ubigeo']},{r['date']},{v},{r['n_halfhours']}\n")
    print(f"OK → {OUT} ({len(rows)} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
