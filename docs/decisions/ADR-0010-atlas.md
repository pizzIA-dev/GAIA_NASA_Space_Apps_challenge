# ADR-0010 — Atlas: un mapa de tendencias por variable para todas las subunidades

- **Fecha:** 2026-11-15 · **Estado:** aceptada
- **Contexto:** plan §4.1 (`/atlas`: mapas de tendencias por variable), §8 (mapa divergente centrado en 0, no
  significativos marcados y no borrados), MAP-01 (leyenda científica con escala y N). Explorar ya pintaba un mapa, pero
  limitado a ≤ 12 unidades (`/analyses/compare`) y a una variable a la vez.
- **Decisión:**
  - `POST /api/v1/atlas` {parent_geo_id, dataset_id, variable_id, start_year, end_year, method}: pendiente anual de
    TODAS las subunidades (máx. 250), con la **misma especificación que Explorar** → mismo `run_id` y caché compartida
    (pulsar una unidad del atlas abre Explorar sin recalcular). BH-FDR sobre las unidades de cada mapa (familia
    `atlas:<parent>`); cada unidad falla por separado (sin píxeles válidos, error de EE) y se informa, no se oculta.
  - Coste: límites aplicados a la **suma** de píxel-imágenes de las unidades nuevas; anónimo solo «ligero» (lluvia
    IMERG sobre el Perú lo es; MERRA-2/GLDAS/NDVI nacional requieren token, igual que en Explorar). Cupo: cada 12
    unidades nuevas cuentan como una extracción (equivale a una familia de `/compare`).
  - Ejecución: un turno del semáforo global de EE y, dentro, extracciones individuales en paralelo
    (`ATLAS_PARALLEL_EXTRACTIONS`, 6 por defecto).
- **Alternativa descartada (medida):** reducción por lotes con una imagen multibanda (un mes por banda) y un solo
  `reduceRegions` para todas las geometrías. Da resultados idénticos (diferencia relativa ≤ 4e-15), pero fue **más
  lenta** con polígonos oficiales IGN (Puno: 21 s individual vs 41 s en lote) y obligó a trocear peticiones por el
  límite de 10 MB de EE (12 MB de geometrías departamentales). EE paraleliza mejor un `reduceRegion` por imagen.
- **UI `/atlas`:** small multiples (lluvia IMERG, temperatura MERRA-2, humedad del suelo GLDAS, NDVI MODIS) para
  Perú/departamentos, La Libertad/provincias y Trujillo/distritos. Cada mapa: escala divergente propia centrada en 0
  con valores ±máx y unidad por década, rayado = sin evidencia (q ≥ 0,05 o IC con 0), borde discontinuo = unidad menor
  que un píxel, recuento aumento/disminución/sin evidencia/sin datos y tabla accesible con IC y q.
- **Consecuencias:** las escalas no son comparables entre variables (se dice en la leyenda). El color divergente es
  marrón↔azul verdoso para toda variable; en temperatura significa solo «menos/más».
- **Validación real:** lluvia IMERG 2003–2024, 25 departamentos del Perú: 25/25 calculados, 7 con evidencia de
  disminución (q < 0,05), 18 sin evidencia, ninguno con aumento.
