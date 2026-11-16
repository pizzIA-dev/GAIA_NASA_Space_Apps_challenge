// Nombres y compatibilidad de métodos (plan §7). La matriz de compatibilidad la publica la API: /catalog/capabilities.
import { tr } from "./i18n";

export interface Capabilities {
  estimators: Record<string, { interval_methods: string[]; significance_tests: string[] }>;
  confidence_levels: number[];
}

const NAMES: Record<string, [string, string]> = {
  ols: ["Regresión lineal (OLS)", "Linear regression (OLS)"], theil_sen: ["Pendiente de Theil–Sen", "Theil–Sen slope"],
  ols_classic: ["IC clásico de OLS", "Classic OLS CI"], hac_newey_west: ["IC robusto HAC (Newey–West)", "Robust HAC CI (Newey–West)"],
  ar1_effective_n: ["IC de OLS con n efectivo AR(1)", "OLS CI with AR(1) effective n"],
  theil_sen_analytic: ["IC analítico de Theil–Sen", "Analytic Theil–Sen CI"],
  theil_sen_ar1: ["IC de Theil–Sen con n efectivo AR(1)", "Theil–Sen CI with AR(1) effective n"],
  moving_block_bootstrap: ["Bootstrap por bloques móviles (pares)", "Moving-block bootstrap (pairs)"],
  ols_t: ["Prueba t clásica", "Classic t-test"], ols_hac_t: ["Prueba t con errores HAC", "t-test with HAC errors"],
  ols_ar1_t: ["Prueba t con n efectivo AR(1)", "t-test with AR(1) effective n"], mann_kendall: ["Mann–Kendall", "Mann–Kendall"],
  mann_kendall_ar1: ["Mann–Kendall con n efectivo AR(1)", "Mann–Kendall with AR(1) effective n"],
  none: ["Sin prueba", "No test"],
};
export const methodName = (k: string) => { const n = NAMES[k]; return n ? tr(n[0], n[1]) : k; };

/** Métodos que NO corrigen la autocorrelación: medido, son optimistas con series cortas (ADR-0012). */
export const UNCORRECTED = new Set(["ols_classic", "hac_newey_west", "theil_sen_analytic", "ols_t", "ols_hac_t", "mann_kendall"]);

/** Recomendado por estimador (por defecto en toda la plataforma). */
export const RECOMMENDED: Record<string, { interval_method: string; significance_test: string }> = {
  theil_sen: { interval_method: "theil_sen_ar1", significance_test: "mann_kendall_ar1" },
  ols: { interval_method: "ar1_effective_n", significance_test: "ols_ar1_t" },
};

/** Nombres cortos para los selectores del panel (conservan el nombre estadístico; caben en la columna). */
const SHORT: Record<string, [string, string]> = {
  ols: ["OLS (regresión lineal)", "OLS (linear regression)"], theil_sen: ["Theil–Sen", "Theil–Sen"],
  theil_sen_ar1: ["Theil–Sen, n efectivo", "Theil–Sen, effective n"], theil_sen_analytic: ["Theil–Sen analítico", "Theil–Sen analytic"],
  moving_block_bootstrap: ["Bootstrap por bloques", "Block bootstrap"],
  ar1_effective_n: ["OLS, n efectivo", "OLS, effective n"], hac_newey_west: ["HAC (Newey–West)", "HAC (Newey–West)"],
  ols_classic: ["OLS clásico", "Classic OLS"], mann_kendall_ar1: ["Mann–Kendall, n efectivo", "Mann–Kendall, effective n"],
  mann_kendall: ["Mann–Kendall", "Mann–Kendall"], ols_ar1_t: ["t, n efectivo", "t, effective n"],
  ols_hac_t: ["t con HAC", "t with HAC"], ols_t: ["t clásica", "classic t"], none: ["Sin prueba", "No test"],
};
export const methodShort = (k: string) => { const n = SHORT[k]; return n ? tr(n[0], n[1]) : k; };
