"""Ensambla las propuestas visuales F1 como HTML autocontenidos (datos + JS en línea) para abrir sin servidor.

Uso:  apps/api/.venv/Scripts/python scripts/build_ux_prototypes.py   (requiere docs/ux/prototypes/data.json)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "docs" / "ux" / "prototypes"
OUTS = {"A.html": "A_cuaderno_de_campo.html", "B.html": "B_mesa_de_observacion.html"}

data = (P / "data.json").read_text(encoding="utf-8")
js = (P / "src" / "proto.js").read_text(encoding="utf-8")
for src, dst in OUTS.items():
    html = (P / "src" / src).read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", data.replace("</", "<\\/")).replace("/*__PROTO_JS__*/", js)
    (P / dst).write_text(html, encoding="utf-8")
    print(f"OK → {P / dst} ({(P / dst).stat().st_size / 1024:.0f} KB)")
