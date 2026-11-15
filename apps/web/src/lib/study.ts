"use client";
// Estado del estudio (plan §14.3: «estado de estudio en JSON y restauración desde URL»). Zustand + query string.
import { create } from "zustand";

export type View = "annual" | "anomaly";
export type Method = "sen" | "ols" | "sen_boot";

export interface StudyState {
  focus: string; // territorio cuyo mapa se muestra (p. ej. provincia)
  selected: string; // territorio analizado (el foco o una unidad hija)
  datasetId: string;
  variableId: string;
  view: View;
  method: Method;
  start: number;
  end: number; // año final inclusivo
  context: boolean; // capa de contexto local (eventos SINPAD + episodios ENFEN) cuando el territorio la tiene
}

export const DEFAULT_STUDY: StudyState = {
  focus: "pe-ign2020:1301",
  selected: "pe-ign2020:1301",
  datasetId: "nasa-gpm-imerg-monthly-v07",
  variableId: "precipitation_mm_month",
  view: "annual",
  method: "sen",
  start: 2003,
  end: 2024,
  context: false,
};

interface Store extends StudyState {
  set: (patch: Partial<StudyState>) => void;
}

export const useStudy = create<Store>((set) => ({ ...DEFAULT_STUDY, set: (patch) => set(patch) }));

const KEYS: (keyof StudyState)[] = ["focus", "selected", "datasetId", "variableId", "view", "method", "start", "end", "context"];

export function readStudyFromUrl(search: string): Partial<StudyState> {
  const q = new URLSearchParams(search);
  const out: Record<string, string | number | boolean> = {};
  for (const k of KEYS) {
    const v = q.get(k);
    if (v == null) continue;
    out[k] = k === "start" || k === "end" ? Number(v) : k === "context" ? v === "true" : v;
  }
  return out as Partial<StudyState>;
}

export function studyToUrl(s: StudyState): string {
  const q = new URLSearchParams();
  for (const k of KEYS) if (s[k] !== DEFAULT_STUDY[k]) q.set(k, String(s[k]));
  const str = q.toString();
  return str ? `?${str}` : "";
}

const METHODS: Record<Method, object> = {
  // Métodos corregidos por autocorrelación (n efectivo AR(1)); ver ADR-0012 y scientific/reports/cobertura_ic.md.
  sen: { estimator: "theil_sen", interval_method: "theil_sen_ar1", significance_test: "mann_kendall_ar1" },
  ols: { estimator: "ols", interval_method: "ar1_effective_n", significance_test: "ols_ar1_t" },
  sen_boot: { estimator: "theil_sen", interval_method: "moving_block_bootstrap", significance_test: "mann_kendall_ar1", seed: 2026 },
};

export const METHOD_LABEL: Record<Method, string> = {
  sen: "Theil–Sen", ols: "OLS (n efectivo)", sen_boot: "Theil–Sen + bootstrap",
};

/** Especificación canónica (§11.2) que la web envía a la API: la misma que usaría el SDK. */
export function buildSpec(s: StudyState, geoId: string = s.selected, view: View = s.view): object {
  const anomaly = view === "anomaly";
  const stats = { ...METHODS[s.method] } as Record<string, unknown>;
  if (s.method === "sen_boot") stats.block_length = anomaly ? 12 : 3;
  return {
    data: { dataset_id: s.datasetId, variable_id: s.variableId },
    geography: { geo_ids: [geoId] },
    time: { start: `${s.start}-01-01`, end_exclusive: `${s.end + 1}-01-01`, granularity: anomaly ? "month" : "year" },
    ...(anomaly ? { transforms: { seasonality: "monthly_anomaly" } } : {}),
    statistics: stats,
  };
}
