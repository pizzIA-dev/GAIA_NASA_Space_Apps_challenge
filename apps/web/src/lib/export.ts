"use client";
// Exportación reproducible (plan §8.2): todo archivo lleva run_id, fuente y especificación. Nada se recalcula aquí.
import { tr } from "./i18n";
import type { Run } from "./types";

function download(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.rel = "noopener";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const csvCell = (v: unknown) => {
  const s = v == null ? "" : String(v);
  return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function exportCsv(run: Run, unit: string) {
  const src = run.source_versions[0];
  const head = ["time_start_utc", "value", "unit", "missing", "run_id", "dataset_id", "ee_collection_id", "product_version", "geo_id", "boundary_set_id"];
  const rows = run.series.map((p) => [
    p.time_start_utc, p.value ?? "", unit, p.value == null ? "true" : "false", run.run_id, src?.dataset_id, src?.ee_collection_id,
    src?.version, run.geography.geo_id ?? "custom_roi", (run.geography as { boundary_set_id?: string }).boundary_set_id ?? "",
  ]);
  const body = [head, ...rows].map((r) => r.map(csvCell).join(",")).join("\n");
  download(`ets_${run.run_id}_serie.csv`, new Blob([`﻿${body}\n`], { type: "text/csv;charset=utf-8" }));
}

export function exportJson(run: Run) {
  const payload = {
    note: tr("Resultado de GaIA. Reproducible por API (GET /api/v1/analyses/{run_id}) o SDK Python con el run_id.",
      "GaIA result. Reproducible via the API (GET /api/v1/analyses/{run_id}) or the Python SDK with the run_id."),
    exported_at: new Date().toISOString(),
    run_id: run.run_id,
    analysis_spec_hash: run.analysis_spec_hash,
    request: run.request,
    statistics: run.statistics,
    source_versions: run.source_versions,
    geography: run.geography,
    series: run.series,
  };
  download(`ets_${run.run_id}.json`, new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
}

type EChart = import("echarts").ECharts;

/** Añade un título con fuente y run_id solo durante la exportación y lo retira después. */
function withCaption<T>(chart: EChart, caption: { title: string; subtitle: string }, fn: () => T): T {
  chart.setOption({ title: { show: true, text: caption.title, subtext: caption.subtitle, left: 8, top: 4,
    textStyle: { fontSize: 14 }, subtextStyle: { fontSize: 11 } }, grid: { top: 74 } });
  try { return fn(); } finally {
    chart.setOption({ title: { show: false }, grid: { top: 26 } });
  }
}

export function exportSvg(chart: EChart, run: Run, caption: { title: string; subtitle: string }) {
  const url = withCaption(chart, caption, () => chart.getDataURL({ type: "svg" }));
  const svg = decodeURIComponent(url.split(",")[1] ?? "");
  download(`ets_${run.run_id}.svg`, new Blob([svg], { type: "image/svg+xml" }));
}

export async function exportPng(chart: EChart, run: Run, caption: { title: string; subtitle: string }, background: string) {
  const url = withCaption(chart, caption, () => chart.getDataURL({ type: "svg" }));
  const img = new Image();
  await new Promise<void>((res, rej) => { img.onload = () => res(); img.onerror = rej; img.src = url; });
  const scale = 2, w = img.width || chart.getWidth(), h = img.height || chart.getHeight();
  const canvas = document.createElement("canvas");
  canvas.width = w * scale; canvas.height = h * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = background; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/png"));
  if (blob) download(`ets_${run.run_id}@2x.png`, blob);
}
