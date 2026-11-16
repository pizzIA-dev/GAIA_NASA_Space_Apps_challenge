import type { Statistics } from "./types";
import { locale, tr } from "./i18n";

const nf = (d: number) => new Intl.NumberFormat(locale(), { minimumFractionDigits: d, maximumFractionDigits: d });
const noData = () => tr("sin dato", "no data");

export const fmt = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? noData() : nf(d).format(v));
export const signed = (v: number | null | undefined, d = 1) =>
  v == null ? noData() : (v > 0 ? "+" : v < 0 ? "−" : "") + nf(d).format(Math.abs(v));

/** Decimales razonables según magnitud (sin precisión artificial, plan §5.3). */
export const digitsFor = (v: number | null | undefined) => {
  const a = Math.abs(v ?? 0);
  return a >= 10 ? 1 : a >= 1 ? 2 : a >= 0.01 ? 3 : 4;
};

export const unitPerDecade = (u: string) =>
  u.replace(/^adimensional/, tr("índice", "index")).replace("/decade", tr(" por década", " per decade"))
    .replace("/year", tr(" por año", " per year"));

export type VerdictKind = "up" | "down" | "nc" | "none";

/** TrendVerdict (plan §5.4): nunca «confirmado al 95 %». */
export function verdictOf(st: Statistics): { kind: VerdictKind; label: string; phrase: string } {
  if (st.status === "insufficient_evidence" || st.estimate == null) {
    return { kind: "none", label: tr("sin inferencia", "no inference"),
      phrase: tr("no tiene datos suficientes para estimar una tendencia", "does not have enough data to estimate a trend") };
  }
  // Con varias pruebas (familia) manda el q-valor corregido BH-FDR; con una sola, el p-valor (plan §7.5).
  // α = 1 − nivel de confianza elegido: IC y prueba se leen con el mismo umbral.
  const alpha = 1 - (st.confidence_level ?? 0.95);
  const evidence = st.q_value ?? st.p_value;
  const sig = evidence != null && evidence < alpha && st.ci_lower != null && st.ci_upper != null &&
    (st.ci_lower > 0 || st.ci_upper < 0);
  if (!sig) return { kind: "nc", label: tr("no concluyente", "inconclusive"),
    phrase: tr("no muestra un cambio distinguible de cero", "shows no change distinguishable from zero") };
  return st.estimate > 0
    ? { kind: "up", label: tr("evidencia de aumento", "evidence of increase"),
        phrase: tr("muestra evidencia de aumento", "shows evidence of an increase") }
    : { kind: "down", label: tr("evidencia de disminución", "evidence of decrease"),
        phrase: tr("muestra evidencia de disminución", "shows evidence of a decrease") };
}

const TEST_LABELS: Record<string, [string, string]> = {
  mann_kendall: ["Mann–Kendall", "Mann–Kendall"], mann_kendall_ar1: ["Mann–Kendall (n efectivo)", "Mann–Kendall (effective n)"],
  ols_hac_t: ["t con errores HAC", "t with HAC errors"], ols_ar1_t: ["t (n efectivo)", "t (effective n)"],
  ols_t: ["t clásica", "classic t"], none: ["sin prueba", "no test"],
};
export const testLabel = (k: string) => { const l = TEST_LABELS[k]; return l ? tr(l[0], l[1]) : k; };

/** p/q legibles: nunca «0,00» (sugiere certeza); por debajo de 0,001 se escribe «< 0,001». */
export const fmtP = (v: number | null | undefined) =>
  v == null ? noData() : v < 0.001 ? `< ${fmt(0.001, 3)}` : v < 0.01 ? fmt(v, 3) : fmt(v, 2);
