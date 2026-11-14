"""Diagnóstico de autenticación Earth Engine (no imprime secretos). Uso:

    apps/api/.venv/Scripts/python scripts/check_ee_auth.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import settings
from app.services.earth_engine.client import EarthEngineUnavailable, auth_mode, get_ee


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"EE_PROJECT={settings.ee_project}")
    print(f"EE_SERVICE_ACCOUNT_EMAIL={settings.ee_service_account_email}")
    print(f"EE_SERVICE_ACCOUNT_FILE={'(definido)' if settings.ee_service_account_file else '(vacío → modo usuario)'}")
    try:
        ee = get_ee()
        n = ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07").filterDate("2024-01-01", "2024-04-01").size().getInfo()
    except EarthEngineUnavailable as exc:
        print(f"FALLO: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — diagnóstico: mostrar cualquier error de permisos de EE
        print(f"FALLO en consulta de prueba: {type(exc).__name__}: {exc}")
        return 1
    print(f"OK · modo={auth_mode()} · consulta de prueba IMERG ene–mar 2024: {n} imágenes (esperado 3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
