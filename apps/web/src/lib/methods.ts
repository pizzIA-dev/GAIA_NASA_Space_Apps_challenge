// Nombres y compatibilidad de métodos (plan §7). La matriz de compatibilidad la publica la API: /catalog/capabilities.
export interface Capabilities {
  estimators: Record<string, { interval_methods: string[]; significance_tests: string[] }>;
  confidence_levels: number[];
}

export const METHOD_NAMES: Record<string, string> = {
  ols: "Regresión lineal (OLS)", theil_sen: "Pendiente de Theil–Sen",
  ols_classic: "IC clásico de OLS", hac_newey_west: "IC robusto HAC (Newey–West)", ar1_effective_n: "IC de OLS con n efectivo AR(1)",
  theil_sen_analytic: "IC analítico de Theil–Sen", theil_sen_ar1: "IC de Theil–Sen con n efectivo AR(1)",
  moving_block_bootstrap: "Bootstrap por bloques móviles (pares)", ols_t: "Prueba t clásica", ols_hac_t: "Prueba t con errores HAC",
  ols_ar1_t: "Prueba t con n efectivo AR(1)", mann_kendall: "Mann–Kendall", mann_kendall_ar1: "Mann–Kendall con n efectivo AR(1)",
  none: "Sin prueba",
};

/** Métodos que NO corrigen la autocorrelación: medido, son optimistas con series cortas (ADR-0012). */
export const UNCORRECTED = new Set(["ols_classic", "hac_newey_west", "theil_sen_analytic", "ols_t", "ols_hac_t", "mann_kendall"]);

/** Recomendado por estimador (por defecto en toda la plataforma). */
export const RECOMMENDED: Record<string, { interval_method: string; significance_test: string }> = {
  theil_sen: { interval_method: "theil_sen_ar1", significance_test: "mann_kendall_ar1" },
  ols: { interval_method: "ar1_effective_n", significance_test: "ols_ar1_t" },
};
