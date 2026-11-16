"use client";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cssVar } from "@/lib/colors";
import { exportCsv, exportJson, exportPng, exportSvg } from "@/lib/export";
import { divergentStops } from "@/lib/colors";
import { digitsFor, fmt, fmtP, signed, testLabel, unitPerDecade, verdictOf } from "@/lib/format";
import { apiText, locale, tr, useT } from "@/lib/i18n";
import { simpleName, simpleNameLower, simpleUnit } from "@/lib/variables";
import { buildSpec, methodLabel, METHODS_ORDER, readStudyFromUrl, studyToUrl, useStudy, type Method } from "@/lib/study";
import type { CompareResult, Dataset, Geography, Run, Variable } from "@/lib/types";
import { useResolvedTheme } from "@/lib/theme";
import { TerritoryMap, type UnitResult } from "./TerritoryMap";
import { SeasonalPanel } from "./SeasonalPanel";
import { TrendChart } from "./TrendChart";

const ARTICLE: Record<string, string> = { ADM0: "", ADM1: "el departamento de ", ADM2: "la provincia de ", ADM3: "el distrito de " };
const where = (g?: Pick<Geography, "admin_level" | "name">) =>
  g ? tr(`${ARTICLE[g.admin_level] ?? ""}${g.name}`, g.name) : tr("el territorio", "the territory");
const MAP_AUTO_MAX_UNITS = 12; // calcular el mapa automáticamente solo para productos mensuales y pocas unidades

export function Explorer() {
  const t = useT();
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
  }, [study.focus, study.selected, study.datasetId, study.variableId, study.view, study.method, study.start, study.end,
    study.ic, study.prueba, study.conf]);

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

  const selectedGeo: Geography | undefined =
    study.selected === study.focus ? focus.data : units.find((u) => u.geo_id === study.selected);
  const unit = simpleUnit(variable?.unit_display ?? "");

  return (
    <div className="layout" id="contenido">
      <aside className="rail" aria-label={t("Configuración del análisis", "Analysis settings")}>
        <section>
          <h2>{t("Territorio", "Territory")}</h2>
          <p className="crumb">{focus.data ? [...(focus.data.path ?? []), focus.data.name].join(" › ") : t("Cargando…", "Loading…")}</p>
          <TerritorySearch iso3={focus.data?.iso3} onPick={(g) => study.set({ focus: g.geo_id, selected: g.geo_id })} />
          <div className="list" role="group" aria-label={t("Elegir territorio", "Choose territory")}>
            <button type="button" className="terr" aria-pressed={study.selected === study.focus}
              onClick={() => study.set({ selected: study.focus })}>
              <span>{focus.data ? t(`${focus.data.name} completo`, `All of ${focus.data.name}`) : t("Territorio completo", "Whole territory")}</span>
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
          <h2>{t("Variable", "Variable")}</h2>
          <div className="chips" role="group" aria-label={t("Variable NASA", "NASA variable")}>
            {variables.data?.map((v) => (
              <button key={`${v.dataset_id}/${v.variable_id}`} type="button" className="chip"
                aria-pressed={v.variable_id === study.variableId && v.dataset_id === study.datasetId}
                onClick={() => study.set({ datasetId: v.dataset_id, variableId: v.variable_id })}>
                {simpleName(v.dataset_id, v.variable_id, v.physical_quantity)}
              </button>
            ))}
          </div>
        </section>
        <section>
          <h2>{t("Periodo y escala", "Period and scale")}</h2>
          <div className="years">
            <label>{t("Desde", "From")} <select value={study.start} onChange={(e) => study.set({ start: Number(e.target.value) })}>
              {range(2001, study.end - 9).map((y) => <option key={y}>{y}</option>)}</select></label>
            <label>{t("hasta", "to")} <select value={study.end} onChange={(e) => study.set({ end: Number(e.target.value) })}>
              {range(study.start + 9, 2024).map((y) => <option key={y}>{y}</option>)}</select></label>
          </div>
          <div className="seg" role="group" aria-label={t("Escala temporal", "Time scale")}>
            <button type="button" aria-pressed={!anomaly} onClick={() => study.set({ view: "annual" })}>{t("Serie anual", "Annual series")}</button>
            <button type="button" aria-pressed={anomaly} onClick={() => study.set({ view: "anomaly" })}>{t("Anomalía mensual", "Monthly anomaly")}</button>
          </div>
        </section>
        <section>
          <h2>{t("Método de tendencia", "Trend method")}</h2>
          <div className="seg" role="group" aria-label={t("Método", "Method")}>
            {METHODS_ORDER.map((m: Method) => (
              <button key={m} type="button" aria-pressed={study.method === m && !study.ic && !study.prueba}
                onClick={() => study.set({ method: m, ic: undefined, prueba: undefined })}>{methodLabel(m)}</button>
            ))}
          </div>
          <p className="hint">{t("IC", "CI")} {Math.round((study.conf ?? 0.95) * 100)} % {t("del mismo estimador y prueba compatible", "from the same estimator and a compatible test")}
            {(study.ic || study.prueba) && t(" (variante elegida en el panel)", " (variant chosen in the dashboard)")}. {t("Los cálculos los hace la API, igual que desde Python.", "The API does the computing, exactly as from Python.")}</p>
        </section>
      </aside>

      <main className="main">
        {main.isPending && variable && <p className="state" role="status">{t("Calculando con datos NASA en Earth Engine…", "Computing with NASA data in Earth Engine…")}</p>}
        {main.error && <ErrorPanel error={main.error} />}
        {main.data && (
          <Verdict run={main.data} geo={selectedGeo} quantity={simpleNameLower(study.datasetId, study.variableId, variable?.physical_quantity ?? "")}
            anomaly={anomaly} start={study.start} end={study.end} />
        )}

        {main.data && (
          <section className="panel chart-wrap" aria-label={t("Serie temporal", "Time series")}>
            <div className="panel-head">
              <h2>{t("Serie y tendencia", "Series and trend")}</h2>
              <div className="toolbar" role="group" aria-label={t("Exportar", "Export")}>
                {study.selected !== study.focus && (
                  <button type="button" className="btn" onClick={() => study.set({ selected: study.focus })}>{t("Volver a", "Back to")} {focus.data?.name}</button>
                )}
                <ExportMenu run={main.data} unit={unit} chartRef={chartRef}
                  caption={{
                    title: `${simpleName(study.datasetId, study.variableId, variable?.physical_quantity ?? "")}, ${selectedGeo?.name ?? ""} (${study.start}–${study.end}${anomaly ? t(", anomalía mensual", ", monthly anomaly") : ""})`,
                    subtitle: `${apiText(dataset?.title)} · ${main.data.statistics.estimator === "ols" ? "OLS" : "Theil–Sen"} ${signed(main.data.statistics.estimate, digitsFor(main.data.statistics.estimate))} ${unitPerDecade(main.data.statistics.estimate_unit)} · run_id ${main.data.run_id}`,
                  }} />
              </div>
            </div>
            <TrendChart run={main.data} unit={unit} anomaly={anomaly} theme={theme} onReady={(c) => { chartRef.current = c; }} />
            <p className="legend-line">
              <span className="lg series-k" />{anomaly ? t("anomalía mensual", "monthly anomaly") : t("valor anual", "annual value")}
              <span className="lg trend-k" />{t("tendencia", "trend")} {main.data.statistics.estimator === "ols" ? "OLS" : "Theil–Sen"}
              <span className="lg fan-k" />{t("pendientes dentro del IC", "slopes within the CI")} {Math.round(main.data.statistics.confidence_level * 100)} % {t("(no es banda de predicción)", "(not a prediction band)")}
            </p>
          </section>
        )}

        <div className="lower">
          <section className="panel" aria-label={t("Mapa de pendientes", "Slope map")}>
            <h2>{t("¿Dónde cambia? Pendiente por unidad", "Where does it change? Slope by unit")}</h2>
            {features.data && (
              <TerritoryMap key={theme} fc={features.data} results={results} selected={study.selected} pixelKm2={pixelKm2}
                onSelect={(id) => study.set({ selected: id, view: "annual" })} />
            )}
            {!mapEnabled && units.length > 0 && main.isSuccess && (
              <p className="hint">
                {t(`Calcular el mapa requiere ${units.length} análisis`, `Computing the map needs ${units.length} analyses`)} ({dataset?.native_granularity === "month" ? t("ligeros", "light") : t("posiblemente pesados", "possibly heavy")}).{" "}
                <button type="button" className="btn" onClick={() => setMapRequested(mapKey)}>{t("Calcular pendientes por unidad", "Compute slopes by unit")}</button>
              </p>
            )}
            {mapEnabled && mapDone < units.length && !unitFamily.error && <p className="hint" role="status">{t(`Calculando ${units.length} unidades en una sola consulta…`, `Computing ${units.length} units in a single request…`)}</p>}
            {unitFamily.error && <p className="hint" role="alert">{apiText(unitFamily.error.problem.detail)}</p>}
            <MapLegend pixelKm2={pixelKm2} theme={theme} />
          </section>
          <section className="panel" aria-label={t("Calidad y procedencia", "Quality and provenance")}>
            <h2>{t("Calidad del resultado", "Result quality")}</h2>
            {main.data && <Quality run={main.data} geo={selectedGeo} pixelKm2={pixelKm2} />}
            {dataset && <Provenance dataset={dataset} attribution={features.data?.attribution} />}
          </section>
        </div>
        {main.data && <SeasonalPanel runId={main.data.run_id} theme={theme} place={selectedGeo?.name ?? t("el territorio", "the territory")} />}
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

function TerritorySearch({ onPick, iso3 }: { onPick: (g: Geography) => void; iso3?: string }) {
  const t = useT();
  const [q, setQ] = useState("");
  const term = q.trim();
  const country = iso3 && iso3.length === 3 ? iso3 : null;
  const countries = useQuery({ queryKey: ["search-countries", term], queryFn: () => api.searchGeographies(term, null), enabled: term.length >= 2 });
  const inside = useQuery({ queryKey: ["search", term, country], queryFn: () => api.searchGeographies(term, country), enabled: term.length >= 2 && !!country });
  const items = [...(inside.data?.items ?? []), ...(countries.data?.items ?? [])];
  return (
    <div className="search-wrap">
      <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder={t("Buscar país o región", "Search country or region")} aria-label={t("Buscar territorio", "Search territory")} />
      {term.length >= 2 && (
        <ul className="results" role="listbox" aria-label={t("Resultados", "Results")}>
          {items.length === 0 && !countries.isPending && <li className="muted">{t("Sin resultados.", "No results.")}</li>}
          {items.map((g) => (
            <li key={g.geo_id}>
              <button type="button" className="terr" onClick={() => { onPick(g); setQ(""); }}>
                <span>{g.name} <small className="muted">{g.path?.slice(1).join(" › ")}</small></span>
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
  const t = useT();
  const st = run.statistics, v = verdictOf(st);
  const subject = anomaly ? t(`Las anomalías mensuales de ${quantity}`, `Monthly anomalies of ${quantity}`)
    : t(`La serie anual de ${quantity}`, `The annual series of ${quantity}`);
  const phrase = !anomaly ? v.phrase
    : t(v.phrase.replace(/^muestra/, "muestran").replace(/^no muestra/, "no muestran").replace(/^tiene/, "tienen"),
      v.phrase.replace(/^shows/, "show").replace(/^does not have/, "do not have"));
  const d = digitsFor(st.estimate);
  return (
    <section className="verdict" aria-live="polite">
      <span className="tag" data-kind={v.kind}>{v.label}</span>
      <h1>{subject} {t("en", "in")} {where(geo)} {phrase} {t("entre", "between")} {start} {t("y", "and")} {end}.</h1>
      {st.estimate != null && (
        <dl className="facts">
          <div><dt>{t("Cambio estimado", "Estimated change")}</dt><dd className="num">{signed(st.estimate, d)} {unitPerDecade(st.estimate_unit)}</dd></div>
          <div><dt>{t("IC", "CI")} {Math.round(st.confidence_level * 100)} %</dt><dd className="num">{signed(st.ci_lower, d)} {t("a", "to")} {signed(st.ci_upper, d)}</dd></div>
          <div><dt>{t("Prueba", "Test")}</dt><dd className="num">{testLabel(st.test_method)}, p = {fmtP(st.p_value)}</dd></div>
          <div><dt>{anomaly ? t("Meses con dato", "Months with data") : t("Años con dato", "Years with data")}</dt><dd className="num">{st.n_observations} {t("de", "of")} {st.n_observations + st.n_missing}</dd></div>
        </dl>
      )}
      <p className="method-note">
        {st.estimator === "ols" ? t("Regresión OLS", "OLS regression") : t("Pendiente de Theil–Sen", "Theil–Sen slope")}
        {st.ci_method === "ar1_effective_n" || st.ci_method === "theil_sen_ar1"
          ? t("; el intervalo y la prueba usan el tamaño muestral efectivo, porque años consecutivos se parecen entre sí (autocorrelación)",
            "; the interval and the test use the effective sample size, because consecutive years resemble each other (autocorrelation)")
          : st.ci_method === "moving_block_bootstrap" ? t("; intervalo por bootstrap de bloques de años consecutivos", "; interval by bootstrap of blocks of consecutive years")
          : st.ci_method === "hac_newey_west" ? t(" con errores robustos HAC (Newey–West)", " with robust HAC errors (Newey–West)") : ""}.
        {" "}{t("El intervalo es una propiedad del procedimiento bajo sus supuestos, no la probabilidad de que el valor real esté dentro.",
          "The interval is a property of the procedure under its assumptions, not the probability that the true value lies inside it.")}
        {" "}{t("Describe el periodo elegido: no es un pronóstico.", "It describes the chosen period: it is not a forecast.")}
      </p>
    </section>
  );
}

function Quality({ run, geo, pixelKm2 }: { run: Run; geo?: Geography; pixelKm2: number }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const warns = run.statistics.warnings.map(apiText);
  if (geo?.area_km2 != null && geo.area_km2 < pixelKm2 && !run.statistics.warnings.some((w) => w.includes("píxel"))) {
    warns.unshift(t(`El territorio (${fmt(geo.area_km2, 0)} km²) es menor que un píxel nativo (~${fmt(pixelKm2, 0)} km²).`,
      `The territory (${fmt(geo.area_km2, 0)} km²) is smaller than a native pixel (~${fmt(pixelKm2, 0)} km²).`));
  }
  return (
    <>
      <ul className="warn">{warns.length ? warns.map((w) => <li key={w}>{w}</li>) : <li>{t("Sin advertencias de calidad.", "No quality warnings.")}</li>}</ul>
      <p className="runrow">
        {t("Cobertura", "Coverage")} {fmt(run.statistics.coverage_fraction * 100, 0)} % · {run.cache_hit ? t("resultado en caché", "cached result") : t("calculado ahora", "computed now")}
      </p>
      <p className="runrow">{t("Reproducible por API o SDK con", "Reproducible via API or SDK with")} <code>{run.run_id}</code>
        <button type="button" className="btn" onClick={async () => {
          try { await navigator.clipboard.writeText(run.run_id); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* sin portapapeles */ }
        }}>{copied ? t("Copiado", "Copied") : t("Copiar run_id", "Copy run_id")}</button>
      </p>
    </>
  );
}

export function Provenance({ dataset, attribution }: { dataset: Dataset; attribution?: string }) {
  const t = useT();
  return (
    <dl className="prov">
      <div><dt>{t("Fuente", "Source")}</dt><dd>{apiText(dataset.title)} (<code>{dataset.ee_collection_id}</code>), {t("vía", "via")} Google Earth Engine</dd></div>
      <div><dt>{t("Resolución", "Resolution")}</dt><dd>{apiText(dataset.nominal_resolution)}; {t("media ponderada por área", "area-weighted mean")}</dd></div>
      {attribution && <div><dt>{t("Fronteras", "Boundaries")}</dt><dd>{apiText(attribution)}</dd></div>}
      {dataset.notes.length > 0 && <div><dt>{t("Límites del dato", "Data limitations")}</dt><dd>{dataset.notes.map(apiText).join(" ")}</dd></div>}
    </dl>
  );
}

function MapLegend({ pixelKm2, theme }: { pixelKm2: number; theme: string }) {
  const t = useT();
  const [stops, setStops] = useState<string[]>([]);
  useEffect(() => setStops(divergentStops()), [theme]);
  return (
    <div className="map-legend">
      <div className="ramp">{stops.map((c) => <span key={c} style={{ background: c }} />)}</div>
      <div className="ramp-labels"><span>{t("disminuye", "decreases")}</span><span>0</span><span>{t("aumenta", "increases")}</span></div>
      <p><span className="key hatch-k" />{t("Rayado: sin evidencia de cambio (q ≥ 0,05 tras corregir por las unidades comparadas, o el IC incluye 0)", "Hatched: no evidence of change (q ≥ 0.05 after correcting for the units compared, or the CI includes 0)")}</p>
      <p><span className="key sub-k" />{t("Borde discontinuo: unidad menor que un píxel del producto", "Dashed outline: unit smaller than one product pixel")} (~{fmt(pixelKm2, 0)} km²)</p>
    </div>
  );
}

export function ErrorPanel({ error }: { error: ApiError }) {
  const t = useT();
  const p = error.problem;
  return (
    <section className="panel error" role="alert">
      <h2>{p.title === "token_required" ? t("Este análisis requiere un token de API", "This analysis requires an API token")
        : p.title === "insufficient_coverage" ? t("No hay datos suficientes para este territorio", "Not enough data for this territory")
        : p.title === "api_unreachable" ? t("No hay conexión con la API", "No connection to the API")
        : t("No se pudo completar el análisis", "The analysis could not be completed")}</h2>
      <p>{apiText(p.detail)}</p>
      {p.cost && <p className="hint">{t("Coste estimado", "Estimated cost")}: {p.cost.source_images.toLocaleString(locale())} {t("imágenes fuente", "source images")}, ~{Math.round(p.cost.estimated_seconds)} s.</p>}
    </section>
  );
}
