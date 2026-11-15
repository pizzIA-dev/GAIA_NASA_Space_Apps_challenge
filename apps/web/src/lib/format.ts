import type { Statistics } from "./types";

const nf = (d: number) => new Intl.NumberFormat("es-PE", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmt = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? "sin dato" : nf(d).format(v));
export const signed = (v: number | null | undefined, d = 1) =>
  v == null ? "sin dato" : (v > 0 ? "+" : v < 0 ? "−" : "") + nf(d).format(Math.abs(v));

/** Decimales razonables según magnitud (sin precisión artificial, plan §5.3). */
export const digitsFor = (v: number | null | undefined) => {
  const a = Math.abs(v ?? 0);
  return a >= 10 ? 1 : a >= 1 ? 2 : a >= 0.01 ? 3 : 4;
};

export const unitPerDecade = (u: string) => u.replace("/decade", " por década").replace("/year", " por año");

export type VerdictKind = "up" | "down" | "nc" | "none";

/** TrendVerdict (plan §5.4): nunca «confirmado al 95 %». */
export function verdictOf(st: Statistics): { kind: VerdictKind; label: string; phrase: string } {
  if (st.status === "insufficient_evidence" || st.estimate == null) {
    return { kind: "none", label: "sin inferencia", phrase: "no tiene datos suficientes para estimar una tendencia" };
  }
  const sig = st.p_value != null && st.p_value < 0.05 && st.ci_lower != null && st.ci_upper != null &&
    (st.ci_lower > 0 || st.ci_upper < 0);
  if (!sig) return { kind: "nc", label: "no concluyente", phrase: "no muestra un cambio distinguible de cero" };
  return st.estimate > 0
    ? { kind: "up", label: "evidencia de aumento", phrase: "muestra evidencia de aumento" }
    : { kind: "down", label: "evidencia de disminución", phrase: "muestra evidencia de disminución" };
}

export const TEST_LABEL: Record<string, string> = {
  mann_kendall: "Mann–Kendall", ols_hac_t: "t con errores HAC", ols_t: "t clásica", none: "sin prueba",
};
