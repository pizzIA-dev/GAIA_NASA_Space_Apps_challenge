"""Ingesta reproducible de límites administrativos oficiales del Perú (ADM1–ADM3, UBIGEO).

Fuente: OCHA HDX "Peru - Subnational Administrative Boundaries" (COD-AB), producida por el Instituto Geográfico
Nacional (IGN), licencia CC BY-IGO. No se modifican geometrías: se validan, se miden y se guardan por unidad.

Salida (no versionada):  .cache/boundaries/pe-ign2020/index.json  y  geoms/<UBIGEO>.json
Manifiesto (versionado):  data/manifests/pe-ign-cod-ab-2020.json

Uso:  apps/api/.venv/Scripts/python scripts/ingest_pe_boundaries.py [--force-download]
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {
    "boundary_set_id": "pe-ign-cod-ab-2020",
    "title": "Peru - Subnational Administrative Boundaries (COD-AB)",
    "producer": "Instituto Geográfico Nacional (IGN), Perú",
    "publisher": "OCHA ROLAC / Humanitarian Data Exchange",
    "license": "CC BY-IGO (Creative Commons Attribution for Intergovernmental Organisations)",
    "dataset_page": "https://data.humdata.org/dataset/cod-ab-per",
    "url": "https://data.humdata.org/dataset/54fc7f4d-f4c0-4892-91f6-2fe7c1ecf363/resource/"
           "63647792-0951-40d2-a30e-4a0e60f7a176/download/per_admin_boundaries.geojson.zip",
    "sha256": "2f0ec51b7a0899b407546aa644621e1c3255cba59fdda76fcde6975ca6baafb3",
    "valid_on": "2020-07-14",
    "source_version": "v01",
    "hdx_last_modified": "2026-01-26",
}
EXPECTED_COUNTS = {1: 25, 2: 196, 3: 1873}
DOWNLOAD = ROOT / "data" / "_downloads" / "hdx-cod-ab-per" / "per_admin_boundaries.geojson.zip"
OUT = ROOT / ".cache" / "boundaries" / "pe-ign2020"
MANIFEST = ROOT / "data" / "manifests" / "pe-ign-cod-ab-2020.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ubigeo(pcode: str) -> str:
    if not pcode.startswith("PE") or not pcode[2:].isdigit():
        raise ValueError(f"pcode inesperado: {pcode}")
    return pcode[2:]


def main(force_download: bool = False) -> int:
    if force_download or not DOWNLOAD.is_file():
        DOWNLOAD.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SOURCE["url"], headers={"User-Agent": "earth-trend-dev/0.1"})
        with urllib.request.urlopen(req, timeout=600) as r, DOWNLOAD.open("wb") as fh:
            fh.write(r.read())
    digest = sha256(DOWNLOAD)
    if digest != SOURCE["sha256"]:
        print(f"SHA256 distinto ({digest}). La fuente cambió: revisar y actualizar SOURCE antes de continuar.")
        return 2

    zf = zipfile.ZipFile(DOWNLOAD)
    (OUT / "geoms").mkdir(parents=True, exist_ok=True)
    index, invalid, counts = [], [], {}
    for lvl in (1, 2, 3):
        feats = json.loads(zf.read(f"per_admin{lvl}.geojson"))["features"]
        counts[lvl] = len(feats)
        if len(feats) != EXPECTED_COUNTS[lvl]:
            print(f"Conteo ADM{lvl}={len(feats)} distinto del esperado {EXPECTED_COUNTS[lvl]}")
            return 3
        for f in feats:
            p, geom = f["properties"], f["geometry"]
            code = ubigeo(p[f"adm{lvl}_pcode"])
            parent = None if lvl == 1 else ubigeo(p[f"adm{lvl - 1}_pcode"])
            shp = shape(geom)
            if not shp.is_valid:
                invalid.append(code)
            minx, miny, maxx, maxy = shp.bounds
            index.append({
                "ubigeo": code, "name": p[f"adm{lvl}_name"], "admin_level": f"ADM{lvl}", "parent_ubigeo": parent,
                "area_km2": round(float(p["area_sqkm"]), 3), "bbox": [round(v, 5) for v in (minx, miny, maxx, maxy)],
                "center": [p["center_lon"], p["center_lat"]],
            })
            (OUT / "geoms" / f"{code}.json").write_text(json.dumps(geom, separators=(",", ":")), encoding="utf-8")

    ingested_at = datetime.now(UTC).isoformat()
    (OUT / "index.json").write_text(json.dumps({"source": SOURCE, "ingested_at": ingested_at, "units": index},
                                               ensure_ascii=False), encoding="utf-8")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        **SOURCE, "files": ["per_admin1.geojson", "per_admin2.geojson", "per_admin3.geojson"],
        "unit_counts": {f"ADM{k}": v for k, v in counts.items()},
        "invalid_geometries": invalid, "geometry_policy": "sin simplificar; CRS84; solo validación y medición",
        "ingested_at": ingested_at, "script": "scripts/ingest_pe_boundaries.py",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {counts} · geometrías inválidas: {len(invalid)} {invalid[:10]} · índice en {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--force-download" in sys.argv))
