# GaIA

Plataforma web, API REST y SDK de Python para detectar **tendencias del sistema terrestre con datos NASA** en cualquier
territorio del mundo: **¿qué cambia?, ¿dónde?, ¿cuánto? y ¿es estadísticamente significativo?**
NASA Space Apps Challenge 2026 · *Be An Earth System Trend Detective!*

| | |
|---|---|
| **Web** | https://gaia-chi-five.vercel.app |
| **API REST v1** | https://gaia-api-sk9y.onrender.com/api/v1 |
| **Documentación de la API (OpenAPI)** | https://gaia-api-sk9y.onrender.com/docs |

> Alojamiento gratuito: si nadie la usó en los últimos 15 minutos, la primera visita tarda 1–2 minutos mientras el
> servidor despierta. Lima (Perú) está precargada; otros territorios se calculan la primera vez y quedan guardados.

## Qué hace

- **Panel:** eliges territorio (búsqueda mundial), periodo, variables, método de tendencia y nivel de confianza (90/95/99 %);
  cada variable muestra su serie anual, la tendencia por década, el intervalo de confianza, la prueba y si hay evidencia.
- **Atlas:** mapa de tendencias por subdivisiones del territorio. **Análisis avanzado:** compara territorios (corrección
  por pruebas múltiples, diferencia de pendientes con su propio intervalo). **Fuentes** y **Métodos** documentan todo.
- La web, la API y el SDK usan **el mismo motor estadístico**: la misma especificación da el mismo resultado (`run_id`).

## Fuentes de datos

| Variable en GaIA | Producto NASA | Colección en Google Earth Engine |
|---|---|---|
| Lluvia | GPM IMERG Final Monthly V07 (NASA GES DISC) | [`NASA/GPM_L3/IMERG_MONTHLY_V07`](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07) |
| Temperatura del aire, vapor de agua, viento | MERRA-2 M2T1NXSLV (NASA GMAO) | [`NASA/GSFC/MERRA/slv/2`](https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_slv_2) |
| Humedad del suelo, temperatura cerca del suelo | GLDAS Noah V2.1 (NASA GES DISC) | [`NASA/GLDAS/V021/NOAH/G025/T3H`](https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H) |
| Vegetación (verdor, NDVI) | MODIS Terra MOD13Q1 v061 (NASA LP DAAC) | [`MODIS/061/MOD13Q1`](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1) |
| Temperatura del mar | MODIS-Aqua L3SMI SST (NASA OB.DAAC) | [`NASA/OCEANDATA/MODIS-Aqua/L3SMI`](https://developers.google.com/earth-engine/datasets/catalog/NASA_OCEANDATA_MODIS-Aqua_L3SMI) |

Fronteras: [geoBoundaries gbOpen v6.0.0](https://www.geoboundaries.org) (mundial, CC BY 4.0; Runfola et al. 2020) e
Instituto Geográfico Nacional del Perú vía [OCHA HDX COD-AB](https://data.humdata.org/dataset/cod-ab-per) (CC BY-IGO).
Earth Engine se usa solo desde el servidor (proyecto registrado para uso no comercial); ninguna credencial está en el
repositorio ni en el navegador.

**Métodos:** Theil–Sen, Mann–Kendall, OLS con HAC, tamaño muestral efectivo AR(1) (Santer et al. 2000, por defecto),
bootstrap por bloques y Benjamini–Hochberg. Su cobertura real se midió por simulación:
[`scientific/reports/cobertura_ic.md`](scientific/reports/cobertura_ic.md). Decisiones: [`docs/decisions/`](docs/decisions/).

## SDK de Python

```python
from earth_trend_client import EarthTrendClient   # pip install -e packages/python-sdk
c = EarthTrendClient(base_url="https://gaia-api-sk9y.onrender.com/api/v1")
run = c.analyses.run({"data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
                      "geography": {"geo_ids": ["pe-ign2020:15"]},
                      "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "year"}})
print(run.id, c.analyses.statistics(run.id))
```

Estructura: `apps/api` (FastAPI + motor estadístico), `apps/web` (Next.js), `packages/python-sdk` (SDK),
`scripts/` (ingesta y validación), `scientific/` (fixtures, informes), `docs/` (decisiones y guías). Despliegue gratuito:
[`docs/runbooks/despliegue-gratuito.md`](docs/runbooks/despliegue-gratuito.md).

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

## Web (Next.js) — desarrollo local

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000/explorar  (requiere la API en :8000)
```

La web no calcula estadística: construye la misma especificación que el SDK y la envía a `POST /api/v1/analyses`.
Tokens de diseño: `packages/design-tokens/tokens.json` (dirección «Cuaderno de campo», ADR-0006).

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
