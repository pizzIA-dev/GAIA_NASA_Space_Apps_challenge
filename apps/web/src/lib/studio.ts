"use client";
// Estado del Estudio (plan §4.3, §5.3): paneles = variables; líneas = territorios (máx. 4). Sincronizado con la URL.
import { create } from "zustand";
import type { Method } from "./study";

export const MAX_PANELS = 4;
export const MAX_TERRITORIES = 4;

export interface StudioState {
  panels: string[]; // "dataset_id/variable_id"
  geos: string[];
  method: Method;
  start: number;
  end: number;
}

export const DEFAULT_STUDIO: StudioState = {
  panels: ["nasa-gpm-imerg-monthly-v07/precipitation_mm_month"],
  // Ejemplo del plan §4.3: «Comparar Huanchaco vs Moche».
  geos: ["pe-ign2020:130104", "pe-ign2020:130107"],
  method: "sen",
  start: 2003,
  end: 2024,
};

interface Store extends StudioState {
  set: (p: Partial<StudioState>) => void;
  addPanel: (key: string) => void;
  replacePanel: (index: number, key: string) => void;
  removePanel: (index: number) => void;
  movePanel: (index: number, delta: -1 | 1) => void;
  addGeo: (geoId: string) => void;
  removeGeo: (geoId: string) => void;
}

export const useStudio = create<Store>((set, get) => ({
  ...DEFAULT_STUDIO,
  set: (p) => set(p),
  addPanel: (key) => {
    const { panels } = get();
    if (panels.length >= MAX_PANELS || panels.includes(key)) return;
    set({ panels: [...panels, key] });
  },
  replacePanel: (i, key) => {
    const panels = [...get().panels];
    if (panels.includes(key)) return;
    panels[i] = key;
    set({ panels });
  },
  removePanel: (i) => set({ panels: get().panels.filter((_, j) => j !== i) }),
  movePanel: (i, d) => {
    const panels = [...get().panels], j = i + d;
    if (j < 0 || j >= panels.length) return;
    [panels[i], panels[j]] = [panels[j]!, panels[i]!];
    set({ panels });
  },
  addGeo: (g) => {
    const { geos } = get();
    if (geos.length >= MAX_TERRITORIES || geos.includes(g)) return;
    set({ geos: [...geos, g] });
  },
  removeGeo: (g) => set({ geos: get().geos.filter((x) => x !== g) }),
}));

export function studioFromUrl(search: string): Partial<StudioState> {
  const q = new URLSearchParams(search), out: Partial<StudioState> = {};
  const panels = q.get("panels"), geos = q.get("geos"), method = q.get("method");
  if (panels) out.panels = panels.split(",").filter(Boolean).slice(0, MAX_PANELS);
  if (geos) out.geos = geos.split(",").filter(Boolean).slice(0, MAX_TERRITORIES);
  if (method === "sen" || method === "ols" || method === "sen_boot") out.method = method;
  if (q.get("start")) out.start = Number(q.get("start"));
  if (q.get("end")) out.end = Number(q.get("end"));
  return out;
}

export function studioToUrl(s: StudioState): string {
  const q = new URLSearchParams();
  if (s.panels.join(",") !== DEFAULT_STUDIO.panels.join(",")) q.set("panels", s.panels.join(","));
  if (s.geos.join(",") !== DEFAULT_STUDIO.geos.join(",")) q.set("geos", s.geos.join(","));
  if (s.method !== DEFAULT_STUDIO.method) q.set("method", s.method);
  if (s.start !== DEFAULT_STUDIO.start) q.set("start", String(s.start));
  if (s.end !== DEFAULT_STUDIO.end) q.set("end", String(s.end));
  const str = q.toString();
  return str ? `?${str}` : "";
}

export const splitKey = (key: string) => {
  const [datasetId = "", variableId = ""] = key.split("/");
  return { datasetId, variableId };
};

/** Patrón de línea por territorio: la comparación no depende solo del color. */
export const LINE_TYPES = ["solid", "dashed", "dotted", [10, 4, 2, 4]] as const;
