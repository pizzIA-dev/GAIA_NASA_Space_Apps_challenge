"use client";
// Historia guiada (plan §9.2): seis escenas declaradas en src/stories/*.json. Todo número sale de la API en tiempo real.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo } from "react";
import { api, ApiError } from "@/lib/api";
import { digitsFor, fmt, fmtP, signed, unitPerDecade, verdictOf } from "@/lib/format";
import { buildSpec, DEFAULT_STUDY } from "@/lib/study";
import { useResolvedTheme } from "@/lib/theme";
import type { CompareResult, Run } from "@/lib/types";
import story from "@/stories/trujillo-el-nino.json";
import { CaseAssociation } from "../explorer/CaseAssociation";
import { CaseEventsPanel } from "../explorer/CaseEventsPanel";
import { CaseBacktest } from "./CaseBacktest";
import { TrendChart } from "../explorer/TrendChart";

type Scene = (typeof story.scenes)[number];
const P = story.period;
const SEN = { estimator: "theil_sen", interval_method: "theil_sen_analytic", significance_test: "mann_kendall" };

function specFor(v: { dataset_id: string; variable_id: string; where: string }) {
  return {
    data: { dataset_id: v.dataset_id, variable_id: v.variable_id },
    geography: v.where === "ocean" ? { custom_geometry: story.ocean_roi.geometry } : { geo_ids: [story.province] },
    time: { start: `${P.start}-01-01`, end_exclusive: `${P.end + 1}-01-01`, granularity: "year" },
    statistics: SEN,
  };
}

function SceneShell({ scene, index, children }: { scene: Scene; index: number; children: React.ReactNode }) {
  return (
    <section className="scene" id={scene.id} aria-labelledby={`${scene.id}-h`}>
      <p className="scene-num" aria-hidden="true">{index + 1}</p>
      <div className="scene-body">
        <h2 id={`${scene.id}-h`}>{scene.title}</h2>
        <p className="lead">{scene.lead}</p>
        {children}
      </div>
    </section>
  );
}

function Pending() { return <p className="state" role="status">Calculando con datos oficiales…</p>; }
function Failed({ e }: { e: unknown }) {
  return <p className="state" role="alert">{e instanceof ApiError ? e.problem.detail : "No se pudo calcular esta escena."}</p>;
}

function Scene1({ scene, theme }: { scene: Scene; theme: string }) {
  const vars = (scene as { variables: { dataset_id: string; variable_id: string; label: string; where: string }[] }).variables;
  return (
    <div className="scene-grid">
      {vars.map((v) => <TrendCard key={v.variable_id} v={v} theme={theme} />)}
    </div>
  );
}

function TrendCard({ v, theme }: { v: { dataset_id: string; variable_id: string; label: string; where: string }; theme: string }) {
  const spec = useMemo(() => specFor(v), [v]);
  const q = useQuery<Run, ApiError>({ queryKey: ["run", spec], queryFn: () => api.analyze(spec) });
  const st = q.data?.statistics, vd = st ? verdictOf(st) : null, d = digitsFor(st?.estimate);
  const unit = st?.estimate_unit.split("/")[0] ?? "";
  return (
    <article className="panel trend-card" data-variable={v.variable_id}>
      <h3>{v.label}</h3>
      <p className="muted small">{v.where === "ocean" ? story.ocean_roi.label : "Provincia de Trujillo"}</p>
      {q.isPending && <Pending />}
      {q.error && <Failed e={q.error} />}
      {st && q.data && (
        <>
          <span className="tag" data-kind={vd!.kind}>{vd!.label}</span>
          <p className="fact num">{signed(st.estimate, d)} {unitPerDecade(st.estimate_unit)}</p>
          <p className="small muted">IC 95 % {signed(st.ci_lower, d)} a {signed(st.ci_upper, d)} · Mann–Kendall p = {fmtP(st.p_value)}</p>
          <TrendChart run={q.data} unit={unit} anomaly={false} theme={theme} />
          {v.where === "ocean" && <p className="small muted">{story.ocean_roi.note}</p>}
        </>
      )}
    </article>
  );
}

function Scene2() {
  const prov = useQuery({ queryKey: ["geo", story.province], queryFn: () => api.geography(story.province) });
  const units = prov.data?.children ?? [];
  const specs = useMemo(() => units.map((u) => buildSpec({ ...DEFAULT_STUDY, selected: u.geo_id }, u.geo_id, "annual")), [units]);
  const fam = useQuery<CompareResult, ApiError>({ queryKey: ["compare", specs], queryFn: () => api.compare(specs, "historia:distritos"),
    enabled: specs.length > 0 });
  if (prov.isPending || fam.isPending) return <Pending />;
  if (fam.error) return <Failed e={fam.error} />;
  const items = (fam.data?.items ?? []).map((it, i) => ({ it, u: units[i]! })).filter((x) => x.it.statistics)
    .sort((a, b) => a.it.statistics!.estimate! - b.it.statistics!.estimate!);
  const evidence = items.filter((x) => verdictOf(x.it.statistics!).kind !== "nc").length;
  const negative = items.filter((x) => x.it.statistics!.estimate! < 0).length;
  const sub = items.filter((x) => x.it.statistics!.warnings.some((w) => w.includes("píxel"))).length;
  return (
    <>
      <p className="finding">
        {negative} de {items.length} distritos tienen pendiente negativa, pero {evidence === 0 ? "ninguno muestra" : `${evidence} muestran`} evidencia
        de cambio tras corregir por las {items.length} comparaciones (BH-FDR). {sub} distritos son más pequeños que un píxel IMERG:
        su valor es el de una celda compartida.
      </p>
      <table className="table">
        <caption className="sr-only">Pendiente de la lluvia anual por distrito, ordenada</caption>
        <thead><tr><th scope="col">Distrito</th><th scope="col">mm por década</th><th scope="col">IC 95 %</th><th scope="col">q</th><th scope="col">Veredicto</th></tr></thead>
        <tbody>
          {items.map(({ it, u }) => {
            const s = it.statistics!, v = verdictOf(s);
            return (
              <tr key={u.geo_id}>
                <th scope="row">{u.name}{s.warnings.some((w) => w.includes("píxel")) && <small className="muted"> · menor que un píxel</small>}</th>
                <td className="num">{signed(s.estimate, 1)}</td>
                <td className="num">{signed(s.ci_lower, 1)} a {signed(s.ci_upper, 1)}</td>
                <td className="num">{fmtP(s.q_value)}</td>
                <td><span className="tag" data-kind={v.kind}>{v.label}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="small"><Link href="/estudio">Compáralos tú mismo en el Estudio</Link>.</p>
    </>
  );
}

function Scene3({ theme }: { theme: string }) {
  const spec = useMemo(() => buildSpec({ ...DEFAULT_STUDY, view: "anomaly" }, story.province, "anomaly"), []);
  const run = useQuery<Run, ApiError>({ queryKey: ["run", spec], queryFn: () => api.analyze(spec) });
  const events = useQuery({ queryKey: ["case-events", story.province, P.start, P.end], queryFn: () => api.caseEvents(story.province, P.start, P.end) });
  const enfen = useQuery({ queryKey: ["case-enfen", P.start, P.end], queryFn: () => api.caseEnfen(P.start, P.end) });
  const annualSpec = useMemo(() => specFor({ dataset_id: "nasa-gpm-imerg-monthly-v07", variable_id: "precipitation_mm_month", where: "province" }), []);
  const annual = useQuery<Run, ApiError>({ queryKey: ["run", annualSpec], queryFn: () => api.analyze(annualSpec) });
  const seasonal = useQuery({ queryKey: ["seasonal", annual.data?.run_id], queryFn: () => api.seasonal(annual.data!.run_id), enabled: !!annual.data });
  if (run.isPending || events.isPending) return <Pending />;
  if (run.error) return <Failed e={run.error} />;
  const ev = events.data?.items ?? [];
  const inNino = ev.filter((e) => e.display_class === "coincidencia_el_nino");
  const byEp = inNino.reduce<Record<string, number>>((a, e) => ({ ...a, [e.enfen.episode_id ?? "?"]: (a[e.enfen.episode_id ?? "?"] ?? 0) + 1 }), {});
  const top = seasonal.data?.extremes[0];
  return (
    <>
      <p className="finding">
        {ev.length} registros de huaico o inundación entre {P.start} y {P.end}; {inNino.length} ocurrieron durante un episodio El Niño
        Costero ({Object.entries(byEp).map(([k, n]) => `${n} en ${k}`).join(", ")}) y {ev.length - inNino.length} fuera de ellos.
        {top && ` El mes más lluvioso del periodo fue ${top.label}: ${fmt(top.value, 0)} mm, ${fmt(top.anomaly, 0)} mm por encima de su media mensual.`}
        {" "}Que coincidan en el tiempo no demuestra que El Niño causara cada evento: ninguno tiene atribución causal verificada.
      </p>
      {run.data && <TrendChart run={run.data} unit="mm" anomaly theme={theme} events={ev} episodes={enfen.data?.episodes} />}
      {events.data && <CaseEventsPanel nested data={events.data} enfen={enfen.data} place="la provincia de Trujillo" />}
    </>
  );
}

function Scene6() {
  const s = useQuery({ queryKey: ["case-summary"], queryFn: api.caseSummary });
  if (s.isPending) return <Pending />;
  if (s.error || !s.data) return <Failed e={s.error} />;
  const r = s.data.reconciliation;
  return (
    <>
      <ul className="limits">{s.data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      <p className="small muted">
        Control con el estudio previo: {r.official_2017_2025} registros oficiales en 2017–2025 en {r.official_districts_2017_2025.length} distritos
        ({r.status === "coincide" ? "coincide con la referencia histórica de 16" : "difiere de la referencia: revisar"}). {r.note}
      </p>
      <p className="small muted">Fuentes: {s.data.sources.map((x) => x.name).join("; ")}. Datos NASA vía Google Earth Engine.</p>
    </>
  );
}

export function Story() {
  const theme = useResolvedTheme();
  return (
    <main className="story" id="contenido">
      <header className="story-head">
        <p className="muted small"><Link href="/historias">Historias</Link> › caso demostrativo</p>
        <h1>{story.title}</h1>
        <p className="lead">{story.subtitle}</p>
        <nav aria-label="Escenas" className="scene-nav">
          {story.scenes.map((s, i) => <a key={s.id} href={`#${s.id}`}>{i + 1}. {s.title}</a>)}
        </nav>
      </header>
      {story.scenes.map((scene, i) => (
        <SceneShell key={scene.id} scene={scene} index={i}>
          {scene.id === "que-cambia" && <Scene1 scene={scene} theme={theme} />}
          {scene.id === "donde" && <Scene2 />}
          {scene.id === "anios-2017-2023" && <Scene3 theme={theme} />}
          {scene.id === "relacion" && (
            <CaseAssociation auto heading={false} datasetId="nasa-gpm-imerg-monthly-v07" variableId="precipitation_mm_month"
              quantity="precipitación" start={P.start} end={P.end} />
          )}
          {scene.id === "alerta" && <CaseBacktest />}
          {scene.id === "limites" && <Scene6 />}
        </SceneShell>
      ))}
    </main>
  );
}
