# ADR-0004 — Adaptadores de composición mensual (GLDAS, MERRA-2, MODIS NDVI, SST MODIS-Aqua)

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** el plan (§14.4) pide `GLDASMonthly`, `MERRA2Monthly`, `MODISNDVI`, `MODISAquaSST` con el mismo contrato
  que IMERG. Son colecciones sub-mensuales (3 h, 1 h, 16 d, 1 d).
- **Decisión:** clase `MonthlyCompositeAdapter` (`app/services/earth_engine/adapters.py`):
  1. Por cada mes, en EE: `filterDate(mes)` → receta de banda (factor, offset, máscara QA) → `mean()` por píxel.
  2. Reducción espacial `mean` (ponderada por fracción de píxel) + `count` a una escala de extracción fija.
  3. Bloques de N años por llamada `getInfo` (GLDAS/MERRA 4 años; NDVI/SST 6) para limitar coste y reintentos.
  4. Por fila: `source_image_count`, `valid_pixel_count`, `extraction_scale_m`, flags `no_image`, `no_valid_pixels`,
     `partial_month_product_start`. Faltante → `null`, nunca 0.
- **Recetas (alineadas con la metodología del estudio previo, verificada leyendo su notebook 02):**

| Dataset | Colección EE | Variables | Receta | Escala extracción |
|---|---|---|---|---|
| GLDAS Noah 2.1 | `NASA/GLDAS/V021/NOAH/G025/T3H` | humedad 0–10 cm; T aire | kg/m²; K−273,15 | 27 830 m |
| MERRA-2 | `NASA/GSFC/MERRA/slv/2` | T2M, TQV, U10M, V10M | K−273,15; kg/m²; m/s | 69 500 m |
| MODIS NDVI | `MODIS/061/MOD13Q1` | NDVI | ×0,0001, `SummaryQA ≤ 1` | 500 m (nativa 250 m) |
| SST | `NASA/OCEANDATA/MODIS-Aqua/L3SMI` (no MUR) | sst | °C | 4616 m |

- **Agregación anual:** solo `mean` para estas variables (`total` → 409).
- **SST:** debe usarse sobre una región oceánica; sobre tierra no hay píxeles → `insufficient_coverage`. El polígono
  oceánico del caso Trujillo se documentará en F5 como ROI del caso, no se impone en el adaptador.
- **Validación:** `scripts/validate_adapters_vs_reference.py` (resultados en la bitácora del equipo).

## Resultado de la validación (2026-11-14)
Misma geometría que el estudio previo, 2003–2024 (264 meses):

| Variable | Laredo 130106 | Trujillo 130101 |
|---|---|---|
| GLDAS humedad 0–10 cm | \|d\| máx 0,158 kg/m², corr 0,99997 | sin píxeles (igual que v12) |
| GLDAS T aire | \|d\| máx 0,074 °C, corr 0,99993 | sin píxeles (igual que v12) |
| MERRA-2 T2M / TQV / U10M / V10M | idénticos (diff 0) | sin píxeles (igual que v12) |
| MODIS NDVI | \|d\| máx 0,0003 | \|d\| máx 0,015, corr 0,9992 |
| SST (océano frente a Trujillo) | — | \|d\| máx 0,0016 °C; 262 meses vs 260 en v12 |

Las pequeñas diferencias de GLDAS/NDVI se atribuyen a `reduceRegion` (tileScale 4) frente a `reduceRegions` (tileScale 16)
del estudio previo. Coste observado: MERRA-2 ~1,5–3,5 min por variable y territorio; GLDAS ~1 min; NDVI/SST ~10 s.

## Nota: territorios menores que una celda (observado en sesión 2)
Earth Engine pondera los píxeles por la fracción que cae dentro del polígono, así que con celdas de 28–70 km un distrito
diminuto puede recibir el valor de una celda o ninguno según pequeñas diferencias de forma (p. ej. Víctor Larco, 12 km²:
sin píxel con el polígono del estudio previo, con píxel con la frontera IGN). En ambos casos la API es honesta: sin
píxel → 422 explicativo; con píxel → valor + aviso "el valor representa una celda que excede el territorio".
