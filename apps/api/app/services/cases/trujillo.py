"""Caso «El Niño Costero y desastres en Trujillo» (plan §9). Lee los datos versionados generados por
scripts/ingest_case_trujillo.py (SINPAD oficial + ICEN oficial). Es un CASO, no define el modelo general del producto.

Reglas: coincidencia temporal ENFEN ≠ causalidad; «sin registro» ≠ «sin fenómeno»; los 16 registros 2017–2025 son
control histórico, no una cifra fija; los registros no son episodios meteorológicos independientes.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.core.config import REPO_ROOT

CASE_ID = "trujillo-el-nino"
DATA = REPO_ROOT / "data" / "case-trujillo"

LIMITATIONS = [
    ("Los registros SINPAD son reportes administrativos de emergencia: un reporte no equivale a un fenómeno físico único "
    "y la ausencia de registro no demuestra ausencia de huaico o inundación."),
    ("Coincidir con un episodio El Niño Costero es una relación temporal; ningún evento tiene atribución causal "
    "individual verificada en esta base (color darkorange reservado: 0 casos)."),
    ("Los episodios se derivan de la serie oficial ICEN con una regla operacional cuyo umbral está pendiente de "
    "verificación directa contra la Nota Técnica ENFEN 01-2024. No se clasifica la magnitud."),
    "Varios registros de marzo de 2017 pertenecen al mismo episodio de lluvias: no son observaciones independientes.",
    ("Alto Trujillo (UBIGEO 130112) no existe en la cartografía oficial IGN v01 usada para los mapas: sus eventos se "
    "listan, pero no se pueden ubicar en el mapa distrital."),
    "Las series NASA son productos de 11–70 km: no describen la quebrada ni la calle donde ocurrió cada evento.",
]


@lru_cache(maxsize=1)
def _load() -> tuple[dict, dict, dict]:
    def read(name: str) -> dict:
        p = DATA / name
        if not p.is_file():
            raise FileNotFoundError(f"Falta {p}. Ejecuta scripts/ingest_case_trujillo.py")
        return json.loads(p.read_text(encoding="utf-8"))

    return read("sinpad_trujillo.json"), read("icen_enfen.json"), read("MANIFEST.json")


def display_class(e: dict) -> str:
    """Clase visual (plan §8.1): verificada → darkorange; coincidencia El Niño → goldenrod; resto → gris."""
    if e["causal_attribution"]["status"] == "verificada":
        return "atribucion_verificada"
    return "coincidencia_el_nino" if e["enfen"]["context"] == "coincidencia_el_nino_costero" else "fuera_de_el_nino"


def events(geo_ubigeo: str | None = None, year_from: int | None = None, year_to: int | None = None,
           focal_only: bool = True, known_geo_ids: set[str] | None = None) -> list[dict]:
    sinpad, _, _ = _load()
    out = []
    for e in sinpad["events"]:
        if focal_only and not e["focal"]:
            continue
        if geo_ubigeo and not e["ubigeo"].startswith(geo_ubigeo):
            continue
        if year_from and e["year"] < year_from or year_to and e["year"] > year_to:
            continue
        geo_id = f"pe-ign2020:{e['ubigeo']}"
        out.append({**e, "geo_id": geo_id if known_geo_ids is None or geo_id in known_geo_ids else None,
                    "display_class": display_class(e), "source": "INDECI/SINPAD (datos abiertos, ODC-BY)"})
    return out


def enfen(year_from: int | None = None, year_to: int | None = None) -> dict:
    _, icen, _ = _load()
    keep = lambda y: (year_from is None or y >= year_from) and (year_to is None or y <= year_to)
    return {
        "source": icen["source"], "rule": icen["rule"],
        "episodes": [e for e in icen["episodes"]
                     if keep(int(e["start"][:4])) or keep(int(e["end"][:4]))],
        "series": [p for p in icen["series"] if keep(p["year"])],
    }


def summary() -> dict:
    sinpad, icen, manifest = _load()
    focal = [e for e in sinpad["events"] if e["focal"]]
    ref = [e for e in focal if 2017 <= e["year"] <= 2025]
    by_class: dict[str, int] = {}
    for e in focal:
        by_class[display_class(e)] = by_class.get(display_class(e), 0) + 1
    return {
        "id": CASE_ID,
        "title": "El Niño Costero y los huaicos e inundaciones de Trujillo",
        "description": "Caso demostrativo: registros oficiales de emergencias (SINPAD) en la provincia de Trujillo, "
                       "contexto de episodios El Niño Costero (ICEN oficial) y series NASA. Ejemplo de la herramienta "
                       "general, no su límite.",
        "province_geo_id": "pe-ign2020:1301",
        "sources": [
            {"kind": "agencia_nacional", "name": sinpad["source"]["publisher"], "url": sinpad["source"]["dataset_page"],
             "license": sinpad["source"]["license"], "files": sinpad["source"]["files"]},
            {"kind": "agencia_nacional", "name": icen["source"]["publisher"], "url": icen["source"]["url"],
             "reference": icen["source"]["reference"], "sha256": icen["source"]["sha256"]},
        ],
        "enfen_rule": icen["rule"],
        "counts": manifest["counts"] | {"focal_by_display_class": by_class,
                                        "focal_by_year": {str(y): sum(1 for e in focal if e["year"] == y)
                                                          for y in sorted({e["year"] for e in focal})}},
        "reconciliation": {
            "reference": "Estudio previo NinoDetect v12/v13.1: 16 registros focales 2017–2025 en 8 distritos",
            "official_2017_2025": len(ref),
            "official_districts_2017_2025": sorted({e["district"] for e in ref}),
            "status": "coincide" if len(ref) == 16 else "difiere_revisar",
            "note": "El conteo histórico es un control, no un valor fijo: si SINPAD se actualiza, se informa la diferencia.",
        },
        "limitations": LIMITATIONS,
        "ingested_at": manifest["ingested_at"],
    }
