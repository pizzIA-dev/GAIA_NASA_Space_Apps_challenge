# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-14 (sesión 2) · **Fase actual:** F2 (Earth Engine + API) — IMERG real validado; faltan geografías ADM y más adaptadores

## Hecho
- **F0** (commit 5cefce7): repo, CLAUDE.md, motor estadístico `trend_core.py` (OLS/HAC/bootstrap, Theil–Sen,
  Mann–Kendall, BH-FDR, guardarraíles), CSV→pendiente explicada.
- **F2 (sesión 2, sin commit aún):**
  - `earthengine-api` 1.7.52 en venv; `.env` local con `EE_PROJECT=nasa-pizzia` (ignorado por git).
  - `app/core/config.py` carga `.env` sin dependencias.
  - `app/schemas/analysis.py`: contrato `AnalysisSpec` (§11.2), `spec_hash` y `extraction_key` separados (§11.5).
  - `app/services/earth_engine/client.py` (init perezoso; cuenta de servicio o credenciales de usuario) y
    `adapters.py`: `IMERGMonthly` real (mm/h × horas del mes → mm), registro de 4 datasets "planned" con IDs verificados
    (GLDAS, MERRA-2, MOD13Q1, MODIS-Aqua SST — no MUR).
  - `app/services/analyses/runner.py`: caché de extracción + run persistido en `.cache/`; año incompleto → null;
    anomalía mensual con climatología base.
  - API: `GET /catalog/datasets|variables`, `POST /analyses`, `GET /analyses/{id}[/statistics|/series|/manifest]`,
    errores `application/problem+json` (404/409/422/503).
  - **30 tests verdes**, incluido golden test vs resultados v13.1 de Trujillo (8 distritos, Sen/HAC/IC/p dentro de 2e-3).
- ZIP del usuario `NinoDetect_TODOS_LOS_ZIPS_FINAL.zip` (raíz, ignorado) → datos/tablas extraídos en
  `data/_local_reference/` (ignorado). Solo validación; nunca runtime. Notebooks NO extraídos.

## Earth Engine: FUNCIONANDO (re-autenticado con la cuenta dueña de `nasa-pizzia`)
- Validación real IMERG 2003–2024 vs serie v12, 8 distritos × 264 meses: Trujillo y Víctor Larco idénticos (diff 0);
  resto |diff| medio ≤0,026 mm, máx 0,21 mm (≈0,1 % de la media; probable diferencia de ponderación de píxeles de borde).
  Script: `apps/api/.venv/Scripts/python scripts/validate_imerg_vs_reference.py <UBIGEO>`.
- E2E por API con un ROI nuevo (Lima, anual, OLS-HAC) → 200 con serie real, IC, p y procedencia.
- Criterio F2 cumplido para ROI libre; falta selección por país/ADM (`geo_ids`).
- **Cuenta de servicio** `earth-trend-backend@nasa-pizzia.iam.gserviceaccount.com` registrada en `.env`
  (`EE_SERVICE_ACCOUNT_EMAIL`). **ACTIVA:** clave JSON fuera del repo (`D:\Nasa_challenge_js\`, ruta en
  `EE_SERVICE_ACCOUNT_FILE`); `check_ee_auth.py` → `modo=service_account` OK; validación IMERG vs v12 (sin caché) idéntica
  y `/health` reporta `service_account`. Runbook: `docs/runbooks/earth-engine-service-account.md`.
  Si falla: vaciar `EE_SERVICE_ACCOUNT_FILE` para volver a modo usuario.
- 36 tests verdes.

## Siguiente
1. Geografías: geoBoundaries ADM0–2 (verificar colección en GEE) + adaptador oficial INEI para Perú; `geo_ids`.
2. Adaptadores GLDAS/MERRA-2 (composición mensual en EE), MODIS NDVI, SST oceánica.
3. SDK Python `packages/python-sdk` + test de paridad; `/catalog/capabilities` ya lista métodos.
4. MK corregido por autocorrelación, Kendall estacional. Docker pospuesto (no necesario aún).

## Cómo verificar rápido
`cd apps/api && .venv/Scripts/python -m pytest -q` · servidor: `.venv/Scripts/python -m uvicorn app.main:app --reload`
