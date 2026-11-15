"use client";
// Escena 4 del caso (plan §9.2): ¿relación o coincidencia? Se calcula en la API (11 análisis), solo a pedido.
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, ApiError } from "@/lib/api";
import { fmt, fmtP, signed } from "@/lib/format";
import type { CaseAssociationResult } from "@/lib/types";

export function CaseAssociation({ datasetId, variableId, quantity, start, end, auto = false, heading = true }:
  { datasetId: string; variableId: string; quantity: string; start: number; end: number; auto?: boolean; heading?: boolean }) {
  const m = useMutation<CaseAssociationResult, ApiError>({
    mutationFn: () => api.caseAssociation({ dataset_id: datasetId, variable_id: variableId, year_from: start, year_to: end }),
  });
  const started = useRef(false);
  useEffect(() => {
    if (auto && !started.current) { started.current = true; m.mutate(); }
  }, [auto, m]);
  const r = m.data;
  return (
    <section className="panel case-assoc" aria-label="Relación o coincidencia">
      {heading && <h2>¿Relación o coincidencia?</h2>}
      <p className="hint">
        Compara la anomalía de {quantity} en los meses de cada distrito con registro SINPAD frente a los meses sin registro
        del mismo mes calendario, en el mismo mes y hasta 3 meses antes. Requiere un análisis por distrito de la provincia.
      </p>
      {!r && (
        <button type="button" className="btn" onClick={() => m.mutate()} disabled={m.isPending}>
          {m.isPending ? "Calculando panel distrito × mes…" : `Analizar asociación con ${quantity}`}
        </button>
      )}
      {m.error && <p className="state" role="alert">{m.error.problem.detail}</p>}
      {r && (
        <>
          <table className="table assoc-table">
            <caption className="sr-only">Anomalía en meses con registro frente a meses sin registro, por desfase</caption>
            <thead>
              <tr><th scope="col">Anomalía medida</th><th scope="col">Diferencia</th><th scope="col">p</th>
                <th scope="col" title="Corregido BH-FDR sobre los desfases">q</th><th scope="col">Lectura</th></tr>
            </thead>
            <tbody>
              {r.results.map((x) => {
                // Familia de desfases: la lectura usa el q-valor BH-FDR (plan §7.5).
                const reading = x.status !== "ok" ? "—" : x.q_value != null && x.q_value < 0.05
                  ? (x.effect! > 0 ? "más alta con registro" : "más baja con registro") : "sin diferencia distinguible";
                return (
                  <tr key={x.lag_months}>
                    <th scope="row">{x.lag_months === 0 ? "el mismo mes" : `${x.lag_months} ${x.lag_months === 1 ? "mes" : "meses"} antes`}</th>
                    <td className="num">{x.effect != null ? `${signed(x.effect, Math.abs(x.effect) < 1 ? 3 : 1)} ${x.effect_unit ?? ""}` : "sin dato"}</td>
                    <td className="num">{fmtP(x.p_value)}</td>
                    <td className="num">{fmtP(x.q_value)}</td>
                    <td>{reading}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {r.results[0] && r.results[0].status === "ok" && (
            <p className="hint">
              {r.results[0].n_event_months} distrito-mes con registro y {fmt(r.results[0].n_control_months, 0)} sin registro, en {r.n_units} distritos;
              {" "}{r.results[0].n_independent_episodes} episodios independientes (el mayor, {r.results[0].dominant_episode}, reúne el {fmt(r.results[0].dominant_episode_share! * 100, 0)} %).
              {r.events_excluded_no_geometry > 0 && ` ${r.events_excluded_no_geometry} registros sin polígono IGN quedan fuera.`}
            </p>
          )}
          <ul className="warn">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          <p className="hint">{r.interpretation} Permutación estratificada ({fmt(r.resamples, 0)} repeticiones, semilla {r.seed}).</p>
        </>
      )}
    </section>
  );
}
