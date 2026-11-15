"use client";
// Panel ambiental (experiencia principal): un territorio, un periodo, varias variables NASA, el método y el nivel de
// confianza que elija el usuario. Cada tarjeta es un análisis /analyses independiente (carga progresiva, caché
// compartida con Explorar, Estudio, API y SDK). Ningún cálculo estadístico se hace en el navegador.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, isTransient } from "@/lib/api";
import { digitsFor, fmt, fmtP, signed, TEST_LABEL, unitPerDecade, verdictOf } from "@/lib/format";
import { METHOD_SHORT, RECOMMENDED, UNCORRECTED } from "@/lib/methods";
import { simpleName, simpleUnit } from "@/lib/variables";
import { statisticsFor, type Method } from "@/lib/study";
import { useResolvedTheme } from "@/lib/theme";
import type { CostEstimate, Dataset, Geography, Run, Variable } from "@/lib/types";
import { ErrorPanel, Provenance } from "../explorer/Explorer";
import { TrendChart } from "../explorer/TrendChart";

const DEFAULT_GEO = "pe-ign2020:15"; // Lima (Perú): ejemplo inicial, cambiable a cualquier territorio
const DEFAULT_VARS = [
  "nasa-gpm-imerg-monthly-v07/precipitation_mm_month", "nasa-merra2-slv/air_temperature_2m_c",
  "nasa-gldas-noah-v21-3h/soil_moisture_0_10cm_kgm2", "nasa-modis-mod13q1-061/ndvi",
];
const FIRST_YEAR = 2001, LAST_YEAR = 2024;
const range = (a: number, b: number) => Array.from({ length: Math.max(0, b - a + 1) }, (_, i) => a + i);

interface Config {
  geo: string; start: number; end: number; vars: string[];
  estimator: "theil_sen" | "ols"; ic: string; prueba: string; conf: number;
}

function readConfig(p: URLSearchParams): Config {
  const estimator = p.get("estimador") === "ols" ? "ols" : "theil_sen";
  const rec = RECOMMENDED[estimator]!;
  const start = Number(p.get("desde")) || 2003, end = Number(p.get("hasta")) || 2024;
  return {
    geo: p.get("territorio") || DEFAULT_GEO,
    start: Math.max(FIRST_YEAR, Math.min(start, LAST_YEAR - 9)), end: Math.min(LAST_YEAR, Math.max(end, start + 9)),
    vars: p.get("variables")?.split(",").filter(Boolean) ?? DEFAULT_VARS,
    estimator, ic: p.get("ic") || rec.interval_method, prueba: p.get("prueba") || rec.significance_test,
    conf: [0.9, 0.95, 0.99].includes(Number(p.get("confianza"))) ? Number(p.get("confianza")) : 0.95,
  };
}

/** Preset + variantes → la misma especificación que construyen Explorar/Estudio (mismo run_id para lo mismo). */
function methodState(c: Config): { method: Method; ic?: string; prueba?: string; conf?: number } {
  const boot = c.ic === "moving_block_bootstrap";
  const method: Method = c.estimator === "ols" ? "ols" : boot ? "sen_boot" : "sen";
  const presetIc = method === "ols" ? "ar1_effective_n" : boot ? "moving_block_bootstrap" : "theil_sen_ar1";
  const presetTest = method === "ols" ? "ols_ar1_t" : "mann_kendall_ar1";
  return { method, ic: c.ic !== presetIc ? c.ic : undefined, prueba: c.prueba !== presetTest ? c.prueba : undefined,
    conf: c.conf !== 0.95 ? c.conf : undefined };
}

function specFor(c: Config, key: string): object {
  const [dataset_id, variable_id] = key.split("/");
  return {
    data: { dataset_id, variable_id }, geography: { geo_ids: [c.geo] },
    time: { start: `${c.start}-01-01`, end_exclusive: `${c.end + 1}-01-01`, granularity: "year" },
    statistics: statisticsFor(methodState(c)),
  };
}

export function Dashboard() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const c = useMemo(() => readConfig(new URLSearchParams(params.toString())), [params]);
  // Cambios encadenados antes de que la URL se actualice no deben pisarse: se acumulan sobre el último pendiente.
  const pending = useRef<string | null>(null);
  useEffect(() => { pending.current = null; }, [params]);
  const set = (patch: Record<string, string | null>) => {
    const q = new URLSearchParams(pending.current ?? params.toString());
    for (const [k, v] of Object.entries(patch)) { if (v == null) q.delete(k); else q.set(k, v); }
    const s = q.toString();
    pending.current = s;
    router.replace(`${pathname}${s ? `?${s}` : ""}`, { scroll: false });
  };
  const caps = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities, staleTime: Infinity });
  const variables = useQuery({ queryKey: ["variables"], queryFn: api.variables, staleTime: Infinity });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets, staleTime: Infinity });
  const geo = useQuery({ queryKey: ["geo", c.geo], queryFn: () => api.geography(c.geo) });
  const est = caps.data?.estimators[c.estimator];

  return (
    <div className="layout dash" id="contenido">
      <aside className="rail" aria-label="Configuración del panel">
        <section>
          <h2>Territorio</h2>
          <TerritoryPicker geo={geo.data} onPick={(id) => set({ territorio: id === DEFAULT_GEO ? null : id })} />
        </section>
        <section>
          <h2>Periodo</h2>
          <div className="years">
            <label>Desde <select value={c.start} onChange={(e) => set({ desde: e.target.value })}>
              {range(FIRST_YEAR, c.end - 9).map((y) => <option key={y}>{y}</option>)}</select></label>
            <label>hasta <select value={c.end} onChange={(e) => set({ hasta: e.target.value })}>
              {range(c.start + 9, LAST_YEAR).map((y) => <option key={y}>{y}</option>)}</select></label>
          </div>
        </section>
        <section>
          <h2>Variables</h2>
          <div className="chips" role="group" aria-label="Variables NASA">
            {variables.data?.map((v) => {
              const key = `${v.dataset_id}/${v.variable_id}`, on = c.vars.includes(key);
              return (
                <button key={key} type="button" className="chip" aria-pressed={on}
                  onClick={() => set({ variables: (on ? c.vars.filter((k) => k !== key) : [...c.vars, key]).join(",") || null })}>
                  {simpleName(v.dataset_id, v.variable_id, v.physical_quantity)}
                </button>
              );
            })}
          </div>
        </section>
        <section>
          <h2>Método</h2>
          <label className="field">Tendencia
            <select value={c.estimator} onChange={(e) => set({ estimador: e.target.value === "ols" ? "ols" : null, ic: null, prueba: null })}>
              {Object.keys(caps.data?.estimators ?? { theil_sen: 1, ols: 1 }).map((k) => <option key={k} value={k}>{METHOD_SHORT[k] ?? k}</option>)}
            </select>
          </label>
          <label className="field">Nivel de confianza
            <select value={c.conf} onChange={(e) => set({ confianza: Number(e.target.value) === 0.95 ? null : e.target.value })}>
              {(caps.data?.confidence_levels ?? [0.9, 0.95, 0.99]).map((l) => <option key={l} value={l}>{Math.round(l * 100)} %</option>)}
            </select>
          </label>
          <details className="advanced" open={c.ic !== RECOMMENDED[c.estimator]!.interval_method || c.prueba !== RECOMMENDED[c.estimator]!.significance_test}>
            <summary>Opciones avanzadas</summary>
            <label className="field">Intervalo de confianza
              <select value={c.ic} onChange={(e) => set({ ic: e.target.value === RECOMMENDED[c.estimator]!.interval_method ? null : e.target.value })}>
                {(est?.interval_methods ?? [c.ic]).map((m) => <option key={m} value={m}>{METHOD_SHORT[m] ?? m}{m === RECOMMENDED[c.estimator]!.interval_method ? " ★" : ""}</option>)}
              </select>
            </label>
            <label className="field">Prueba de significancia
              <select value={c.prueba} onChange={(e) => set({ prueba: e.target.value === RECOMMENDED[c.estimator]!.significance_test ? null : e.target.value })}>
                {(est?.significance_tests ?? [c.prueba]).map((m) => <option key={m} value={m}>{METHOD_SHORT[m] ?? m}{m === RECOMMENDED[c.estimator]!.significance_test ? " ★" : ""}</option>)}
              </select>
            </label>
            <p className="hint">★ recomendado: corrige la autocorrelación. <Link href="/metodos">Métodos</Link></p>
          </details>
          {(UNCORRECTED.has(c.ic) || UNCORRECTED.has(c.prueba)) && (
            <p className="hint warn-hint">Este método no corrige la autocorrelación: su confianza real es menor que la indicada.</p>
          )}
        </section>
      </aside>

      <main className="main">
        <header className="dash-head">
          <p className="muted small">{geo.data ? [...(geo.data.path ?? []), geo.data.name].join(" › ") : "Cargando territorio…"}</p>
          <h1>{geo.data?.name ?? "Territorio"} · {c.start}–{c.end}</h1>
          {geo.error && <p className="state" role="alert">{(geo.error as ApiError).problem.detail}</p>}
        </header>
        {c.vars.length === 0 && <p className="state">Elige al menos una variable.</p>}
        <div className="dash-grid">
          {c.vars.map((key) => (
            <VariableCard key={key} cfg={c} varKey={key}
              variable={variables.data?.find((v) => `${v.dataset_id}/${v.variable_id}` === key)}
              dataset={datasets.data?.find((d) => d.dataset_id === key.split("/")[0])} />
          ))}
        </div>
        <p className="hint dash-more">
          <Link href={`/atlas?territorio=${encodeURIComponent(c.geo)}`}>Ver el mapa por subdivisiones</Link>
        </p>
      </main>
    </div>
  );
}

function VariableCard({ cfg, varKey, variable, dataset }:
  { cfg: Config; varKey: string; variable?: Variable; dataset?: Dataset }) {
  const theme = useResolvedTheme();
  const spec = useMemo(() => specFor(cfg, varKey), [cfg, varKey]);
  // Si Earth Engine está ocupado (503 source_busy) se reintenta solo, sin que el usuario tenga que hacer nada.
  const q = useQuery<Run, ApiError>({ queryKey: ["run", spec], queryFn: () => api.analyze(spec),
    retry: (n, e) => n < 12 && isTransient(e), retryDelay: 10_000 });
  const est = useQuery({ queryKey: ["cost", spec], queryFn: () => api.estimateCost(spec), enabled: q.isPending, staleTime: Infinity });
  const st = q.data?.statistics, vd = st ? verdictOf(st) : null, d = digitsFor(st?.estimate);
  const unit = simpleUnit(variable?.unit_display ?? "");
  const ms = methodState(cfg);
  const detail = `/explorar?focus=${encodeURIComponent(cfg.geo)}&selected=${encodeURIComponent(cfg.geo)}&datasetId=${varKey.split("/")[0]}` +
    `&variableId=${varKey.split("/")[1]}&start=${cfg.start}&end=${cfg.end}${ms.method !== "sen" ? `&method=${ms.method}` : ""}` +
    `${ms.ic ? `&ic=${ms.ic}` : ""}${ms.prueba ? `&prueba=${ms.prueba}` : ""}${ms.conf ? `&conf=${ms.conf}` : ""}`;
  const [showProv, setShowProv] = useState(false);
  return (
    <section className="panel dash-card" aria-labelledby={`h-${varKey}`} data-variable={varKey.split("/")[1]}>
      <div className="panel-head">
        <h2 id={`h-${varKey}`}>{simpleName(varKey.split("/")[0] ?? "", varKey.split("/")[1] ?? "", variable?.physical_quantity ?? varKey)}</h2>
        {vd && <span className="tag" data-kind={vd.kind}>{vd.label}</span>}
      </div>
      {q.isPending && <Waiting cost={est.data?.cost} granularity={dataset?.native_granularity} retrying={q.failureCount > 0} />}
      {q.error && <ErrorPanel error={q.error} />}
      {st && q.data && (
        <>
          <p className="dash-value num">{st.estimate != null ? `${signed(st.estimate, d)} ${unitPerDecade(st.estimate_unit)}` : "Sin datos suficientes"}</p>
          {st.estimate != null && (
            <p className="dash-stats num">
              IC {Math.round(st.confidence_level * 100)} %: {signed(st.ci_lower, d)} a {signed(st.ci_upper, d)} · {TEST_LABEL[st.test_method] ?? st.test_method}: p = {fmtP(st.p_value)}
            </p>
          )}
          <TrendChart run={q.data} unit={unit} anomaly={false} theme={theme} />
        </>
      )}
      <p className="card-links">
        <Link href={detail}>Ver detalle</Link>
        {dataset && <button type="button" className="linkish" aria-expanded={showProv} onClick={() => setShowProv((s) => !s)}>Fuente y detalles</button>}
      </p>
      {showProv && dataset && (
        <>
          <Provenance dataset={dataset} />
          <p className="small muted">Disponible desde {dataset.temporal_coverage_start} · versión {dataset.version} · {dataset.license}.
            {st && ` Años con dato: ${st.n_observations} de ${st.n_observations + st.n_missing}.`}{q.data && ` run_id ${q.data.run_id}.`}</p>
          {st && st.warnings.length > 0 && <ul className="warn">{st.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
        </>
      )}
    </section>
  );
}

export function TerritoryPicker({ geo, onPick }: { geo?: Geography & { children: Geography[] }; onPick: (geoId: string) => void }) {
  const [q, setQ] = useState("");
  const iso3 = geo?.iso3 && geo.iso3.length === 3 ? geo.iso3 : null;
  const term = q.trim();
  const countries = useQuery({ queryKey: ["search-countries", term], queryFn: () => api.searchGeographies(term, null), enabled: term.length >= 2 });
  const inside = useQuery({ queryKey: ["search", term, iso3], queryFn: () => api.searchGeographies(term, iso3), enabled: term.length >= 2 && !!iso3 });
  const level = (g: Geography) => ({ ADM0: "país", ADM1: "1.ª división", ADM2: "2.ª división", ADM3: "3.ª división" }[g.admin_level] ?? g.admin_level);
  const items = [...(inside.data?.items ?? []), ...(countries.data?.items ?? [])];
  return (
    <div className="picker">
      <p className="crumb">{geo ? [...(geo.path ?? []), geo.name].join(" › ") : "…"}</p>
      <div className="search-wrap">
        <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar país o región" aria-label="Buscar territorio (cualquier país)" />
        {term.length >= 2 && (
          <ul className="results" role="listbox" aria-label="Resultados">
            {items.length === 0 && !countries.isPending && <li className="muted">Sin resultados.</li>}
            {items.map((g) => (
              <li key={g.geo_id}>
                <button type="button" className="terr" onClick={() => { onPick(g.geo_id); setQ(""); }}>
                  <span>{g.name} <small className="muted">{g.path?.slice(1).join(" › ")}</small></span>
                  <span className="muted">{level(g)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {geo?.parent_id && (
        <button type="button" className="btn small" onClick={() => onPick(geo.parent_id!)}>↑ Subir un nivel</button>
      )}
      {geo && geo.children.length > 0 && (
        <details className="children">
          <summary>{geo.children.length} subdivisiones</summary>
          <div className="list" role="group" aria-label={`Subdivisiones de ${geo.name}`}>
            {geo.children.map((u) => (
              <button key={u.geo_id} type="button" className="terr" onClick={() => onPick(u.geo_id)}>
                <span>{u.name}</span><span className="num muted">{fmt(u.area_km2, 0)} km²</span>
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

const GRANULARITY: Record<string, string> = {
  "1h": "horario", "3h": "de cada 3 horas", "1d": "diario", "16d": "de cada 16 días", month: "mensual",
};

/** Espera honesta: tiempo estimado del primer cálculo, tiempo transcurrido y que el resultado quedará guardado. */
function Waiting({ cost, granularity, retrying }: { cost?: CostEstimate; granularity?: string; retrying: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  if (cost?.tier === "cached") return <p className="state" role="status">Cargando resultado guardado…</p>;
  const secs = cost ? Math.max(5, Math.round(cost.estimated_seconds / 10) * 10) : null;
  return (
    <div className="state waiting" role="status">
      <p>
        <b>Calculando con datos NASA en Earth Engine</b>{granularity && GRANULARITY[granularity] ? ` (producto ${GRANULARITY[granularity]})` : ""}.
        {secs != null && ` La primera vez tarda aprox. ${secs >= 90 ? `${Math.round(secs / 60)} min` : `${secs} s`}`}
        {secs != null && "; después queda guardado y será inmediato para todos."}
      </p>
      <p className="muted small">
        {retrying ? "Earth Engine está ocupado con otros cálculos; reintentando automáticamente… " : ""}
        Llevamos {elapsed} s. Puedes revisar las otras variables mientras tanto.
      </p>
    </div>
  );
}
