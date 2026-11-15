"use client";
// Serie temporal + tendencia + abanico de pendientes del IC (plan §8). No calcula estadística: usa la del run.
import { useEffect, useRef } from "react";
import { cssVar } from "@/lib/colors";
import { fmt, signed } from "@/lib/format";
import type { CaseEvent, EnfenEpisode, Run } from "@/lib/types";

const decYear = (iso: string) => {
  const d = new Date(iso);
  const y = d.getUTCFullYear();
  return y + (d.getTime() - Date.UTC(y, 0, 1)) / (365.2425 * 864e5);
};
const fromDec = (t: number) => {
  const y = Math.floor(t);
  return Date.UTC(y, 0, 1) + (t - y) * 365.2425 * 864e5;
};
const median = (a: number[]) => {
  const s = [...a].sort((x, y) => x - y), n = s.length;
  return n % 2 ? s[(n - 1) / 2]! : (s[n / 2 - 1]! + s[n / 2]!) / 2;
};

const EVENT_COLOR: Record<CaseEvent["display_class"], string> = {
  atribucion_verificada: "--event-verified", coincidencia_el_nino: "--event-coincidence", fuera_de_el_nino: "--event-outside",
};
const CONTEXT_LABEL: Record<string, string> = {
  coincidencia_el_nino_costero: "durante El Niño Costero (coincidencia temporal, no prueba causa)",
  coincidencia_la_nina_costera: "durante La Niña Costera", fuera_de_episodio: "fuera de episodios ENFEN",
};

export function TrendChart({ run, unit, anomaly, theme, onReady, events, episodes }:
  { run: Run; unit: string; anomaly: boolean; theme: string; onReady?: (c: import("echarts").ECharts | null) => void;
    events?: CaseEvent[]; episodes?: EnfenEpisode[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let chart: import("echarts").ECharts | undefined;
    let ro: ResizeObserver | undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");

    const render = async () => {
      const echarts = await import("echarts");
      if (disposed || !ref.current) return;
      chart?.dispose();
      chart = echarts.init(ref.current, undefined, { renderer: "svg" });
      onReady?.(chart);
      const st = run.statistics;
      const perYear = (v: number) => (st.estimate_unit.endsWith("/decade") ? v / 10 : v);
      const pts = run.series.map((p) => [Date.parse(p.time_start_utc), p.value] as [number, number | null]);
      const valid = run.series.filter((p) => p.value != null).map((p) => decYear(p.time_start_utc));
      const series: import("echarts").SeriesOption[] = [{
        name: anomaly ? "anomalía mensual" : "valor anual", type: "line", data: pts, connectNulls: false,
        symbol: anomaly ? "none" : "circle", symbolSize: 6, showSymbol: !anomaly,
        lineStyle: { width: anomaly ? 1 : 1.6, color: cssVar("--series") },
        itemStyle: { color: cssVar("--paper"), borderColor: cssVar("--series"), borderWidth: 1.4 },
        z: 3,
      }];
      if (st.estimate != null && st.intercept != null && valid.length) {
        const t0 = Math.min(...valid), t1 = Math.max(...valid), tm = median(valid);
        const y = (t: number) => st.intercept! + perYear(st.estimate!) * t;
        series.push({
          name: "tendencia", type: "line", data: [[fromDec(t0), y(t0)], [fromDec(t1), y(t1)]], symbol: "none",
          lineStyle: { width: 2.6, color: cssVar("--trend") }, z: 4, silent: true,
        });
        if (st.ci_lower != null && st.ci_upper != null) {
          const ym = y(tm);
          const lo = (t: number) => ym + perYear(st.ci_lower!) * (t - tm);
          const hi = (t: number) => ym + perYear(st.ci_upper!) * (t - tm);
          // Abanico: polígono del rango de pendientes del IC alrededor de la mediana (no es banda de predicción).
          series.push({
            name: "IC de la pendiente", type: "custom", silent: true, z: 1,
            renderItem: (_p, api) => {
              const P = (t: number, v: number) => api.coord([fromDec(t), v]);
              return { type: "polygon", shape: { points: [P(t0, lo(t0)), P(t1, lo(t1)), P(t1, hi(t1)), P(t0, hi(t0))] },
                       style: { fill: cssVar("--fan") } };
            },
            data: [[fromDec(t0), lo(t0)]],
          });
        }
      }
      const vals = run.series.map((p) => p.value).filter((v): v is number => v != null);
      // Capa de contexto local (caso Trujillo): bandas de episodios ENFEN y marcadores SINPAD sobre el gráfico.
      if (episodes?.length) {
        const monthEnd = (ym: string) => { const [y, m] = ym.split("-").map(Number); return Date.UTC(y!, m!, 1); };
        (series[0] as { markArea?: unknown }).markArea = {
          silent: true,
          data: episodes.map((e) => [
            { xAxis: Date.parse(`${e.start}-01T00:00:00Z`), name: e.id,
              itemStyle: { color: cssVar(e.kind === "el_nino_costero" ? "--episode-nino" : "--episode-nina") },
              label: { show: e.kind === "el_nino_costero", position: "insideTop", color: cssVar("--muted"), fontSize: 11,
                       formatter: e.ongoing ? `${e.id} (en curso)` : e.id } },
            { xAxis: monthEnd(e.end) },
          ]),
        };
      }
      if (events?.length && vals.length) {
        const top = Math.max(...vals), span = top - Math.min(...vals, 0) || 1;
        const seen: Record<string, number> = {};
        series.push({
          name: "eventos", type: "scatter", z: 6,
          data: events.filter((e) => e.date).map((e) => {
            const k = e.date!.slice(0, 7), n = (seen[k] = (seen[k] ?? 0) + 1);
            return { value: [Date.parse(e.date!), top + span * (0.06 + 0.07 * (n - 1))], event: e,
                     symbol: e.hazard === "huaico" ? "triangle" : "circle", symbolSize: 11,
                     itemStyle: { color: cssVar(EVENT_COLOR[e.display_class]), borderColor: cssVar("--event-stroke"), borderWidth: 1.2 } };
          }),
        });
      }
      chart.setOption({
        animation: false,
        aria: { enabled: true, label: { description: `Serie de ${run.series.length} puntos con tendencia ${st.estimator === "ols" ? "OLS" : "Theil–Sen"}` } },
        textStyle: { fontFamily: "var(--font-sans)", color: cssVar("--muted") },
        grid: { left: 56, right: 16, top: 26, bottom: 34 },
        xAxis: { type: "time", axisLine: { lineStyle: { color: cssVar("--rule") } }, axisLabel: { color: cssVar("--muted") },
                 splitLine: { show: false } },
        yAxis: { type: "value", name: anomaly ? `${unit} respecto al mismo mes` : `${unit} por año`, nameTextStyle: { align: "left", color: cssVar("--muted") },
                 min: anomaly ? undefined : Math.max(0, Math.floor(Math.min(...vals) * 0.85)),
                 axisLabel: { color: cssVar("--muted") }, splitLine: { lineStyle: { color: cssVar("--grid") } } },
        tooltip: {
          trigger: "axis", backgroundColor: cssVar("--ink"), borderWidth: 0, textStyle: { color: cssVar("--paper"), fontSize: 13 },
          formatter: (params: unknown) => {
            const all = params as { seriesName: string; value: [number, number | null]; data?: { event?: CaseEvent } }[];
            const evs = all.filter((x) => x.seriesName === "eventos" && x.data?.event).map((x) => x.data!.event!);
            const evHtml = evs.map((e) => `<br><b>${e.hazard === "huaico" ? "Huaico" : "Inundación"}</b> · ${e.district} · ${e.date}<br>` +
              `SINPAD ${e.sinpad_code} · ${CONTEXT_LABEL[e.enfen.context] ?? e.enfen.context}`).join("");
            const p = all.find((x) => !["tendencia", "IC de la pendiente", "eventos"].includes(x.seriesName));
            if (!p) return evHtml.replace(/^<br>/, "");
            const d = new Date(p.value[0]);
            const when = anomaly ? d.toLocaleDateString("es-PE", { month: "long", year: "numeric", timeZone: "UTC" }) : String(d.getUTCFullYear());
            return `<b>${when}</b><br>${p.value[1] == null ? "sin dato (no es cero)" : `${anomaly ? signed(p.value[1], 1) : fmt(p.value[1], 0)} ${unit}`}${evHtml}`;
          },
        },
        series,
      });
    };
    void render();
    ro = new ResizeObserver(() => chart?.resize());
    if (ref.current) ro.observe(ref.current);
    const onScheme = () => void render();
    mq.addEventListener("change", onScheme);
    return () => { disposed = true; ro?.disconnect(); mq.removeEventListener("change", onScheme); onReady?.(null); chart?.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, unit, anomaly, theme, events, episodes]);

  return <div ref={ref} className="chart" role="img" aria-label="Serie temporal con tendencia" />;
}
