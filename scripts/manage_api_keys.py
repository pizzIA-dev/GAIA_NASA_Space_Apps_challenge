"""Gestión local de tokens de API (solo administradores con acceso al servidor).

    apps/api/.venv/Scripts/python scripts/manage_api_keys.py create "notebook-aldo" [--scopes catalog:read,analyses:write,runs:read]
    apps/api/.venv/Scripts/python scripts/manage_api_keys.py list
    apps/api/.venv/Scripts/python scripts/manage_api_keys.py revoke <key_id>

El token se imprime UNA sola vez; guárdalo en EARTH_TREND_API_TOKEN (nunca en el repositorio ni en chats).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import settings
from app.core.security import DEFAULT_SCOPES, ApiKeyStore


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--scopes", default=",".join(DEFAULT_SCOPES))
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("key_id")
    a = ap.parse_args()

    store = ApiKeyStore(settings.api_keys_file)
    if a.cmd == "create":
        token, rec = store.create(a.name, tuple(s.strip() for s in a.scopes.split(",") if s.strip()))
        print(f"key_id={rec.key_id} name={rec.name} scopes={','.join(rec.scopes)}")
        print("TOKEN (se muestra una sola vez):")
        print(token)
    elif a.cmd == "list":
        for rec in store.list():
            state = f"revocada {rec.revoked_at}" if rec.revoked_at else "activa"
            print(f"{rec.key_id}  {rec.name:24} {','.join(rec.scopes):40} {state}")
    else:
        print("revocada" if store.revoke(a.key_id) else "no encontrada o ya revocada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
