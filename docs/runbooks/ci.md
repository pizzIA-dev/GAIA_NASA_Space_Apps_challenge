# Runbook — Integración continua (GitHub Actions)

Workflow: `.github/workflows/ci.yml`. Se ejecuta en `push` a main/master, en pull requests y manualmente.
**Requiere que el repositorio esté en GitHub** (hoy no tiene remoto).

| Job | Qué verifica | Notas |
|---|---|---|
| `api` | `ruff` + `pytest` (backend y SDK) | Instala desde `apps/api/pyproject.toml` (`[dev]`), no desde el lock de Windows. No instala `earthengine-api`: ninguna prueba lo necesita. |
| `web` | contraste WCAG de tokens, TypeScript estricto, build de producción | `npm ci` desde `apps/web/package-lock.json`. |
| `e2e` | Playwright (Chromium) contra API + web | Depende de los dos anteriores. Earth Engine **deshabilitado**; caché sembrada con `scientific/fixtures/e2e`. |

## Por qué fixtures y no credenciales en CI
La clave de la cuenta de servicio no se sube a GitHub. Las pruebas E2E usan **series NASA reales ya extraídas**
(12 IMERG + 3 NDVI, provincia de Trujillo e IGN; ver `scientific/fixtures/e2e/MANIFEST.json`). Cualquier petición no
cubierta responde `503 source_unavailable`: el CI nunca inventa datos.

## Regenerar los fixtures (si cambian las pruebas E2E o el formato de extracción)
Requiere Earth Engine configurado en local.
```bash
apps/api/.venv/Scripts/python scripts/e2e_fixtures.py subset .cache_e2e
cd apps/web && CACHE_DIR=.cache_e2e npx playwright test   # extrae SOLO lo que usan las pruebas
cd ../.. && apps/api/.venv/Scripts/python scripts/e2e_fixtures.py collect .cache_e2e
```
Detén antes cualquier API en el puerto 8000 (Playwright la reutilizaría con otra caché).

## Reproducir el CI en local
```bash
apps/api/.venv/Scripts/python scripts/e2e_fixtures.py seed .cache_ci
cd apps/web && CI=1 CACHE_DIR=.cache_ci EE_PROJECT= EE_SERVICE_ACCOUNT_FILE= npx playwright test
```
En Windows Playwright usa Edge (`msedge`); en CI, Chromium (`PW_CHANNEL=""`).

## Verificado (2026-11-14, local)
`api` en venv limpio: ruff OK, 79/79 (sin `earthengine-api`). `web` tras `npm ci`: contraste 34/34, tsc OK, build OK.
`e2e` con fixtures y EE deshabilitado: 12/12. **Pendiente:** primera ejecución real en GitHub (Chromium/Linux).
