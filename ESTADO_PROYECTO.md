# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-14 (sesión 1) · **Fase actual:** F0 (fundación) — parcialmente completada

## Hecho
- [x] Repo git inicializado; estructura de carpetas del plan §13 creada (vacía salvo backend).
- [x] `CLAUDE.md` (reglas + mapa de líneas del plan), `README.md`, `.gitignore`, `.env.example`.
- [x] Backend `apps/api` (FastAPI 0.135, Python 3.13, venv en `apps/api/.venv`, deps en `requirements.lock.txt`).
- [x] Motor estadístico `app/services/statistics/trend_core.py`: OLS (clásico/HAC/bootstrap), Theil–Sen
      (analítico/bootstrap), Mann–Kendall con empates, BH-FDR, autocorrelación lag-1, guardarraíles
      (N mínimo, serie constante, cobertura). Matriz `COMPATIBILITY` → ADR-0001.
- [x] `app/services/analyses/series_csv.py`: CSV materializado (§11.4) → pendiente + procedencia + explicación.
- [x] Endpoints: `GET /api/v1/health`, `GET /api/v1/catalog/capabilities`.
- [x] **15 tests verdes** (`tests/scientific/test_methods.py`, `tests/contract/test_f0_acceptance.py`).
      Criterio de aceptación F0 (CSV → pendiente + IC explicada sin GEE/UI) ✅.

## Siguiente (en orden, plan §22)
1. **Credenciales GEE** (bloqueo, ver abajo) → instalar `earthengine-api` (`pip install -e .[gee]`).
2. Adaptador `IMERGMonthly` (`NASA/GPM_L3/IMERG_MONTHLY_V07`) en `app/services/earth_engine/` con interfaz
   `DatasetAdapter` (validate, availability, extract, unit_transform, quality_report) — §13.1.
3. Contrato Pydantic de `analysis_spec` (§11.2) + hash canónico (§11.5) + `POST /api/v1/analyses` y
   `GET /analyses/{id}/statistics|series|manifest` (§12.1). Errores `application/problem+json`.
4. SDK Python mínimo `packages/python-sdk` (`earth_trend_client`) + test de paridad API/SDK.
5. Pendientes estadísticos: MK corregido por autocorrelación, Kendall estacional, anomalías mensuales.
6. Luego F1 (UI Next.js) — antes, búsqueda/auditoría de skills (§18.2) y registro en `docs/skills/INSTALLED_SKILLS.md`.

## Bloqueos / decisiones del usuario
- **GEE:** falta proyecto Cloud registrado y método de auth (cuenta de servicio JSON fuera del repo, o
  `earthengine authenticate` local). El plan menciona un proyecto de investigación existente: confirmar si
  está habilitado y elegible (no comercial). gcloud y earthengine CLI **no instalados**.
- **Docker no instalado:** `docker compose` de F0 queda pospuesto; desarrollo con venv + SQLite/archivos.
- **F0 pendiente que depende de datos externos:** golden tests contra "CSV v13.1" del maestro Trujillo (16 eventos /
  8 distritos) — no hay ese CSV en el repo y el plan prohíbe depender de notebooks; reconstruir desde SINPAD en F5.

## Cómo verificar rápido
`cd apps/api && .venv/Scripts/python -m pytest -q`
