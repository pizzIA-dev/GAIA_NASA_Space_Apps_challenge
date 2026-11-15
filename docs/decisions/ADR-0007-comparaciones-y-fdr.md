# ADR-0007 — Comparaciones (`/analyses/compare`), BH-FDR y veredicto por q-valor

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** plan §12A.1 («comparar territorios»), §7.5 («BH por defecto al comparar múltiples distritos/variables»;
  «mostrar q si hay múltiples pruebas») y §4.3/§5.3 (Estudio: comparar territorios, ejes sincronizados, sin doble eje).
- **Decisión:**
  - `POST /api/v1/analyses/compare {specs[1..12], multiple_testing: BH_FDR|none, family_id}`: cada spec pasa por la misma
    política que `/analyses` (coste, token, 413). **Errores por ítem** (p. ej. `insufficient_coverage`, `token_required`)
    sin invalidar la familia. **La cuota se verifica para toda la familia antes de consumir** (no quedan comparaciones a
    medias). q-valores BH sobre los ítems con p-valor; `multiple_tests_family` = `family_id`.
  - **No** se estima la diferencia entre pendientes (requiere bootstrap conjunto): la respuesta lo advierte; un solapamiento
    de IC no equivale a una prueba de diferencia.
  - **Veredicto:** si hay q-valor (familia), «evidencia» exige q < 0,05 y IC sin 0; con un solo análisis se usa p.
    Hallazgo real que motivó la regla: NDVI 2003–2024 de Laredo, p = 0,04 sola, **q = 0,06** frente a Huanchaco y Moche
    → «no concluyente» en la comparación. Moche: −0,033/década, q < 0,001 → evidencia de disminución.
  - p/q < 0,001 se muestran como «< 0,001» (nunca «0,00»).
  - Explorar usa `compare` para el mapa por unidades (1 llamada en vez de N; mismo criterio q).
  - Estudio: paneles = variables (una unidad por eje, sin doble eje), líneas = territorios (≤ 4) con color categórico
    (tokens `cat-1..4`, contraste ≥ 3:1) **y** patrón de línea; tooltips sincronizados entre paneles (grupo ECharts).
    Arrastrar con dnd-kit (puntero y teclado, anuncios en español) + alternativa por botones.
