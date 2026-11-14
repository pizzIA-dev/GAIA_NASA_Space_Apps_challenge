# Earth Trend Studio *(nombre provisional)*

Laboratorio visual para investigar cómo cambia la Tierra con datos NASA (vía Google Earth Engine):
**¿qué cambia?, ¿dónde?, ¿cuánto? y ¿es estadísticamente significativo?** — NASA Space Apps Challenge 2026,
*Be An Earth System Trend Detective!*

Web, API REST v1 y SDK Python comparten un único motor científico. Especificación completa:
[PLAN_MAESTRO_PLATAFORMA_TENDENCIAS_NASA_WEB.md](PLAN_MAESTRO_PLATAFORMA_TENDENCIAS_NASA_WEB.md).
Estado actual: [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md).

## Backend (FastAPI) — desarrollo local

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn app.main:app --reload            # http://localhost:8000/docs
```

No se requieren notebooks, ZIP ni credenciales para ejecutar las pruebas. Earth Engine se configura solo por
variables de entorno (ver `.env.example`).
