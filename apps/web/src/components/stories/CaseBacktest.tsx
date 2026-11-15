"use client";
// Escena 5 del caso (plan §9.2): ¿habría dado una alerta? Toda cifra viene de GET /cases/{id}/backtest.
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { fmt } from "@/lib/format";
import type { CaseBacktest as Result } from "@/lib/types";

const pct = (v: number | null | undefined) => (v == null ? "sin dato" : `${fmt(v * 100, 0)} %`);
const ci = (c: (number | null)[]) => (c[0] == null || c[1] == null ? "sin dato" : `${pct(c[0])} a ${pct(c[1])}`);
const days = (n: number) => `${n} ${n === 1 ? "día" : "días"}`;

export function CaseBacktest() {
  const q = useQuery<Result, ApiError>({ queryKey: ["case-backtest"], queryFn: api.caseBacktest });
  if (q.isPending) return <p className="state" role="status">Calculando con datos oficiales…</p>;
  if (q.error || !q.data) return <p className="state" role="alert">{q.error?.problem.detail ?? "No se pudo calcular esta escena."}</p>;
  const r = q.data, rule = r.primary.rule, t = r.primary.test_out_of_sample, c = r.primary.calibration_in_sample;
  const name = (u: string) => r.unit_names[u] ?? u;
  const alerts = t.contingency.tp + t.contingency.fp;
  return (
    <div className="backtest">
      <p className="finding">
        Regla declarada antes de ver los resultados: alerta en un distrito cuando la lluvia de los {days(rule.window_days)} anteriores
        supera su percentil {rule.percentile} de {r.periods.calibration[0].slice(0, 4)}–{r.periods.calibration[1].slice(0, 4)};
        se considera acierto si hay un registro SINPAD en los {days(rule.horizon_days)} siguientes.
        Fuera de muestra ({r.periods.test[0].slice(0, 4)}–{r.periods.test[1].slice(0, 4)}) anticipó{" "}
        <b>{t.events_anticipated} de {t.events_evaluable}</b> registros evaluables (IC 95 % {ci(t.pod_ci95)}).
        Emitió {fmt(alerts, 0)} alertas distrito-día{alerts > 0 && t.contingency.tp === 0
          ? "; ninguna fue seguida de un registro (falsas alarmas: 100 %)."
          : ` y ${fmt(t.contingency.fp, 0)} no tuvieron registro (falsas alarmas: ${pct(t.far)}).`} Con alertas al azar de la misma frecuencia se esperaría anticipar el {pct(t.pod_random_expected)}.
      </p>
      <div className="scene-grid">
        <table className="table contingency">
          <caption>Distrito-día en el periodo de prueba</caption>
          <thead><tr><td /><th scope="col">Con registro</th><th scope="col">Sin registro</th></tr></thead>
          <tbody>
            <tr><th scope="row">Alerta</th><td className="num">{fmt(t.contingency.tp, 0)}</td><td className="num">{fmt(t.contingency.fp, 0)}</td></tr>
            <tr><th scope="row">Sin alerta</th><td className="num">{fmt(t.contingency.fn, 0)}</td><td className="num">{fmt(t.contingency.tn, 0)}</td></tr>
          </tbody>
        </table>
        <table className="table">
          <caption>Registros del periodo de prueba</caption>
          <thead><tr><th scope="col">Fecha</th><th scope="col">Distrito</th><th scope="col">Lluvia previa</th><th scope="col">Umbral</th><th scope="col">¿Anticipado?</th></tr></thead>
          <tbody>
            {t.events_detail.map((e) => (
              <tr key={`${e.date}-${e.unit}`}>
                <th scope="row" className="num">{e.date}</th>
                <td>{name(e.unit)}</td>
                <td className="num">{e.signal_mm == null ? "sin dato" : `${fmt(e.signal_mm, 1)} mm`}</td>
                <td className="num">{e.threshold_mm == null ? "sin dato" : `${fmt(e.threshold_mm, 1)} mm`}</td>
                <td>{!e.evaluable ? "no evaluable" : e.anticipated ? `sí, ${days(e.lead_days ?? 0)} antes` : "no"}</td>
              </tr>
            ))}
            {r.events_excluded.filter((e) => e.date >= r.periods.test[0]).map((e) => (
              <tr key={`x-${e.date}-${e.ubigeo}`} className="muted">
                <th scope="row" className="num">{e.date}</th><td>{e.district}</td><td colSpan={3}>excluido: {e.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">
        En el periodo de calibración (en muestra, optimista) anticipó {c.events_anticipated} de {c.events_evaluable} registros con
        {" "}{pct(c.far)} de falsas alarmas. Promedio: {fmt(t.alerts_per_unit_per_year, 1)} alertas por distrito y año en la prueba.
      </p>
      <details className="sensitivity">
        <summary>Sensibilidad: las {r.grid.length} combinaciones evaluadas</summary>
        <table className="table">
          <caption className="sr-only">Desempeño fuera de muestra por percentil, ventana y horizonte</caption>
          <thead><tr><th scope="col">Percentil</th><th scope="col">Ventana</th><th scope="col">Horizonte</th><th scope="col">Anticipados</th>
            <th scope="col">Falsas alarmas</th><th scope="col">Alertas por distrito-año</th><th scope="col">Azar esperado</th></tr></thead>
          <tbody>
            {r.grid.map((g) => {
              const prim = g.percentile === rule.percentile && g.window_days === rule.window_days && g.horizon_days === rule.horizon_days;
              return (
                <tr key={`${g.percentile}-${g.window_days}-${g.horizon_days}`} data-primary={prim || undefined}>
                  <th scope="row">P{g.percentile}{prim && <small className="muted"> · principal</small>}</th>
                  <td className="num">{days(g.window_days)}</td><td className="num">{days(g.horizon_days)}</td>
                  <td className="num">{g.test.events_anticipated}/{g.test.events_evaluable}</td>
                  <td className="num">{pct(g.test.far)}</td><td className="num">{fmt(g.test.alerts_per_unit_per_year, 1)}</td>
                  <td className="num">{pct(g.test.pod_random_expected)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="small muted">Escoger aquí la mejor fila después de verla sería sobreajustar: con tan pocos registros, cualquier
          diferencia entre filas puede ser azar.</p>
      </details>
      <ul className="warn">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      <p className="small muted">Datos: {r.source.provenance}</p>
    </div>
  );
}
