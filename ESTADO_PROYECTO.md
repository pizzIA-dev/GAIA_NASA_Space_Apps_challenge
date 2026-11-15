# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-14 (sesión 2) · **Fase actual:** F2 ✅ cerrada (backend + API + SDK + notebook 01).
Próximo: F1 (UI Next.js). 5 datasets NASA, fronteras global + Perú oficial, coste/tokens/límites.

## Commits
- `5cefce7` F0 — repo, CLAUDE.md, motor estadístico, CSV→pendiente explicada.
- `5a060d4` F2 — cliente EE, `AnalysisSpec`+hashes, IMERG, runner con caché, `/analyses`, golden v13.1.
- `e1f3c8c` F2 — geografías geoBoundaries v6 + fronteras oficiales Perú (IGN), ingesta y manifiesto.

## Qué funciona (verificado con datos reales)
- **Earth Engine** vía cuenta de servicio `earth-trend-backend@nasa-pizzia.iam.gserviceaccount.com` (clave fuera del repo,
  `D:\Nasa_challenge_js\`; ruta en `.env`). Diagnóstico: `apps/api/.venv/Scripts/python scripts/check_ee_auth.py`.
  Runbook: `docs/runbooks/earth-engine-service-account.md`. Volver a modo usuario: vaciar `EE_SERVICE_ACCOUNT_FILE`.
- **IMERG mensual V07** (`app/services/earth_engine/adapters.py`): idéntico a la serie v12 de Trujillo (264 meses);
  8 distritos con |diff| máx 0,21 mm. Script: `scripts/validate_imerg_vs_reference.py <UBIGEO>`.
- **Adaptadores mensuales** GLDAS/MERRA-2/MODIS NDVI/SST (ADR-0004): composición mensual en EE por bloques de años,
  recetas idénticas a la v12 (K→°C, NDVI×0,0001 con SummaryQA≤1). Validación: `scripts/validate_adapters_vs_reference.py`
  → vs v12 (2003–2024, misma geometría): MERRA-2 (T2M, TQV, U10M, V10M) idéntico (diff 0); GLDAS |diff| máx 0,16
  (corr ≥ 0,9999); NDVI |diff| máx 0,015 (corr ≥ 0,999); SST océano frente a Trujillo |diff| máx 0,002 °C (262 vs 260 meses).
  Distritos < celda (Trujillo 38 km², Víctor Larco 12 km²) → 0 píxeles en GLDAS/MERRA-2, igual que en la v12 → 422
  explicativo (no se extrapola). MERRA-2 tarda ~1,5–3,5 min por variable/territorio (720 imágenes/mes).
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
- **SDK Python** `packages/python-sdk` (`earth_trend_client`, httpx; contrato §12A.4: catalog.search, geographies.search,
  analyses.submit/wait/run/statistics/series_dataframe/manifest/plot; errores problem+json tipados; reintentos 429/503 con
  Retry-After). Instalado editable en el venv. Paridad REST↔SDK probada (`tests/contract/test_api_sdk_front_parity.py`).
  Ejemplos `examples/requests/01_trend.http`, `examples/python/01_trend_requests.py`, `02_trend_sdk.py` — **verificados en
  vivo** contra uvicorn + EE (provincia Trujillo IGN: −15,85 mm/década, IC95 [−37,15; 24,08], p=0,40).
- **Notebook Anexo D** `examples/notebooks/01_analisis_tendencias_api.ipynb` (fuente: `scripts/build_notebook_01.py`,
  regenerar/ejecutar con `--execute` y servidor levantado). 8 secciones ejecutadas con datos reales: catálogo, geografía,
  tendencia IMERG Trujillo, robustez entre 4 métodos (extracción en caché), anomalías mensuales + bootstrap, NDVI
  (+0,020/década, p=0,037), avisos de soporte espacial (MERRA en distrito 12 km²) y 422 (SST en provincia andina), manifiesto
  y HTTP puro. Kernel local "earth-trend" registrado.
- `temporal_aggregation` ahora opcional: por defecto la de la variable (total precipitación, media resto); se normaliza
  antes del hash (mismo run_id).
- **Acceso/coste/límites** (ADR-0005): `POST /analyses/estimate-cost` (niveles cached/light/heavy/too_large calibrados:
  MERRA-2 22 años ≈ 157 s est.), tokens `ets_…` revocables con scopes (solo hash en `.cache/security/`;
  `scripts/manage_api_keys.py create|list|revoke`), `GET /me`, `/me/api-keys`. Anónimo: cached+light; token: +heavy;
  413 too_large; 429 + Retry-After (20/h anónimo, 200/h token, solo extracciones nuevas); 503 source_busy (2 simultáneas).
  `AUTH_MODE=required` para exigir token. Runner dividido en `prepare()`/`execute()`. SDK: `estimate_cost()`, `me()`.
  Verificado en vivo (token creado, usado y revocado).
- **71 tests verdes** (`cd apps/api && .venv/Scripts/python -m pytest -q`).

## Datos locales (no versionados)
`NinoDetect_TODOS_LOS_ZIPS_FINAL.zip` (raíz) → tablas en `data/_local_reference/`. Solo validación, nunca runtime.
`data/_downloads/` (descargas crudas) y `.cache/` (índices, geometrías, extracciones, runs) son regenerables.

## Siguiente
1. F1 (UI Next.js) — antes auditar skills (frontend-design, react, ui-ux-pro-max) y registrar en
   docs/skills/INSTALLED_SKILLS.md; dos propuestas visuales; AppShell, selector geográfico, catálogo, serie + mapa.
2. MK corregido por autocorrelación, Kendall estacional. Docker pospuesto (no necesario aún).

## Pendiente para el caso Trujillo (F5)
- Cartografía distrital INEI reciente que incluya Alto Trujillo (130112) como nuevo `boundary_set_id`.
- Notebook 02 (Anexo D): eventos Trujillo vía API, contexto Niño ≠ causa, periodos de control.
