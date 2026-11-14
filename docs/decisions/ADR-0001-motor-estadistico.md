# ADR-0001 — Motor estadístico puro en Python, con matriz de compatibilidad

- **Fecha:** 2026-11-14 · **Estado:** aceptada
- **Contexto:** el plan (§7, §12A) exige que web, API y SDK den resultados idénticos y que el IC corresponda al estimador.
- **Decisión:** `apps/api/app/services/statistics/trend_core.py` contiene funciones puras (sin I/O ni GEE).
  Una tabla `COMPATIBILITY` define qué IC/pruebas acepta cada estimador; combinaciones inválidas lanzan
  `IncompatibleMethodError` (→ HTTP 409). `/api/v1/catalog/capabilities` expone esa tabla para que UI/SDK no dupliquen reglas.
- **Métodos v0.1:** OLS (IC clásico | HAC Newey–West | bootstrap por bloques; prueba t | t-HAC),
  Theil–Sen (IC analítico SciPy | bootstrap por bloques; Mann–Kendall con corrección de empates). BH-FDR.
- **Pendiente:** Mann–Kendall corregido por autocorrelación (Hamed–Rao o Yue–Wang), Kendall estacional, LOWESS,
  anomalías mensuales/climatología, extremos P95.
- **Consecuencias:** N < mínimo o serie constante → `insufficient_evidence` con `null`; cobertura < umbral → `exploratory`.
