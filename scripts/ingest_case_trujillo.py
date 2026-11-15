"""Ingesta reproducible del caso «El Niño Costero y desastres en Trujillo» desde fuentes oficiales (plan §6.5, §9).

1) Eventos: INDECI / SINPAD, Plataforma Nacional de Datos Abiertos (ODC-BY). Se descargan los CSV oficiales, se verifica
   SHA256, se normalizan fechas (formatos mixtos, desambiguados con las columnas oficiales AÑO/MES) y UBIGEO, y se
   guardan los registros de la provincia de Trujillo (UBIGEO 1301xx). «Focal» = HUAYCO o INUNDACION.
2) Contexto ENFEN: serie oficial ICEN (IGP, «ICEN; ENFEN, 2024 — versión oficial»). Los episodios se DERIVAN con la regla
   operacional configurable (por defecto: neutro −0,7…+0,5; El Niño Costero si ICEN > +0,5 ≥ 3 meses consecutivos;
   La Niña Costera si ICEN < −0,7 ≥ 3 meses). Umbral citado de documentos ENFEN, pendiente de verificación directa
   contra la Nota Técnica 01-2024 (su web no responde desde el entorno de desarrollo).

Salidas versionadas (pequeñas, públicas): data/case-trujillo/{sinpad_trujillo.json, icen_enfen.json, MANIFEST.json}.
Descargas crudas (no versionadas): data/_downloads/{sinpad,enfen}/.

Uso:  apps/api/.venv/Scripts/python scripts/ingest_case_trujillo.py [--refresh]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "data" / "_downloads"
OUT = ROOT / "data" / "case-trujillo"
UA = {"User-Agent": "earth-trend-dev/0.1"}

SINPAD = {
    "dataset_page": "https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento",
    "publisher": "INDECI — Sistema de Información Nacional para la Respuesta y Rehabilitación (SINPAD)",
    "license": "ODC-BY (Open Data Commons Attribution)",
    "files": {
        "BD_2003-2025_EMERGENCIAS.csv": "a1fe63f0a7c836b8ff7dd1c87271d3bd3144f8444e41f93b7db205c85fef2687",
        "BD_2026_Semestre_I.csv": "acb09730fd53ee65175a1584bb043d0259c6932cc979f7bc6e452d670be52280",
    },
    "base_url": "https://www.datosabiertos.gob.pe/sites/default/files/",
}
ICEN = {
    "url": "http://met.igp.gob.pe/datos/ICEN.txt",
    "publisher": "Instituto Geofísico del Perú (IGP) — serie oficial ICEN (ENFEN, 2024)",
    "reference": "ENFEN (2024). Definición operacional de los eventos El Niño Costero y La Niña Costera en el Perú. "
                 "Nota Técnica ENFEN 01-2024.",
    "reference_url": "https://enfen.imarpe.gob.pe/download/nota-tecnica-enfen-01-2024-definicion-operacional-de-los-"
                     "eventos-el-nino-costero-y-la-nina-costera-en-el-peru/",
}
RULE = {
    "warm_threshold_gt": 0.5, "cold_threshold_lt": -0.7, "min_consecutive_months": 3,
    "status": "umbral_citado_pendiente_de_verificacion",
    "note": "Neutro −0,7 ≤ ICEN ≤ +0,5 y duración mínima de 3 meses según documentos ENFEN que citan la NT 01-2024. "
            "Episodios DERIVADOS por la plataforma, no lista oficial transcrita. Magnitud no clasificada.",
}
PROVINCE_UBIGEO = "1301"
FOCAL_HAZARDS = {"HUAYCO": "huaico", "INUNDACION": "inundacion"}
MONTHS = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
          "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
DAMAGE_COLS = {"FALLECIDOS": "fallecidos", "DESAPARECIDOS": "desaparecidos", "LESIONADOS": "lesionados",
               "DAMNIFICADOS": "damnificados", "AFECTADOS": "afectados", "VIVIENDAS DESTRUIDAS": "viviendas_destruidas",
               "VIVIENDAS AFECTADAS": "viviendas_afectadas"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def fetch(url: str, dst: Path, refresh: bool) -> Path:
    if refresh or not dst.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
            dst.write_bytes(r.read())
    return dst


def parse_date(raw: str, year: str, month_name: str) -> tuple[str | None, str]:
    """Fecha ISO y su precisión. Formatos observados: DD/MM/YYYY (2003–2024) y M/D/YY (2025). AÑO/MES deciden."""
    s = (raw or "").strip()
    y, m = int(year), MONTHS.get((month_name or "").strip().upper())
    parts = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", s)
    if parts and m:
        a, b, yy = int(parts[1]), int(parts[2]), int(parts[3])
        yy = yy + 2000 if yy < 100 else yy
        for day, mon in ((a, b), (b, a)):  # probar DD/MM y MM/DD; aceptar solo si coincide con AÑO/MES oficiales
            if mon == m and yy == y:
                try:
                    return date(y, m, day).isoformat(), "dia"
                except ValueError:
                    pass
    return (date(y, m, 1).isoformat(), "mes") if m else (None, "desconocida")


def to_num(v):
    try:
        x = float(str(v).replace(",", ".").strip())
        return int(x) if x.is_integer() else x
    except (TypeError, ValueError):
        return None


def ingest_sinpad(refresh: bool) -> dict:
    frames, files = [], []
    for name, expected in SINPAD["files"].items():
        p = fetch(SINPAD["base_url"] + name, DL / "sinpad" / name, refresh)
        digest = sha256(p)
        if digest != expected:
            raise SystemExit(f"SHA256 distinto para {name}: {digest}. La fuente cambió: revisar y actualizar.")
        d = pd.read_csv(p, sep=";", encoding="latin1", dtype=str, low_memory=False)
        d.columns = [c.strip() for c in d.columns]
        d["_archivo"] = name
        frames.append(d)
        files.append({"file": name, "sha256": digest, "rows": len(d)})
    d = pd.concat(frames, ignore_index=True)
    ub = d["COD. DISTRITO"].str.strip().str.zfill(6)
    prov = d[ub.str.startswith(PROVINCE_UBIGEO, na=False)].copy()
    events, bad_dates = [], 0
    for _, r in prov.iterrows():
        iso, precision = parse_date(r["FECHA  DE LA EMER"], r["AÑO"], r["MES"])
        bad_dates += precision != "dia"
        hazard = r["PELIGRO"].strip().upper()
        events.append({
            "sinpad_code": r["CODIGO DE EMERGENCIA-SINPAD"].strip(),
            "date": iso, "date_precision": precision, "date_raw": r["FECHA  DE LA EMER"].strip(),
            "year": int(r["AÑO"]), "hazard_sinpad": hazard, "hazard": FOCAL_HAZARDS.get(hazard),
            "focal": hazard in FOCAL_HAZARDS, "hazard_type": (r.get("TIPO DE PELIGRO") or "").strip(),
            "ubigeo": r["COD. DISTRITO"].strip().zfill(6), "district": r["DIST."].strip().title(),
            "damages": {v: to_num(r.get(k)) for k, v in DAMAGE_COLS.items()},
            "source_file": r["_archivo"],
        })
    dup = len(events) - len({e["sinpad_code"] for e in events})
    return {"files": files, "events": sorted(events, key=lambda e: (e["date"] or "", e["sinpad_code"])),
            "duplicates_by_code": dup, "dates_not_day_precision": bad_dates}


def derive_episodes(series: list[dict]) -> list[dict]:
    def runs(pred, kind):
        out, cur = [], []
        for p in series:
            if pred(p["icen"]):
                cur.append(p)
            else:
                if len(cur) >= RULE["min_consecutive_months"]:
                    out.append(cur)
                cur = []
        ongoing = len(cur) >= RULE["min_consecutive_months"]
        if ongoing:
            out.append(cur)
        eps = []
        for i, run in enumerate(out):
            last = run is out[-1] and ongoing
            start, end = run[0], run[-1]
            eid = f"{'EN' if kind == 'nino' else 'LN'}-COSTERO-{start['year']}" + (
                f"-{str(end['year'])[2:]}" if end["year"] != start["year"] else "")
            eps.append({"id": eid, "kind": "el_nino_costero" if kind == "nino" else "la_nina_costera",
                        "start": f"{start['year']}-{start['month']:02d}", "end": f"{end['year']}-{end['month']:02d}",
                        "months": len(run), "peak_icen": max((p["icen"] for p in run), key=abs),
                        "ongoing": last, "derived": True})
        return eps

    return sorted(runs(lambda v: v > RULE["warm_threshold_gt"], "nino") +
                  runs(lambda v: v < RULE["cold_threshold_lt"], "nina"), key=lambda e: e["start"])


def ingest_icen(refresh: bool) -> dict:
    p = fetch(ICEN["url"], DL / "enfen" / "ICEN.txt", refresh)
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    header = [ln for ln in lines if ln.startswith("%")]
    series = []
    for ln in lines:
        m = re.fullmatch(r"\s*(\d{4})\s+(\d{1,2})\s+(-?\d+(?:\.\d+)?)\s*", ln)
        if m:
            series.append({"year": int(m[1]), "month": int(m[2]), "icen": float(m[3])})
    if not series:
        raise SystemExit("ICEN.txt sin datos reconocibles")
    return {"sha256": sha256(p), "header": header, "series": series, "episodes": derive_episodes(series)}


def classify(events: list[dict], episodes: list[dict], series: list[dict]) -> None:
    icen = {(p["year"], p["month"]): p["icen"] for p in series}
    for e in events:
        if not e["date"]:
            e["enfen"] = {"context": "sin_fecha", "episode_id": None, "icen_month": None}
        else:
            ym = e["date"][:7]
            ep = next((x for x in episodes if x["kind"] == "el_nino_costero" and x["start"] <= ym <= x["end"]), None)
            nina = next((x for x in episodes if x["kind"] == "la_nina_costera" and x["start"] <= ym <= x["end"]), None)
            e["enfen"] = {"context": "coincidencia_el_nino_costero" if ep else "coincidencia_la_nina_costera" if nina
                          else "fuera_de_episodio", "episode_id": (ep or nina or {}).get("id"),
                          "icen_month": icen.get((int(ym[:4]), int(ym[5:7])))}
        # Causalidad individual: NUNCA inferida por fecha (plan §6.5.2, §8.1). Solo con documento específico.
        e["causal_attribution"] = {"status": "no_verificada", "evidence_url": None}


def main(refresh: bool) -> int:
    sinpad = ingest_sinpad(refresh)
    icen = ingest_icen(refresh)
    classify(sinpad["events"], icen["episodes"], icen["series"])
    now = datetime.now(UTC).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sinpad_trujillo.json").write_text(json.dumps({
        "source": {k: v for k, v in SINPAD.items() if k != "files"} | {"files": sinpad["files"]},
        "province_ubigeo": PROVINCE_UBIGEO, "focal_hazards": list(FOCAL_HAZARDS), "ingested_at": now,
        "events": sinpad["events"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "icen_enfen.json").write_text(json.dumps({
        "source": ICEN | {"sha256": icen["sha256"], "header": icen["header"]}, "rule": RULE, "ingested_at": now,
        "episodes": icen["episodes"], "series": icen["series"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    focal = [e for e in sinpad["events"] if e["focal"]]
    manifest = {
        "case": "trujillo-el-nino", "ingested_at": now, "script": "scripts/ingest_case_trujillo.py",
        "sinpad_files": sinpad["files"], "icen_sha256": icen["sha256"],
        "counts": {"province_records": len(sinpad["events"]), "focal_records": len(focal),
                   "focal_2017_2025": sum(1 for e in focal if 2017 <= e["year"] <= 2025),
                   "duplicates_by_code": sinpad["duplicates_by_code"],
                   "dates_not_day_precision": sinpad["dates_not_day_precision"]},
        "episodes_since_2000": [e for e in icen["episodes"] if e["start"] >= "2000"],
        "attribution": "Eventos: INDECI/SINPAD (ODC-BY). ICEN: IGP/ENFEN. Coincidencia temporal ≠ causalidad.",
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    for ep in manifest["episodes_since_2000"]:
        print(f"  {ep['id']:22} {ep['start']}→{ep['end']} ({ep['months']} meses, pico {ep['peak_icen']:+.2f}){' EN CURSO' if ep['ongoing'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--refresh" in sys.argv))
