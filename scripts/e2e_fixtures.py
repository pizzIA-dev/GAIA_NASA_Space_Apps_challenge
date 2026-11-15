"""Fixtures para E2E/CI sin Earth Engine (plan §16): series NASA REALES ya extraídas, nunca datos inventados.

Flujo para regenerarlos (requiere Earth Engine local):
  1) python scripts/e2e_fixtures.py subset .cache_e2e      # caché vacía + fronteras IGN de la provincia de Trujillo
  2) levantar API con CACHE_DIR=.cache_e2e y correr Playwright (extrae SOLO lo que las pruebas usan)
  3) python scripts/e2e_fixtures.py collect .cache_e2e     # copia extracciones + fronteras a scientific/fixtures/e2e/
En CI:
  python scripts/e2e_fixtures.py seed <dir_cache>          # recrea la caché desde los fixtures (sin credenciales EE)

Sin Earth Engine, cualquier extracción no incluida responde 503 source_unavailable (honesto), nunca un valor falso.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_BOUNDS = ROOT / ".cache" / "boundaries" / "pe-ign2020"
FIXTURES = ROOT / "scientific" / "fixtures" / "e2e"
PROVINCE = "1301"  # Trujillo (IGN): la provincia y sus distritos cubren todas las pruebas E2E


def copy_bounds(dst_bounds: Path, src_bounds: Path) -> int:
    idx = json.loads((src_bounds / "index.json").read_text(encoding="utf-8"))
    keep = {u["ubigeo"] for u in idx["units"] if u["ubigeo"] == PROVINCE or u["parent_ubigeo"] == PROVINCE}
    keep |= {PROVINCE[:2]}  # departamento, para la ruta «Perú › La Libertad»
    (dst_bounds / "geoms").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_bounds / "index.json", dst_bounds / "index.json")  # índice completo (búsqueda), 420 KB
    for code in keep:
        src = src_bounds / "geoms" / f"{code}.json"
        if src.is_file():
            shutil.copy2(src, dst_bounds / "geoms" / f"{code}.json")
    return len(keep)


def subset(cache: Path) -> None:
    if cache.exists():
        shutil.rmtree(cache)
    n = copy_bounds(cache / "boundaries" / "pe-ign2020", SRC_BOUNDS)
    print(f"Caché vacía en {cache} con {n} geometrías IGN (provincia {PROVINCE} y distritos)")


def collect(cache: Path) -> None:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    shutil.copytree(cache / "extractions", FIXTURES / "extractions")
    copy_bounds(FIXTURES / "boundaries" / "pe-ign2020", cache / "boundaries" / "pe-ign2020")
    rows = []
    for f in sorted((FIXTURES / "extractions").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))["rows"]
        rows.append({"file": f.name, "dataset": r[0].get("source_dataset_id"), "variable": r[0].get("variable_id"),
                     "months": len(r), "valid": sum(x["value"] is not None for x in r),
                     "extracted_at": r[0].get("extracted_at")})
    manifest = {
        "purpose": "Fixtures de E2E/CI: series mensuales NASA reales (Earth Engine) usadas por apps/web/e2e. No son datos sintéticos.",
        "generated_at": datetime.now(UTC).isoformat(),
        "boundaries": "IGN Perú vía OCHA HDX COD-AB v01 (CC BY-IGO): índice completo + geometrías de la provincia de Trujillo",
        "extractions": rows,
    }
    (FIXTURES / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    size = sum(p.stat().st_size for p in FIXTURES.rglob("*") if p.is_file()) / 1024
    print(f"{len(rows)} extracciones → {FIXTURES} ({size:.0f} KB)")


def seed(cache: Path) -> None:
    if not FIXTURES.is_dir():
        raise SystemExit("No hay fixtures: genera con subset/collect")
    shutil.copytree(FIXTURES / "extractions", cache / "extractions", dirs_exist_ok=True)
    shutil.copytree(FIXTURES / "boundaries", cache / "boundaries", dirs_exist_ok=True)
    print(f"Caché sembrada en {cache} desde {FIXTURES}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"subset", "collect", "seed"}:
        raise SystemExit(__doc__)
    {"subset": subset, "collect": collect, "seed": seed}[sys.argv[1]](Path(sys.argv[2]).resolve())
