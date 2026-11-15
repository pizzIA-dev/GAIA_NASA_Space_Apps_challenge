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
.venv/Scripts/python -m pip install -e ../../packages/python-sdk  # SDK (usado por las pruebas de paridad)
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn app.main:app --reload            # http://localhost:8000/docs
```

No se requieren notebooks, ZIP ni credenciales para ejecutar las pruebas. Earth Engine se configura solo por
variables de entorno (ver `.env.example` y `docs/runbooks/earth-engine-service-account.md`).

Fronteras oficiales del Perú (una vez por máquina): `python scripts/ingest_pe_boundaries.py` (descarga 45 MB de HDX,
verifica SHA256).

## Datasets NASA disponibles

IMERG V07 mensual (precipitación) · GLDAS Noah 2.1 (humedad del suelo, temperatura) · MERRA-2 (T2M, vapor, viento) ·
MODIS NDVI (MOD13Q1) · SST MODIS-Aqua L3SMI. Fronteras: geoBoundaries v6 (global ADM0–2) e IGN Perú (ADM1–3, UBIGEO).

## SDK Python y ejemplos

```bash
pip install -e packages/python-sdk[pandas]
```

```python
from earth_trend_client import EarthTrendClient
client = EarthTrendClient("http://localhost:8000/api/v1")
region = client.geographies.search("trujillo", country="PER", level="ADM2")[0]
run = client.analyses.run({"data": {"dataset_id": "nasa-gpm-imerg-monthly-v07",
                                    "variable_id": "precipitation_mm_month"},
                           "geography": {"geo_ids": [region["geo_id"]]},
                           "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"}})
print(client.analyses.statistics(run.id))
```

Ejemplos: `examples/requests/01_trend.http` (REST crudo), `examples/python/01_trend_requests.py` (sin SDK),
`examples/python/02_trend_sdk.py` (SDK).

## Acceso, coste y límites

Catálogo, geografías y resultados ya calculados son públicos. Los análisis nuevos ligeros pueden hacerse sin registro;
los pesados (p. ej. MERRA-2 horario de 20 años) requieren token. Antes de lanzar uno:
`POST /api/v1/analyses/estimate-cost` (o `client.analyses.estimate_cost(spec)`), y `GET /api/v1/me` para ver tu cupo.

```bash
python scripts/manage_api_keys.py create "mi-notebook"   # el token se muestra una sola vez
python scripts/manage_api_keys.py list
python scripts/manage_api_keys.py revoke <key_id>
```

## Atribuciones

Datos NASA (GPM IMERG, GLDAS, MERRA-2, MODIS) procesados mediante Google Earth Engine; coberturas, cuotas y tiempos
de respuesta sujetos al servicio. Límites: geoBoundaries gbOpen v6.0.0 (CC BY 4.0); IGN Perú vía OCHA HDX COD-AB
(CC BY-IGO).
