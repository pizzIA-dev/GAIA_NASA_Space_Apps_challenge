# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-14 (sesión 2) · **Fase actual:** F2 (Earth Engine + API) — IMERG + geografías
(global ADM0–2 y Perú oficial ADM1–3) funcionando; faltan adaptadores GLDAS/MERRA-2/MODIS.

## Commits
- `5cefce7` F0 — repo, CLAUDE.md, motor estadístico, CSV→pendiente explicada.
- `5a060d4` F2 — cliente EE, `AnalysisSpec`+hashes, IMERG, runner con caché, `/analyses`, golden v13.1.
- **Sin commit:** geografías geoBoundaries + fronteras oficiales Perú (IGN).

## Qué funciona (verificado con datos reales)
- **Earth Engine** vía cuenta de servicio `earth-trend-backend@nasa-pizzia.iam.gserviceaccount.com` (clave fuera del repo,
  `D:\Nasa_challenge_js\`; ruta en `.env`). Diagnóstico: `apps/api/.venv/Scripts/python scripts/check_ee_auth.py`.
  Runbook: `docs/runbooks/earth-engine-service-account.md`. Volver a modo usuario: vaciar `EE_SERVICE_ACCOUNT_FILE`.
- **IMERG mensual V07** (`app/services/earth_engine/adapters.py`): idéntico a la serie v12 de Trujillo (264 meses);
  8 distritos con |diff| máx 0,21 mm. Script: `scripts/validate_imerg_vs_reference.py <UBIGEO>`.
- **Motor estadístico** reproduce las tendencias v13.1 (8 distritos, Sen/HAC/IC/p < 2e-3).
- **Geografías** (`app/services/geographies/geoboundaries.py`, ADR-0002): geoBoundaries v6 ADM0–ADM2 global en EE;
  `geo_id = gb6:<ISO3>[:<ADMn>:<shapeID>]`; índice por país cacheado en `.cache/geographies/` (Perú: 222 unidades,
  ~20 s la primera vez); jerarquía calculada; geometría nunca descargada para analizar.
  Ej.: provincia Trujillo `gb6:PER:ADM2:86281439B80561874516771` (1782 km²) → IMERG anual 2003–2024 Theil–Sen
  −15,9 mm/década, IC95 [−37,1; 24,0], p=0,40 (no significativa).
- **Perú oficial** (`app/services/geographies/peru_ign.py`, ADR-0003): IGN vía HDX COD-AB v01 (2020), CC BY-IGO,
  ADM1–ADM3 con UBIGEO (25/196/1873). `geo_id = pe-ign2020:<UBIGEO>`. Por defecto para `country=PER`.
  **Requiere ingesta** en máquina nueva: `apps/api/.venv/Scripts/python scripts/ingest_pe_boundaries.py`
  (descarga 45 MB, verifica SHA256; manifiesto en `data/manifests/`). Registro que enruta geo_ids:
  `app/services/geographies/registry.py`. Validado: 7 distritos focales ≈ serie v12 (|diff| máx 0,2 mm).
  ⚠️ **Alto Trujillo (130112) no existe en IGN v01** (está dentro de El Porvenir/Huanchaco) → 404; para F5 hará falta INEI reciente.
- **API:** `/health`, `/catalog/capabilities|datasets|variables`, `/geographies/boundary-sets|countries|search|{geo_id}`
  (`?geometry=simplified`), `POST /analyses` (custom_geometry o geo_ids), `GET /analyses/{id}[/statistics|/series|/manifest]`.
  Errores problem+json. Aviso automático si el territorio < 1 píxel nativo.
- **49 tests verdes** (`cd apps/api && .venv/Scripts/python -m pytest -q`).

## Datos locales (no versionados)
`NinoDetect_TODOS_LOS_ZIPS_FINAL.zip` (raíz) → tablas en `data/_local_reference/`. Solo validación, nunca runtime.
`data/_downloads/` (descargas crudas) y `.cache/` (índices, geometrías, extracciones, runs) son regenerables.

## Siguiente
1. Adaptadores GLDAS/MERRA-2 (composición mensual en EE), MODIS NDVI, SST oceánica.
2. SDK Python `packages/python-sdk` + test de paridad API/SDK.
3. MK corregido por autocorrelación, Kendall estacional. Docker pospuesto (no necesario aún).

## Pendiente para el caso Trujillo (F5)
- Cartografía distrital INEI reciente que incluya Alto Trujillo (130112) como nuevo `boundary_set_id`.
