"use client";
// Varias series (territorios) de UNA variable: mismo eje y misma unidad (sin doble eje engañoso, plan §5.3).
// Los paneles comparten grupo ECharts: el cursor y la fecha se sincronizan entre variables.
import { useEffect, useRef } from "react";
import { cssVar } from "@/lib/colors";
import { fmt } from "@/lib/format";
import { tr, useLang } from "@/lib/i18n";
import { LINE_TYPES } from "@/lib/studio";
import type { CompareItem } from "@/lib/types";

const GROUP = "estudio";
const decYear = (iso: string) => {
  const d = new Date(iso), y = d.getUTCFullYear();
  return y + (d.getTime() - Date.UTC(y, 0, 1)) / (365.2425 * 864e5);
};
const fromDec = (t: number) => { const y = Math.floor(t); return Date.UTC(y, 0, 1) + (t - y) * 365.2425 * 864e5; };

export function CompareChart({ items, names, unit, theme, label }:
  { items: CompareItem[]; names: Record<string, string>; unit: string; theme: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const lang = useLang();
  useEffect(() => {
    let disposed = false, chart: import("echarts").ECharts | undefined;
    (async () => {
      const echarts = await import("echarts");
      if (disposed || !ref.current) return;
      chart = echarts.init(ref.current, undefined, { renderer: "svg" });
      chart.group = GROUP;
      echarts.connect(GROUP);
      const series: import("echarts").SeriesOption[] = [];
      const vals: number[] = [];
      items.forEach((it, i) => {
        if (it.status !== "succeeded" || !it.series || !it.statistics) return;
        const color = cssVar(`--cat-${(i % 4) + 1}`), type = LINE_TYPES[i % 4] as "solid";
        const name = names[it.geo_id] ?? it.geo_id;
        it.series.forEach((p) => { if (p.value != null) vals.push(p.value); });
        series.push({ name, type: "line", data: it.series.map((p) => [Date.parse(p.time_start_utc), p.value]),
          connectNulls: false, symbol: "circle", symbolSize: 5, lineStyle: { color, width: 1.6, type }, itemStyle: { color } });
        const st = it.statistics;
        if (st.estimate != null && st.intercept != null) {
          const valid = it.series.filter((p) => p.value != null).map((p) => decYear(p.time_start_utc));
          const t0 = Math.min(...valid), t1 = Math.max(...valid);
          const per = st.estimate_unit.endsWith("/decade") ? st.estimate / 10 : st.estimate;
          series.push({ name: `${name} (trend)`, type: "line", silent: true, symbol: "none",
            data: [[fromDec(t0), st.intercept + per * t0], [fromDec(t1), st.intercept + per * t1]],
            lineStyle: { color, width: 2.4, type, opacity: 0.85 } });
        }
      });
      chart.setOption({
        animation: false,
        aria: { enabled: true, label: { description: label } },
        textStyle: { fontFamily: "var(--font-sans)", color: cssVar("--muted") },
        grid: { left: 56, right: 16, top: 28, bottom: 30 },
        legend: { show: false },
        xAxis: { type: "time", axisLabel: { color: cssVar("--muted") }, axisLine: { lineStyle: { color: cssVar("--rule") } } },
        yAxis: { type: "value", name: tr(`${unit} (valor anual)`, `${unit} (annual value)`), nameTextStyle: { align: "left", color: cssVar("--muted") },
          min: vals.length && Math.min(...vals) >= 0 ? Math.floor(Math.min(...vals) * 0.85) : undefined,
          axisLabel: { color: cssVar("--muted") }, splitLine: { lineStyle: { color: cssVar("--grid") } } },
        tooltip: {
          trigger: "axis", backgroundColor: cssVar("--ink"), borderWidth: 0, textStyle: { color: cssVar("--paper"), fontSize: 13 },
          formatter: (params: unknown) => {
            const ps = (params as { seriesName: string; value: [number, number | null]; color: string }[])
              .filter((p) => !p.seriesName.endsWith("(trend)"));
            if (!ps.length) return "";
            const year = new Date(ps[0]!.value[0]).getUTCFullYear();
            return `<b>${year}</b><br>` + ps.map((p) =>
              `${p.seriesName}: ${p.value[1] == null ? tr("sin dato", "no data") : `${fmt(p.value[1], Math.abs(p.value[1]) < 10 ? 2 : 0)} ${unit}`}`).join("<br>");
          },
        },
        series,
      });
    })();
    const ro = new ResizeObserver(() => chart?.resize());
    if (ref.current) ro.observe(ref.current);
    return () => { disposed = true; ro.disconnect(); chart?.dispose(); };
  }, [items, names, unit, theme, label, lang]);
  return <div ref={ref} className="chart compare" role="img" aria-label={label} />;
}
