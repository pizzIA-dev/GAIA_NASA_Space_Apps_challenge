"use client";
// Ciclo estacional (plan §8): heatmap año × mes y climatología con rango intercuartílico. Todo viene de la API.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, ApiError } from "@/lib/api";
import { cssVar } from "@/lib/colors";
import { fmt, signed } from "@/lib/format";
import { apiText, useLang, useT } from "@/lib/i18n";
import type { Seasonal } from "@/lib/types";

export function SeasonalPanel({ runId, theme, place }: { runId: string; theme: string; place: string }) {
  const t = useT();
  const lang = useLang();
  const q = useQuery<Seasonal, ApiError>({ queryKey: ["seasonal", runId], queryFn: () => api.seasonal(runId) });
  const heatRef = useRef<HTMLDivElement>(null);
  const climRef = useRef<HTMLDivElement>(null);
  const s = q.data;

  useEffect(() => {
    if (!s) return;
    let disposed = false;
    const charts: import("echarts").ECharts[] = [];
    (async () => {
      const echarts = await import("echarts");
      if (disposed || !heatRef.current || !climRef.current) return;
      const muted = cssVar("--muted"), grid = cssVar("--grid"), ink = cssVar("--ink"), paper = cssVar("--paper");
      const tooltip = { backgroundColor: ink, borderWidth: 0, textStyle: { color: paper, fontSize: 13 } };
      const M = s.months.map(apiText);
      const d = s.climatology.some((c) => (c.max ?? 0) < 10) ? 2 : 0;

      const heat = echarts.init(heatRef.current, undefined, { renderer: "svg" });
      charts.push(heat);
      const cells = s.years.flatMap((y, yi) => s.matrix[yi]!.map((v, mi) => [mi, yi, v ?? "-"]));
      const vals = s.matrix.flat().filter((v): v is number => v != null);
      heat.setOption({
        animation: false,
        aria: { enabled: true, label: { description: t(`Valores mensuales por año en ${place}`, `Monthly values by year in ${place}`) } },
        grid: { left: 44, right: 12, top: 8, bottom: 56 },
        xAxis: { type: "category", data: M, axisLabel: { color: muted }, axisTick: { show: false }, axisLine: { show: false } },
        yAxis: { type: "category", data: s.years.map(String), inverse: true, axisLabel: { color: muted, interval: 2 },
                 axisTick: { show: false }, axisLine: { show: false } },
        visualMap: { min: Math.min(...vals), max: Math.max(...vals), calculable: false, orient: "horizontal", left: "center", bottom: 4,
                     itemHeight: 140, itemWidth: 10, text: [`${fmt(Math.max(...vals), d)} ${s.unit}`, fmt(Math.min(...vals), d)],
                     textStyle: { color: muted }, inRange: { color: [cssVar("--seq-0"), cssVar("--seq-1")] } },
        tooltip: { ...tooltip, formatter: (p: { value: [number, number, number | "-"] }) =>
          `${M[p.value[0]]} ${s.years[p.value[1]]}: ${p.value[2] === "-" ? t("sin dato (no es cero)", "no data (not zero)") : `${fmt(p.value[2], d)} ${s.unit}`}` },
        series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: paper, borderWidth: 1 },
                   emphasis: { itemStyle: { borderColor: ink, borderWidth: 1.5 } } }],
      });

      const clim = echarts.init(climRef.current, undefined, { renderer: "svg" });
      charts.push(clim);
      const c = s.climatology;
      clim.setOption({
        animation: false,
        aria: { enabled: true, label: { description: t(`Media mensual con rango intercuartílico en ${place}`, `Monthly mean with interquartile range in ${place}`) } },
        grid: { left: 52, right: 12, top: 26, bottom: 28 },
        xAxis: { type: "category", data: M, axisLabel: { color: muted }, axisLine: { lineStyle: { color: cssVar("--rule") } } },
        yAxis: { type: "value", name: t(`${s.unit} por mes`, `${s.unit} per month`), nameTextStyle: { color: muted, align: "left" },
                 axisLabel: { color: muted }, splitLine: { lineStyle: { color: grid } } },
        tooltip: { ...tooltip, trigger: "axis", formatter: (ps: { dataIndex: number }[]) => {
          const m = c[ps[0]!.dataIndex]!;
          const lbl = apiText(m.label);
          return m.mean == null ? `${lbl}: ${t("sin dato", "no data")}` :
            `<b>${lbl}</b><br>${t("media", "mean")} ${fmt(m.mean, d)} · ${t("mediana", "median")} ${fmt(m.median, d)} ${s.unit}<br>P25–P75: ${fmt(m.p25, d)}–${fmt(m.p75, d)}<br>${m.n_valid} ${t("de", "of")} ${m.n_years} ${t("años con dato", "years with data")}`;
        } },
        series: [
          { name: "P25", type: "line", data: c.map((m) => m.p25), stack: "iqr", symbol: "none", lineStyle: { opacity: 0 }, silent: true },
          { name: "P25–P75", type: "line", data: c.map((m) => (m.p75 != null && m.p25 != null ? m.p75 - m.p25 : null)),
            stack: "iqr", symbol: "none", lineStyle: { opacity: 0 }, areaStyle: { color: cssVar("--fan") }, silent: true },
          { name: t("media", "mean"), type: "line", data: c.map((m) => m.mean), symbol: "circle", symbolSize: 6,
            lineStyle: { color: cssVar("--trend"), width: 2.4 }, itemStyle: { color: cssVar("--trend") } },
          { name: t("mediana", "median"), type: "line", data: c.map((m) => m.median), symbol: "none",
            lineStyle: { color: cssVar("--series"), width: 1.2, type: "dashed" } },
        ],
      });
    })();
    const ro = new ResizeObserver(() => charts.forEach((ch) => ch.resize()));
    if (heatRef.current) ro.observe(heatRef.current);
    return () => { disposed = true; ro.disconnect(); charts.forEach((ch) => ch.dispose()); };
  }, [s, theme, place, lang]);

  return (
    <section className="panel seasonal" aria-label={t("Ciclo estacional", "Seasonal cycle")}>
      <h2>{t("¿Cuándo llueve o cambia en el año? Ciclo estacional", "When does it rain or change during the year? Seasonal cycle")}</h2>
      {q.isPending && <p className="state" role="status">{t("Calculando ciclo estacional…", "Computing seasonal cycle…")}</p>}
      {q.error && <p className="state" role="alert">{apiText(q.error.problem.detail)}</p>}
      {s && (
        <>
          <p className="hint">
            {t("Mes más alto en promedio", "Highest month on average")}: <b>{apiText(s.peak_month)}</b>; {t("más bajo", "lowest")}: <b>{apiText(s.low_month)}</b>.
            {s.n_missing > 0 && t(` ${s.n_missing} de ${s.n_months} meses sin dato (no se rellenan).`, ` ${s.n_missing} of ${s.n_months} months without data (not filled in).`)}
          </p>
          <div className="seasonal-grid">
            <div>
              <h3>{t("Cada mes de cada año", "Every month of every year")}</h3>
              <div ref={heatRef} className="chart heat" role="img" aria-label={t(`Mapa de calor año por mes en ${place}`, `Year-by-month heat map in ${place}`)} />
            </div>
            <div>
              <h3>{t("Ciclo medio del periodo", "Mean cycle of the period")}</h3>
              <div ref={climRef} className="chart clim" role="img" aria-label={t(`Climatología mensual en ${place}`, `Monthly climatology in ${place}`)} />
              <p className="legend-line"><span className="lg trend-k" />{t("media", "mean")} <span className="lg series-k" />{t("mediana", "median")}
                <span className="lg fan-k" />{t("rango intercuartílico P25–P75", "P25–P75 interquartile range")}</p>
              <table className="table extremes">
                <caption>{t("Meses más altos del periodo", "Highest months of the period")}</caption>
                <thead><tr><th scope="col">{t("Mes", "Month")}</th><th scope="col">{t("Valor", "Value")}</th><th scope="col">{t("Sobre su media mensual", "Above its monthly mean")}</th></tr></thead>
                <tbody>
                  {s.extremes.map((e) => (
                    <tr key={e.label}><th scope="row">{apiText(e.label)}</th><td className="num">{fmt(e.value, 0)} {s.unit}</td>
                      <td className="num">{signed(e.anomaly, 0)} {s.unit}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="hint">{apiText(s.note)}</p>
        </>
      )}
    </section>
  );
}
