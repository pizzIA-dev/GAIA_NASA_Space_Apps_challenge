# CLAUDE.md — GaIA (observatorio ambiental; antes «Earth Trend Studio»)

> **Al iniciar sesión, lee SOLO este archivo y `ESTADO_PROYECTO.md`.** No releas el plan completo (146 KB):
> consulta secciones puntuales con `grep -n "^#" PLAN_MAESTRO_PLATAFORMA_TENDENCIAS_NASA_WEB.md` y luego `Read` con offset.

## Qué es
Plataforma web + API REST v1 + SDK Python para detectar tendencias del sistema terrestre con datos NASA vía
Google Earth Engine (NASA Space Apps 2026 — "Be An Earth System Trend Detective!"). Responde: ¿qué cambia?,
¿dónde?, ¿cuánto?, ¿es significativo? Caso demo opcional: El Niño Costero + huaicos en Trujillo (NO es la marca).

**Prioridad desde 2026-11-15 (ADR-0013):** la experiencia principal es el **Panel** (`/`): territorio (cualquier país) +
periodo + variables + método + nivel de confianza → una tarjeta por variable. Módulos opcionales: Explorar (detalle de
una variable), Análisis avanzado (`/estudio`), Atlas, Casos de estudio (`/historias`). El caso Trujillo y ENFEN los
trabajan los usuarios: no ampliarlos. Punto de recuperación previo: tag `pre-dashboard-2026-11-15`.

## Mapa rápido del plan (líneas en PLAN_MAESTRO_...md)
| Tema | Línea |
|---|---|
| Reglas innegociables §0 | 32 |
| Resolución/granularidad §3 | 117 |
| Motor estadístico §7 (métodos, IC, guardarraíles) | 386 |
| Visualizaciones §8 | 514 |
| Caso Trujillo §9 | 567 |
| Stack y reglas GEE §10 | 608 |
| Contratos JSON (spec, respuesta) §11 | 692 |
| Endpoints API §12 / SDK §12A | 838 / 916 |
| Estructura repo §13 | 1102 |
| Fases F0–F7 §14 | 1206 |
| Backlog P0/P1 §15 | 1322 |
| Pruebas científicas §16 | 1368 |
| Skills §18 | 1494 |
| Orden de arranque §22 | 1724 |
| IA/navegación §4 · Arte/UX §5 | 168 · 207 |
| Decisiones cerradas Anexo A / Entregables API-SDK Anexo D | 1781 / 1845 |

## Reglas que no se negocian
- GEE solo desde backend; nunca credenciales en el navegador ni en el repo. Proyecto GEE por env (`EE_PROJECT`).
- Sin dato = `null` con razón; nunca 0 ni "NS" inventado. Sin inferencia suficiente → `status=insufficient_evidence`.
- Estimador e IC compatibles (Theil–Sen ≠ IC de OLS). p-valor ≠ probabilidad de verdad.
- El frontend NO calcula estadística: UI, API y SDK usan el mismo motor (`apps/api/app/services/statistics`).
- Sin notebooks/ZIP/Base64 como dependencia. Coincidencia temporal El Niño ≠ causalidad.
- UI editorial/cartográfica propia; prohibido look de "dashboard IA" (glassmorphism, degradado púrpura, tarjetas genéricas).

## Entorno (verificado 2026-11-14)
Windows 11 · Python 3.13.5 · Node 24 / npm 11 · git 2.37. **No instalados:** uv, pnpm, docker, gcloud (no necesarios).
Backend: venv `apps/api/.venv` (pip). Tests: `cd apps/api && .venv/Scripts/python -m pytest -q`.
Web: `apps/web` (npm; Next 16, TS 5.9). `npm --prefix apps/web run dev` (genera tokens y copia worker MapLibre) ·
`npx tsc --noEmit` · `npx next build` · `npm run test:e2e` (Playwright, Edge) · `npm run check:contrast`. Servidores para el panel del navegador: `.claude/launch.json` (api, web).
Earth Engine: cuenta de servicio (ruta en `.env`, clave fuera del repo); diagnóstico `scripts/check_ee_auth.py`.
CI: `.github/workflows/ci.yml` sin EE (fixtures reales en `scientific/fixtures/e2e`); ver `docs/runbooks/ci.md`.

## Flujo git (acordado con el usuario 2026-11-14)
- Remoto `github.com/pizzIA-dev/NASA_Space_Apps_challenge` (privado, organización pizzIA-dev; antes RoAlro, redirige). **Nunca push directo a `main`.**
- Cada tarea: rama corta (`feat/…`, `fix/…`, `chore/…`) → PR con `gh pr create` → CI verde → `gh pr merge --squash --delete-branch`.
- Autorización permanente del usuario para abrir PR y hacer merge con CI en verde. Nunca merge en rojo.
- `gh` en `C:/Program Files/GitHub CLI` (en Bash: `export PATH="$PATH:/c/Program Files/GitHub CLI"`).
- El plan gratuito no impone rulesets en repos privados: la protección es por disciplina.

## Documentación
- `ESTADO_PROYECTO.md` — estado vivo: qué está hecho, qué sigue, bloqueos. **Actualizar al cerrar cada sesión.**
- Vault Obsidian `D:/Obsidian_vaults/NASA_Space_Apps_challenge/` — notas largas (decisiones/ADR, bitácora de sesiones,
  hallazgos de fuentes). Índice: `00_INDICE.md`. Escribir con las herramientas de archivo normales.
- `docs/decisions/` — ADRs del repo.
