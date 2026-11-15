# ESTADO DEL PROYECTO — leer al inicio de cada sesión

**Última actualización:** 2026-11-15 (sesión 3) · **Producto: GaIA** · F0–F4 entregadas; F5 entregada en lo que
corresponde a la plataforma (el caso Trujillo/ENFEN lo trabajan los usuarios). **Realineación UX (ADR-0013):** la
portada es el **Panel ambiental** (territorio mundial + periodo + variables + método + nivel de confianza). Módulos
opcionales: Explorar (detalle), Análisis avanzado (`/estudio`), Atlas, Casos de estudio. Tag de recuperación
`pre-dashboard-2026-11-15`. **Git:** push directo a `main` tras pruebas locales (sin PR, decisión del usuario).

## Commits
- `5cefce7` F0 — repo, CLAUDE.md, motor estadístico, CSV→pendiente explicada.
- `5a060d4` F2 — cliente EE, `AnalysisSpec`+hashes, IMERG, runner con caché, `/analyses`, golden v13.1.
- `e1f3c8c` F2 — geografías geoBoundaries v6 + fronteras oficiales Perú (IGN), ingesta y manifiesto.
- `3c32d82` F2 — adaptadores GLDAS/MERRA-2/NDVI/SST, SDK, notebook 01, coste/tokens/límites.
- `16c59ae` F1 — dirección «Cuaderno de campo», tokens, web Explorar con API real.
- `b3644af` F1 — tema, exportación, Fuentes/Métodos, Playwright, contraste.
- `977b629` F4 — Estudio comparativo, /analyses/compare, veredicto por q.
- (lista completa: `git log --oneline`)

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
- **F1 web** (`apps/web`, ADR-0006): dirección **A «Cuaderno de campo»** elegida por el usuario. Tokens únicos en
  `packages/design-tokens/tokens.json` → `tokens.css` (claro + oscuro derivado; ámbar/darkorange reservados a eventos).
  Next.js 16 + React 19 + TS 5.9 estricto, TanStack Query, Zustand (estado ↔ URL), ECharts (serie + tendencia + abanico IC),
  MapLibre sin teselas externas (worker servido desde `public/maplibre/`, copiado por `npm run assets`).
  **/explorar funcional:** búsqueda de territorio, lista de unidades hijas con pendientes, 9 variables del catálogo, periodo,
  serie anual/anomalía mensual, 3 métodos, veredicto en frase, mapa de pendientes (auto para productos mensuales; botón para
  el resto), calidad, run_id y procedencia. Verificado en navegador (1440/390 px, sin errores de consola, build de
  producción OK). Hallazgo vía web: NDVI Laredo +0,016/década, IC [+0,002; +0,030], p=0,04 → evidencia de aumento.
- **F1 (sesión 2, cont.):** selector de tema Sistema/Claro/Oscuro (sin parpadeo, recordado); exportación CSV/JSON/SVG/PNG@2×
  con run_id, fuente y especificación (`src/lib/export.ts`); páginas **Fuentes** (catálogo y fronteras desde la API) y
  **Métodos** (flujo, matriz de compatibilidad de la API, lectura del veredicto, glosario); Estudio/Atlas/Historias con
  página honesta «aún no disponible». **Playwright 8/8** (`npm --prefix apps/web run test:e2e`, Edge `msedge`, sin
  descargar navegadores): paridad web↔API, exportaciones, URL, error 401 honesto, tema, Fuentes/Métodos, 1024/768/390 px.
  **Contraste WCAG 2.1 AA 26/26** (`npm --prefix apps/web run check:contrast`).
- **Estudio + comparaciones** (ADR-0007): `POST /analyses/compare` (≤12 specs, BH-FDR, errores por ítem, cuota de familia
  previa), SDK `analyses.compare()`. Explorar: mapa por unidades en 1 llamada. **/estudio**: paneles = variables, líneas =
  territorios (≤4, color + patrón), tooltips sincronizados, arrastrar (dnd-kit puntero/teclado) + botones Añadir/Subir/Bajar/
  Quitar, estado en URL. **Veredicto usa q cuando hay familia** (caso real: NDVI Laredo p=0,04 → q=0,06 → no concluyente;
  Moche −0,033/década q<0,001 → disminución). Tests: backend 79, Playwright 12/12, contraste 34/34.
- **CI** (`.github/workflows/ci.yml`, runbook `docs/runbooks/ci.md`): jobs api (ruff+pytest, instala desde pyproject),
  web (contraste, tsc, build) y e2e (Playwright Chromium, **Earth Engine deshabilitado**, caché sembrada con fixtures NASA
  reales `scientific/fixtures/e2e`, 3 MB, generados con `scripts/e2e_fixtures.py`). Reproducido en local (venv limpio
  79/79, `npm ci` + build OK, e2e 12/12 sin EE). **CI #1 en verde en GitHub (3 min).** Flujo: rama + PR + CI + merge (ver CLAUDE.md).
- **Accesibilidad automática:** axe-core en Playwright (WCAG 2.1 A/AA, 4 páginas × 2 temas) en CI; corregidos mapa
  (`role=group`) y nombre accesible de «Añadir panel/En uso». PR #2.
- **Ciclo estacional:** `GET /analyses/{id}/seasonal` (matriz año×mes, climatología media/mediana/P25–P75, meses
  extremos; desde la extracción cacheada, sin EE) + panel en Explorar (heatmap + ciclo medio + tabla de extremos), SDK
  `analyses.seasonal()`. Dato real: mes más extremo de 2003–2024 en la provincia de Trujillo = **marzo 2017, 140 mm
  (+75 mm sobre su media)** (coincide con El Niño Costero 2017; no se afirma causa). Tests: backend 83, Playwright 21.
- **Caso Trujillo (F5, ADR-0008):** ingesta oficial reproducible `scripts/ingest_case_trujillo.py` → `data/case-trujillo/`
  (SINPAD/INDECI datos abiertos ODC-BY con SHA256; ICEN oficial IGP/ENFEN). Conciliación **16/16 con la v12** (2017–2025).
  Episodios ENFEN derivados (regla ICEN > +0,5 ≥ 3 meses, **umbral pendiente de verificar con el PDF de la NT 01-2024**;
  la web de ENFEN no responde desde aquí). API `/cases/...` (events, enfen), SDK `client.cases`, capa «Contexto local» en
  Explorar (bandas + marcadores + tabla; causalidad siempre «no verificada»). **El Niño Costero 2026 en curso** (ICEN +4,50
  sep-2026). Bug corregido: geometría ausente → 503 (antes 500).
- **Escena 4 «¿Relación o coincidencia?»:** `POST /cases/trujillo-el-nino/association` (permutación estratificada por mes
  calendario, desfases 0–3, BH-FDR, avisos de episodios) + panel en Explorar. Real IMERG 2003–2024: **mismo mes +22,2 mm
  (q<0,001); meses previos sin diferencia** → coincidencia con lluvia, sin anticipación. Fixtures CI regenerados (27 series).
  Tests: backend 96, Playwright 25 (también sin EE).
- **Historia guiada** `/historias/trujillo-el-nino` (config declarativa `apps/web/src/stories/trujillo-el-nino.json`):
  6 escenas con números de la API en tiempo real — (1) lluvia no concluyente, **NDVI aumento**, SST océano +0,44 °C/década
  no concluyente; (2) 11/11 distritos negativos, 0 con evidencia tras BH; 6 menores que un píxel; (3) 22 registros, 11
  durante El Niño, marzo 2017 = 140 mm; (4) asociación; (5) alerta (ver abajo); (6) límites y conciliación. Playwright 29 (axe incluye la historia), fixtures 29 series.
- **Escena 5 «¿Habría dado una alerta?»** (ADR-0009): IMERG V07 diario por distrito IGN y día local de Lima
  (`scripts/ingest_case_trujillo_daily.py` → `data/case-trujillo/imerg_daily_districts.csv.gz`, 36 157 filas, 48/48
  semihoras todos los días; idéntico a v12, r = 1,000). Motor `services/cases/backtest.py` + `GET /cases/{id}/backtest`
  (umbral 2017–2021, prueba 2022–2025, VP/FP/FN/VN, POD Wilson, azar esperado, 27 combinaciones). Regla principal
  P95/3 d/3 d: **0 de 3 anticipados, 755 falsas alarmas (17 por distrito-año)** — resultado nulo publicado, coincide
  con v13.1. Tests backend 106, Playwright historia + axe verdes.
- **Atlas `/atlas`** (ADR-0010): `POST /api/v1/atlas` = pendiente anual de todas las subunidades (≤ 250) con la misma
  spec que Explorar (caché compartida), BH-FDR por mapa, coste por suma de píxeles, 12 unidades nuevas = 1 extracción
  del cupo, extracciones individuales en paralelo (`ATLAS_PARALLEL_EXTRACTIONS`=6). UI: small multiples (lluvia,
  temperatura 2 m, humedad del suelo, NDVI) para Perú/departamentos, La Libertad/provincias, Trujillo/distritos.
  Real: lluvia 25 departamentos → 7 disminución, 18 sin evidencia. La reducción multibanda por lotes se descartó (más lenta).
- **Diferencia de pendientes** (ADR-0011): `POST /analyses/difference` + SDK + bloque en cada panel del Estudio.
  Δ = TS(A) − TS(B) con IC por bootstrap de bloques sobre pares de periodos (cobertura simulada 96–98,5 %). OLS no se
  ofrece (sus IC cubrieron 73–92 % con n = 22). Real: Huanchaco − Moche lluvia +4,9 mm/década, IC −24 a +14, r = 0,96.
- **Motor 0.2: autocorrelación corregida por defecto** (ADR-0012). Estudio de cobertura reproducible
  (`scripts/coverage_study.py` → `scientific/reports/cobertura_ic.md`) mostró que HAC, Theil–Sen analítico + MK y el
  bootstrap de residuos subcubrían (66–89 %, error tipo I hasta 33 %) con n = 22. Nuevos por defecto: Theil–Sen +
  IC con n efectivo AR(1) + MK AR(1) (94–96 % / 3–7 % con φ ≤ 0,3); bootstrap por pares. Atlas Perú cambia:
  lluvia 7 → 0, temperatura 9 → 0, humedad del suelo 18 → 2, NDVI 18 → 18. Pruebas de cobertura en CI.
- **Panel ambiental `/`** (ADR-0013): selector de territorio mundial (países geoBoundaries + subdivisiones; Perú IGN),
  periodo, variables (tarjeta por variable, carga progresiva, caché compartida), estimador + IC + prueba según
  `/catalog/capabilities`, nivel 90/95/99 % (veredicto con α = 1 − nivel), aviso si el método no corrige la
  autocorrelación, procedencia y cobertura temporal por tarjeta, «Ver detalle» → Explorar con la misma configuración.
  Atlas acepta cualquier territorio. E2E de paridad web = API (`e2e/panel.spec.ts`). Marca GaIA y navegación nueva.
- API: CORS (`ALLOWED_ORIGINS`), `GET /geographies/{id}/features` (FeatureCollection) y `path` en `/geographies/{id}`.
- Servidores: `.claude/launch.json` (api :8000, web :3000) o `npm --prefix apps/web run dev`.
- **73 tests verdes** (backend) (`cd apps/api && .venv/Scripts/python -m pytest -q`).

## Datos locales (no versionados)
`NinoDetect_TODOS_LOS_ZIPS_FINAL.zip` (raíz) → tablas en `data/_local_reference/`. Solo validación, nunca runtime.
`data/_downloads/` (descargas crudas) y `.cache/` (índices, geometrías, extracciones, runs) son regenerables.

## Siguiente
1. Prueba con lector de pantalla (NVDA).
2. **F4 restante:** brush temporal,
   Kendall estacional y dependencia de largo plazo (ENSO) más allá de AR(1) (ver ADR-0012, «Límites»).
3. ✅ Resuelto 2026-11-15: umbral «ligero» ampliado (ADR-0005): las 4 variables por defecto se calculan sin token
   (1–3 min la primera vez, luego en caché); el Panel muestra tiempo estimado/transcurrido y reintenta si EE está ocupado.
4. F6: despliegue, guía de uso, demo.
5. Base de datos (PostgreSQL/PostGIS) cuando se despliegue: usar skill local `sql-code-review` (del usuario).
6. Kendall estacional. Docker pospuesto (no necesario aún).

## Caso Trujillo (F5)
Lo trabajan los usuarios sobre la plataforma (decisión 2026-11-15). ENFEN: no se continúa. Quedan disponibles en la
plataforma: eventos SINPAD, episodios derivados del ICEN, asociación, evaluación de alertas e historia de 6 escenas.
