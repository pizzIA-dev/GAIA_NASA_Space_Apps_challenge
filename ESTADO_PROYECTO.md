# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-15 (cierre de la sesión 3) · **Producto: GaIA** · **Estado: publicado y funcional.**
El desarrollo de la plataforma está terminado; queda material de presentación (ver «Siguiente»).
Historial técnico detallado hasta esta fecha (validaciones, cifras, decisiones intermedias): vault Obsidian,
nota «Historial tecnico hasta 2026-11-15». Decisiones: `docs/decisions/ADR-0001…0014`.

## Enlaces públicos
| | |
|---|---|
| Web | https://gaia-chi-five.vercel.app |
| API REST v1 | https://gaia-api-sk9y.onrender.com/api/v1 |
| Documentación API (OpenAPI) | https://gaia-api-sk9y.onrender.com/docs |
| Repositorio (público desde 2026-11-15) | https://github.com/pizzIA-dev/NASA_Space_Apps_challenge |
| Ficha de fuentes para evaluadores | artifact de Claude (privado hasta que el usuario lo comparta) |

## Qué es hoy GaIA
- **Panel** (`/`, experiencia principal): territorio de cualquier país (búsqueda mundial; Perú con fronteras IGN),
  periodo, variables con nombres sencillos, método de tendencia y nivel de confianza 90/95/99 %. Una tarjeta por
  variable: cambio por década, IC, prueba y p, gráfico; detalles y procedencia plegados. Ejemplo por defecto: **Lima**.
- **Explorar** (detalle de una variable, «Ver detalle» desde el Panel): mapa de subdivisiones, ciclo estacional,
  anomalías mensuales, exportación CSV/JSON/SVG/PNG.
- **Atlas:** pendiente por subdivisiones de cualquier territorio, 4 variables, BH-FDR por mapa.
- **Análisis avanzado** (`/estudio`): hasta 4 territorios, paneles arrastrables, q-valores BH-FDR, diferencia de
  pendientes A − B con IC propio (solo Theil–Sen).
- **Fuentes** (nombres técnicos, productos, bandas, licencias) y **Métodos** (matriz de compatibilidad, glosario).
- **Idioma ES/EN** (selector en la cabecera; español por defecto, se recuerda en el navegador, mismas URL). Textos en
  pares `t("es", "en")` junto a su uso (`lib/i18n.ts`); los textos de la API se traducen en la web con `apiText()`
  (la API sigue en español). Todo componente que muestre texto llama a `useT()`/`useLang()` (hidratación segura).
- **Sin caso de estudio en la plataforma:** el caso Trujillo/ENFEN lo trabajan los usuarios. Los endpoints `/cases`
  existen pero están desactivados por defecto (`ENABLE_CASE_STUDIES=true` para activarlos; las pruebas lo hacen).

## Ciencia (motor `trend_core` 0.2)
- Estimadores Theil–Sen (por defecto) y OLS; IC: n efectivo AR(1) (por defecto, Santer 2000), analítico, HAC,
  bootstrap por bloques sobre pares; pruebas Mann–Kendall (n efectivo / clásica), t. Veredicto con α = 1 − nivel;
  con varios territorios manda el q-valor.
- Cobertura medida por simulación (`scripts/coverage_study.py` → `scientific/reports/cobertura_ic.md`):
  métodos por defecto 94–96 % / error tipo I 3–7 % con φ ≤ 0,3 (n = 22 años); con φ = 0,6 ≈ 87–89 % / 9 % (se avisa).
- Datos: IMERG V07 mensual, MERRA-2 (T2M, TQV, U10M, V10M), GLDAS Noah V2.1 (humedad del suelo, temperatura),
  MODIS Terra NDVI, MODIS-Aqua SST. Validados contra el estudio previo (v12). Sin dato = null, nunca 0.

## Publicación (US$ 0, ADR-0014)
- **Web:** Vercel Hobby, proyecto `gaia` (cuenta `pizziaperu-8760`). Redesplegar: `cd apps/web && npx vercel deploy --prod`
  (compila en Vercel; `apps/web` es autosuficiente: `src/styles/tokens.css` versionado + `scripts/sync-tokens.mjs`).
  Integración Git de Vercel desconectada (Hobby no desplegaba el repo privado de organización; ahora es público y
  podría reconectarse si se quiere despliegue automático de la web).
- **API:** Render Free, servicio `gaia-api` (srv-dbsvth56e07s73b1st70, región Virginia), **auto-deploy en cada merge
  a `main`** (requiere la app de Render instalada en la organización pizzIA-dev ✅). Compilación: dependencias +
  fronteras IGN (HDX, SHA-256) + siembra de caché (`scripts/e2e_fixtures.py seed`, incluye `data/demo-cache`: Lima,
  sus provincias y Arequipa → portada instantánea, ~1 s por variable).
- **Earth Engine en Render:** Secret File `ee-service-account.json` (cuenta `earth-trend-backend@nasa-pizzia`,
  proyecto `REGISTERED_NOT_COMMERCIALLY`). Variables: `EE_PROJECT`, `EE_SERVICE_ACCOUNT_FILE`, `EE_SERVICE_ACCOUNT_EMAIL`,
  `ALLOWED_ORIGINS=https://gaia-chi-five.vercel.app`, `CACHE_DIR`, `PYTHON_VERSION`.
- **Límites (gratuitos):** Render se duerme tras 15 min (1–2 min para despertar; la web lo avisa), caché efímera,
  0,1 CPU, 5 GB/mes de salida (respuestas gzip). Sin tarjeta en Render ni Vercel → al superar límites se suspende, no se
  cobra. Sin token, todas las variables 2001–2024 en territorios ≲ 400 000 km² (umbral «ligero» ampliado, ADR-0005);
  cupo anónimo 20 extracciones/h por IP real (`--proxy-headers`).
- **Claves:** la clave de API de Render compartida en el chat fue **revocada** (2026-11-15). No hay secretos en el
  historial del repositorio (revisado al hacerlo público). La clave de EE local sigue en `D:\Nasa_challenge_js\`.

## Desarrollo local
- API: `cd apps/api && .venv/Scripts/python -m pytest -q` (**124** pruebas) · servidor: `.claude/launch.json` (api :8000).
- Web: `npm --prefix apps/web run dev` · `npx tsc --noEmit` · `npx playwright test` (**33** E2E, Edge local) ·
  `npm run check:contrast` (WCAG 2.1 AA).
- Las E2E usan el territorio de prueba `pe-ign2020:1301` explícito en la URL (fixtures de CI sin Earth Engine); no
  aparece en la plataforma.
- Regenerar la caché de demostración si cambian los ejemplos por defecto o la versión de un producto:
  `apps/api/.venv/Scripts/python scripts/demo_cache.py collect` (una prueba de contrato lo exige).

## Git
Ruleset «main protegida» (activo): PR obligatorio + checks «API y SDK (ruff + pytest)», «Web (contraste + tipos +
build)», «E2E Playwright (fixtures NASA, sin Earth Engine)». Flujo: rama → PR → `gh pr merge --squash --delete-branch`.
El usuario prefiere velocidad: correr pruebas locales antes de subir. Tag de recuperación: `pre-dashboard-2026-11-15`.

## Datos locales (no versionados)
`NinoDetect_TODOS_LOS_ZIPS_FINAL.zip` → `data/_local_reference/` (solo validación). `data/_downloads/` y `.cache/`
son regenerables. `apps/web/.vercel/` y `apps/web/.env.local` (CLI de Vercel) están excluidos de Git.

## Siguiente
1. **Presentación del challenge:** guía de uso breve, video de demostración, diapositivas (arquitectura, fuentes,
   límites) y compartir la ficha de fuentes con los evaluadores.
2. Prueba con lector de pantalla (NVDA).
3. Opcionales: reconectar la integración Git de Vercel (repo ya público), brush temporal, Kendall estacional,
   dependencia de largo plazo (ENSO) más allá de AR(1), base de datos si se necesita persistencia (skill local
   `sql-code-review`), rotar la clave de la cuenta de servicio al cerrar el challenge.
