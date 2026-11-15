# ADR-0012 — IC y pruebas corregidos por autocorrelación (n efectivo AR(1)) como valor por defecto

- **Fecha:** 2026-11-15 · **Estado:** aceptada · **Motor:** `trend_core/0.1.0` → `0.2.0`
- **Contexto:** al validar la diferencia de pendientes (ADR-0011) se vio que los IC de OLS subcubrían con series
  anuales cortas. Se midió el motor completo con `scripts/coverage_study.py` (simulación AR(1) gaussiana, tendencia
  conocida; informe en `scientific/reports/cobertura_ic.md`). Series de la plataforma: anual n = 22 (2003–2024) y
  anomalía mensual n = 264.
- **Hallazgos (versión 0.1, IC nominal 95 %, α = 0,05):**
  - Theil–Sen analítico + Mann–Kendall (el valor por defecto): correcto sin autocorrelación (95 % / 4 %), pero con
    φ = 0,3 → 89 % / 13 % y φ = 0,6 → 71 % / 30 %. Mensual φ = 0,5 → 76 % / 22 %.
  - OLS + HAC Newey–West: **82,7 % / 12,8 % incluso sin autocorrelación** con n = 22 (66 % / 33 % con φ = 0,6).
  - Bootstrap por bloques (remuestreo de residuos): 84 % sin autocorrelación, 66 % con φ = 0,6. Defecto del método.
  - Correcciones clásicas de MK probadas y descartadas con n = 22: Hamed–Rao (rechazo 11–24 %) y TFPW (12–33 %).
- **Decisión:**
  - Nuevos métodos: `theil_sen_ar1` (IC analítico de Theil–Sen ensanchado por √((1+ρ)/(1−ρ))), `mann_kendall_ar1`
    (varianza de S × (1+ρ)/(1−ρ)), `ar1_effective_n` + `ols_ar1_t` (OLS con varianza y g.l. de n_ef =
    n(1−ρ)/(1+ρ), Santer et al. 2000). ρ = autocorrelación de orden 1 de los residuos con corrección de sesgo
    (+(1+4ρ)/n), acotada a [0; 0,95].
  - **Valores por defecto** (API, web, SDK, Atlas, historia): Theil–Sen + `theil_sen_ar1` + `mann_kendall_ar1`;
    preset OLS = `ar1_effective_n` + `ols_ar1_t`; preset bootstrap = bloques sobre **pares** (t, y) + `mann_kendall_ar1`.
  - `moving_block_bootstrap` se corrige: remuestrea pares de periodos (vectorizado), no residuos.
  - Los métodos clásicos siguen disponibles para reproducir estudios (p. ej. la referencia v13.1) y avisan.
    HAC con n < 50 añade una advertencia; con ρ corregido > 0,5 se advierte que el rechazo puede rondar el 9 %.
- **Resultado (versión 0.2):** anual n = 22: 96 % / 3 % (φ = 0), 94 % / 7 % (φ = 0,3), 87–89 % / 9 % (φ = 0,6);
  mensual n = 264: 96 % / 4–6 %. Bootstrap por pares: 90–98 %. Pruebas de cobertura en CI
  (`tests/scientific/test_methods.py`).
- **Consecuencias con datos reales (Perú, 25 departamentos, 2003–2024):** lluvia IMERG 7 → 0 departamentos con
  evidencia; temperatura MERRA-2 9 → 0; humedad del suelo GLDAS 18 → 2; NDVI 18 aumento → 18 (sin cambio: señal
  robusta). Los hallazgos anteriores estaban en el límite (q ≈ 0,047) o dependían de la autocorrelación. Con 22 años
  la potencia es baja: «sin evidencia» no significa «sin cambio». Al cambiar `ALGORITHM_VERSION` cambian los
  `run_id`; la caché de extracciones se reutiliza (no hace falta Earth Engine).
- **Límites:** el modelo AR(1) no captura dependencia de más largo plazo (p. ej. ENSO multianual); con φ alto y
  n corto ningún método probado alcanza el 95 %.
