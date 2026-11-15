"use client";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cssVar } from "@/lib/colors";
import { exportCsv, exportJson, exportPng, exportSvg } from "@/lib/export";
import { divergentStops } from "@/lib/colors";
import { digitsFor, fmt, fmtP, signed, TEST_LABEL, unitPerDecade, verdictOf } from "@/lib/format";
import { buildSpec, METHOD_LABEL, readStudyFromUrl, studyToUrl, useStudy, type Method } from "@/lib/study";
import type { CompareResult, Dataset, Geography, Run, Variable } from "@/lib/types";
import { useResolvedTheme } from "@/lib/theme";
import { TerritoryMap, type UnitResult } from "./TerritoryMap";
import { CaseEventsPanel } from "./CaseEventsPanel";
import { SeasonalPanel } from "./SeasonalPanel";
import { TrendChart } from "./TrendChart";

const ARTICLE: Record<string, string> = { ADM0: "", ADM1: "el departamento de ", ADM2: "la provincia de ", ADM3: "el distrito de " };
const where = (g?: Pick<Geography, "admin_level" | "name">) => (g ? `${ARTICLE[g.admin_level] ?? ""}${g.name}` : "el territorio");
const cleanQuantity = (q: string) => q.replace(/\s*\(.*?\)\s*/g, " ").trim();
const SHORT_SOURCE: Record<string, string> = {
  "nasa-gpm-imerg-monthly-v07": "IMERG", "nasa-gldas-noah-v21-3h": "GLDAS", "nasa-merra2-slv": "MERRA-2",
  "nasa-modis-mod13q1-061": "MODIS", "nasa-modis-aqua-sst-l3smi": "MODIS-Aqua",
};
const MAP_AUTO_MAX_UNITS = 12; // calcular el mapa automáticamente solo para productos mensuales y pocas unidades

export function Explorer() {
  const study = useStudy();
  const theme = useResolvedTheme();
  const chartRef = useRef<import("echarts").ECharts | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const hydrated = useRef(false);

  // URL → estado (una vez) y estado → URL (siempre): estudios compartibles por enlace.
  useEffect(() => {
    if (!hydrated.current) { study.set(readStudyFromUrl(params.toString())); hydrated.current = true; return; }
    router.replace(`${pathname}${studyToUrl(study)}`, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.focus, study.selected, study.datasetId, study.variableId, study.view, study.method, study.start, study.end, study.context]);

  const variables = useQuery({ queryKey: ["variables"], queryFn: api.variables });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const focus = useQuery({ queryKey: ["geo", study.focus], queryFn: () => api.geography(study.focus) });
  const features = useQuery({ queryKey: ["features", study.focus], queryFn: () => api.features(study.focus) });

  const dataset: Dataset | undefined = datasets.data?.find((d) => d.dataset_id === study.datasetId);
  const variable: Variable | undefined = variables.data?.find((v) => v.variable_id === study.variableId && v.dataset_id === study.datasetId);
  const anomaly = study.view === "anomaly";
  const spec = useMemo(() => buildSpec(study), [study]);
  const main = useQuery<Run, ApiError>({ queryKey: ["run", spec], queryFn: () => api.analyze(spec), enabled: !!variable });

  const units: Geography[] = useMemo(() => focus.data?.children ?? [], [focus.data]);
  const pixelKm2 = dataset ? (dataset.native_scale_m / 1000) ** 2 : 124;
  const autoMap = !!dataset && dataset.native_granularity === "month" && units.length <= MAP_AUTO_MAX_UNITS;
  const [mapRequested, setMapRequested] = useState<string>("");
  const mapKey = `${study.focus}|${study.datasetId}|${study.variableId}|${study.method}|${study.start}|${study.end}`;
  const mapEnabled = main.isSuccess && (autoMap || mapRequested === mapKey);
  // Una sola llamada /analyses/compare para todas las unidades (q-valores BH-FDR de la familia incluidos).
  const unitSpecs = useMemo(() => units.map((u) => buildSpec(study, u.geo_id, "annual")), [units, study]);
  const unitFamily = useQuery<CompareResult, ApiError>({
    queryKey: ["compare", unitSpecs], queryFn: () => api.compare(unitSpecs, `mapa:${study.focus}`),
    enabled: mapEnabled && unitSpecs.length > 0,
  });
  const results: Record<string, UnitResult> = {};
  units.forEach((u, i) => {
    const it = unitFamily.data?.items[i];
    results[u.geo_id] = { geoId: u.geo_id, st: it?.statistics, error: it?.error?.code };
  });
  const mapDone = unitFamily.data ? units.length : 0;

  // Capa de contexto local: solo donde existe un caso con fuente nacional conectada (plan §9.3).
  const hasCase = study.selected.startsWith("pe-ign2020:1301");
  const showCase = hasCase && study.context;
  const caseEvents = useQuery({ queryKey: ["case-events", study.selected, study.start, study.end],
    queryFn: () => api.caseEvents(study.selected, study.start, study.end), enabled: showCase });
  const caseEnfen = useQuery({ queryKey: ["case-enfen", study.start, study.end],
    queryFn: () => api.caseEnfen(study.start, study.end), enabled: showCase });

  const selectedGeo: Geography | undefined =
    study.selected === study.focus ? focus.data : units.find((u) => u.geo_id === study.selected);
  const unit = variable?.unit_display ?? "";

  return (
    <div className="layout" id="contenido">
      <aside className="rail" aria-label="Configuración del análisis">
        <section>
          <h2>Territorio</h2>
          <p className="crumb">{focus.data ? [...(focus.data.path ?? []), focus.data.name].join(" › ") : "Cargando…"}</p>
          <TerritorySearch onPick={(g) => study.set({ focus: g.geo_id, selected: g.geo_id })} />
          <div className="list" role="group" aria-label="Elegir territorio">
            <button type="button" className="terr" aria-pressed={study.selected === study.focus}
              onClick={() => study.set({ selected: study.focus })}>
              <span>{focus.data ? `${focus.data.name} completo` : "Territorio completo"}</span>
              <span className="num muted">{fmt(focus.data?.area_km2, 0)} km²</span>
            </button>
            {units.map((u) => {
              const st = results[u.geo_id]?.st;
              return (
                <button key={u.geo_id} type="button" className="terr" aria-pressed={study.selected === u.geo_id}
                  onClick={() => study.set({ selected: u.geo_id, view: "annual" })}>
                  <span>{u.name}</span>
                  <span className="num muted">{st?.estimate != null ? signed(st.estimate, digitsFor(st.estimate)) : ""}</span>
                </button>
              );
            })}
          </div>
        </section>
        <section>
          <h2>Variable</h2>
          <div className="chips" role="group" aria-label="Variable NASA">
            {variables.data?.map((v) => (
              <button key={`${v.dataset_id}/${v.variable_id}`} type="button" className="chip"
                aria-pressed={v.variable_id === study.variableId && v.dataset_id === study.datasetId}
                onClick={() => study.set({ datasetId: v.dataset_id, variableId: v.variable_id })}>
                {cleanQuantity(v.physical_quantity)} <small>{SHORT_SOURCE[v.dataset_id] ?? v.dataset_id}</small>
              </button>
            ))}
          </div>
        </section>
        <section>
          <h2>Periodo y escala</h2>
          <div className="years">
            <label>Desde <select value={study.start} onChange={(e) => study.set({ start: Number(e.target.value) })}>
              {range(2001, study.end - 9).map((y) => <option key={y}>{y}</option>)}</select></label>
            <label>hasta <select value={study.end} onChange={(e) => study.set({ end: Number(e.target.value) })}>
              {range(study.start + 9, 2024).map((y) => <option key={y}>{y}</option>)}</select></label>
          </div>
          <div className="seg" role="group" aria-label="Escala temporal">
            <button type="button" aria-pressed={!anomaly} onClick={() => study.set({ view: "annual" })}>Serie anual</button>
            <button type="button" aria-pressed={anomaly} onClick={() => study.set({ view: "anomaly" })}>Anomalía mensual</button>
          </div>
        </section>
        <section>
          <h2>Método de tendencia</h2>
          <div className="seg" role="group" aria-label="Método">
            {(Object.keys(METHOD_LABEL) as Method[]).map((m) => (
              <button key={m} type="button" aria-pressed={study.method === m} onClick={() => study.set({ method: m })}>{METHOD_LABEL[m]}</button>
            ))}
          </div>
          <p className="hint">IC 95 % del mismo estimador y prueba compatible. Los cálculos los hace la API, igual que desde Python.</p>
        </section>
        {hasCase && (
          <section>
            <h2>Contexto local</h2>
            <label className="check">
              <input type="checkbox" checked={study.context} onChange={(e) => study.set({ context: e.target.checked })} />
              Eventos SINPAD y episodios El Niño Costero (caso Trujillo)
            </label>
            <p className="hint">Registros oficiales de emergencias y contexto ENFEN. Coincidencia temporal no es causa.</p>
          </section>
        )}
      </aside>

      <main className="main">
        {main.isPending && variable && <p className="state" role="status">Calculando con datos NASA en Earth Engine…</p>}
        {main.error && <ErrorPanel error={main.error} />}
        {main.data && (
          <Verdict run={main.data} geo={selectedGeo} quantity={cleanQuantity(variable?.physical_quantity ?? "")}
            anomaly={anomaly} start={study.start} end={study.end} />
        )}

        {main.data && (
          <section className="panel chart-wrap" aria-label="Serie temporal">
            <div className="panel-head">
              <h2>Serie y tendencia</h2>
              <div className="toolbar" role="group" aria-label="Exportar">
                {study.selected !== study.focus && (
                  <button type="button" className="btn" onClick={() => study.set({ selected: study.focus })}>Volver a {focus.data?.name}</button>
                )}
                <ExportMenu run={main.data} unit={unit} chartRef={chartRef}
                  caption={{
                    title: `${cleanQuantity(variable?.physical_quantity ?? "")}, ${selectedGeo?.name ?? ""} (${study.start}–${study.end}${anomaly ? ", anomalía mensual" : ""})`,
                    subtitle: `${dataset?.title ?? ""} · ${main.data.statistics.estimator === "ols" ? "OLS-HAC" : "Theil–Sen"} ${signed(main.data.statistics.estimate, digitsFor(main.data.statistics.estimate))} ${unitPerDecade(main.data.statistics.estimate_unit)} · run_id ${main.data.run_id}`,
                  }} />
              </div>
            </div>
            <TrendChart run={main.data} unit={unit} anomaly={anomaly} theme={theme} onReady={(c) => { chartRef.current = c; }}
              events={showCase ? caseEvents.data?.items : undefined} episodes={showCase ? caseEnfen.data?.episodes : undefined} />
            <p className="legend-line">
              <span className="lg series-k" />{anomaly ? "anomalía mensual" : "valor anual"}
              <span className="lg trend-k" />tendencia {main.data.statistics.estimator === "ols" ? "OLS" : "Theil–Sen"}
              <span className="lg fan-k" />pendientes dentro del IC {Math.round(main.data.statistics.confidence_level * 100)} % (no es banda de predicción)
            </p>
          </section>
        )}

        <div className="lower">
          <section className="panel" aria-label="Mapa de pendientes">
            <h2>¿Dónde cambia? Pendiente por unidad</h2>
            {features.data && (
              <TerritoryMap key={theme} fc={features.data} results={results} selected={study.selected} pixelKm2={pixelKm2}
                onSelect={(id) => study.set({ selected: id, view: "annual" })} />
            )}
            {!mapEnabled && units.length > 0 && main.isSuccess && (
              <p className="hint">
                Calcular el mapa requiere {units.length} análisis ({dataset?.native_granularity === "month" ? "ligeros" : "posiblemente pesados"}).{" "}
                <button type="button" className="btn" onClick={() => setMapRequested(mapKey)}>Calcular pendientes por unidad</button>
              </p>
            )}
            {mapEnabled && mapDone < units.length && !unitFamily.error && <p className="hint" role="status">Calculando {units.length} unidades en una sola consulta…</p>}
            {unitFamily.error && <p className="hint" role="alert">{unitFamily.error.problem.detail}</p>}
            <MapLegend pixelKm2={pixelKm2} theme={theme} />
          </section>
          <section className="panel" aria-label="Calidad y procedencia">
            <h2>Calidad del resultado</h2>
            {main.data && <Quality run={main.data} geo={selectedGeo} pixelKm2={pixelKm2} />}
            {dataset && <Provenance dataset={dataset} attribution={features.data?.attribution} />}
          </section>
        </div>
        {showCase && caseEvents.data && (
          <CaseEventsPanel data={caseEvents.data} enfen={caseEnfen.data} place={selectedGeo?.name ?? "el territorio"} />
        )}
        {showCase && caseEvents.error && <p className="state" role="alert">{(caseEvents.error as ApiError).problem.detail}</p>}
        {main.data && <SeasonalPanel runId={main.data.run_id} theme={theme} place={selectedGeo?.name ?? "el territorio"} />}
      </main>
    </div>
  );
}

function ExportMenu({ run, unit, chartRef, caption }:
  { run: Run; unit: string; chartRef: React.RefObject<import("echarts").ECharts | null>; caption: { title: string; subtitle: string } }) {
  const chart = () => chartRef.current;
  return (
    <>
      <button type="button" className="btn" onClick={() => exportCsv(run, unit)}>CSV</button>
      <button type="button" className="btn" onClick={() => exportJson(run)}>JSON</button>
      <button type="button" className="btn" onClick={() => { const c = chart(); if (c) exportSvg(c, run, caption); }}>SVG</button>
      <button type="button" className="btn" onClick={() => { const c = chart(); if (c) void exportPng(c, run, caption, cssVar("--paper")); }}>PNG</button>
    </>
  );
}

function range(a: number, b: number) { return Array.from({ length: Math.max(0, b - a + 1) }, (_, i) => a + i); }

function TerritorySearch({ onPick }: { onPick: (g: Geography) => void }) {
  const [q, setQ] = useState("");
  const search = useQuery({ queryKey: ["search", q], queryFn: () => api.searchGeographies(q), enabled: q.trim().length >= 2 });
  return (
    <div className="search-wrap">
      <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar distrito, provincia o UBIGEO" aria-label="Buscar territorio en Perú" />
      {q.trim().length >= 2 && search.data && (
        <ul className="results" role="listbox" aria-label="Resultados">
          {search.data.items.length === 0 && <li className="muted">Sin resultados en las fronteras oficiales.</li>}
          {search.data.items.map((g) => (
            <li key={g.geo_id}>
              <button type="button" className="terr" onClick={() => { onPick(g); setQ(""); }}>
                <span>{g.name} <small className="muted">{g.path?.slice(1).join(" › ")}</small></span>
                <span className="muted">{g.admin_level === "ADM3" ? "distrito" : g.admin_level === "ADM2" ? "provincia" : "departamento"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Verdict({ run, geo, quantity, anomaly, start, end }:
  { run: Run; geo?: Geography; quantity: string; anomaly: boolean; start: number; end: number }) {
  const st = run.statistics, v = verdictOf(st);
  const subject = anomaly ? `Las anomalías mensuales de ${quantity}` : `La serie anual de ${quantity}`;
  const phrase = anomaly ? v.phrase.replace(/^muestra/, "muestran").replace(/^no muestra/, "no muestran").replace(/^tiene/, "tienen") : v.phrase;
  const d = digitsFor(st.estimate);
  return (
    <section className="verdict" aria-live="polite">
      <span className="tag" data-kind={v.kind}>{v.label}</span>
      <h1>{subject} en {where(geo)} {phrase} entre {start} y {end}.</h1>
      {st.estimate != null && (
        <dl className="facts">
          <div><dt>Cambio estimado</dt><dd className="num">{signed(st.estimate, d)} {unitPerDecade(st.estimate_unit)}</dd></div>
          <div><dt>IC {Math.round(st.confidence_level * 100)} %</dt><dd className="num">{signed(st.ci_lower, d)} a {signed(st.ci_upper, d)}</dd></div>
          <div><dt>Prueba</dt><dd className="num">{TEST_LABEL[st.test_method] ?? st.test_method}, p = {fmtP(st.p_value)}</dd></div>
          <div><dt>{anomaly ? "Meses con dato" : "Años con dato"}</dt><dd className="num">{st.n_observations} de {st.n_observations + st.n_missing}</dd></div>
        </dl>
      )}
      <p className="method-note">
        {st.estimator === "ols" ? "Regresión OLS con errores robustos HAC (Newey–West)" : "Pendiente de Theil–Sen"}.
        El intervalo es una propiedad del procedimiento bajo sus supuestos, no la probabilidad de que el valor real esté dentro.
        Describe el periodo elegido: no es un pronóstico.
      </p>
    </section>
  );
}

function Quality({ run, geo, pixelKm2 }: { run: Run; geo?: Geography; pixelKm2: number }) {
  const [copied, setCopied] = useState(false);
  const warns = [...run.statistics.warnings];
  if (geo?.area_km2 != null && geo.area_km2 < pixelKm2 && !warns.some((w) => w.includes("píxel"))) {
    warns.unshift(`El territorio (${fmt(geo.area_km2, 0)} km²) es menor que un píxel nativo (~${fmt(pixelKm2, 0)} km²).`);
  }
  return (
    <>
      <ul className="warn">{warns.length ? warns.map((w) => <li key={w}>{w}</li>) : <li>Sin advertencias de calidad.</li>}</ul>
      <p className="runrow">
        Cobertura {fmt(run.statistics.coverage_fraction * 100, 0)} % · {run.cache_hit ? "resultado en caché" : "calculado ahora"}
      </p>
      <p className="runrow">Reproducible por API o SDK con <code>{run.run_id}</code>
        <button type="button" className="btn" onClick={async () => {
          try { await navigator.clipboard.writeText(run.run_id); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* sin portapapeles */ }
        }}>{copied ? "Copiado" : "Copiar run_id"}</button>
      </p>
    </>
  );
}

function Provenance({ dataset, attribution }: { dataset: Dataset; attribution?: string }) {
  return (
    <dl className="prov">
      <div><dt>Fuente</dt><dd>{dataset.title} (<code>{dataset.ee_collection_id}</code>), vía Google Earth Engine</dd></div>
      <div><dt>Resolución</dt><dd>{dataset.nominal_resolution}; media ponderada por área</dd></div>
      {attribution && <div><dt>Fronteras</dt><dd>{attribution}</dd></div>}
      {dataset.notes.length > 0 && <div><dt>Límites del dato</dt><dd>{dataset.notes.join(" ")}</dd></div>}
    </dl>
  );
}

function MapLegend({ pixelKm2, theme }: { pixelKm2: number; theme: string }) {
  const [stops, setStops] = useState<string[]>([]);
  useEffect(() => setStops(divergentStops()), [theme]);
  return (
    <div className="map-legend">
      <div className="ramp">{stops.map((c) => <span key={c} style={{ background: c }} />)}</div>
      <div className="ramp-labels"><span>disminuye</span><span>0</span><span>aumenta</span></div>
      <p><span className="key hatch-k" />Rayado: sin evidencia de cambio (q ≥ 0,05 tras corregir por las unidades comparadas, o el IC incluye 0)</p>
      <p><span className="key sub-k" />Borde discontinuo: unidad menor que un píxel del producto (~{fmt(pixelKm2, 0)} km²)</p>
    </div>
  );
}

function ErrorPanel({ error }: { error: ApiError }) {
  const p = error.problem;
  return (
    <section className="panel error" role="alert">
      <h2>{p.title === "token_required" ? "Este análisis requiere un token de API"
        : p.title === "insufficient_coverage" ? "No hay datos suficientes para este territorio"
        : p.title === "api_unreachable" ? "No hay conexión con la API" : "No se pudo completar el análisis"}</h2>
      <p>{p.detail}</p>
      {p.cost && <p className="hint">Coste estimado: {p.cost.source_images.toLocaleString("es-PE")} imágenes fuente, ~{Math.round(p.cost.estimated_seconds)} s.</p>}
    </section>
  );
}
