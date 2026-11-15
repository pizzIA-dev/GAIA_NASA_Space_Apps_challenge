"use client";
// Atlas (plan §4.1, §8 «mapa de tendencias», MAP-01): un mapa por variable para todas las subunidades de un territorio.
// Cada mapa es una familia BH-FDR propia; los números vienen de POST /atlas (misma especificación que Explorar).
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { divergentStops } from "@/lib/colors";
import { digitsFor, fmt, fmtP, signed, unitPerDecade, verdictOf } from "@/lib/format";
import { useResolvedTheme } from "@/lib/theme";
import type { AtlasResult, FeatureCollection } from "@/lib/types";
import { TerritoryPicker } from "../dashboard/Dashboard";
import { TerritoryMap, type UnitResult } from "../explorer/TerritoryMap";

const DEFAULT_PARENT = "pe-ign2020:15"; // Lima: ejemplo inicial, cambiable
const VARIABLES = [
  { dataset_id: "nasa-gpm-imerg-monthly-v07", variable_id: "precipitation_mm_month", label: "Lluvia" },
  { dataset_id: "nasa-merra2-slv", variable_id: "air_temperature_2m_c", label: "Temperatura del aire" },
  { dataset_id: "nasa-gldas-noah-v21-3h", variable_id: "soil_moisture_0_10cm_kgm2", label: "Humedad del suelo" },
  { dataset_id: "nasa-modis-mod13q1-061", variable_id: "ndvi", label: "Vegetación (verdor)" },
];
const START = 2003, END = 2024;

export function Atlas() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const parentId = params.get("territorio") || DEFAULT_PARENT;
  const parentGeo = useQuery({ queryKey: ["geo", parentId], queryFn: () => api.geography(parentId) });
  const parent = { id: parentId, label: parentGeo.data?.name ?? "…" };
  const features = useQuery({ queryKey: ["features", parent.id], queryFn: () => api.features(parent.id) });
  return (
    <main className="atlas" id="contenido">
      <header className="atlas-head">
        <h1>Atlas · {parent.label}</h1>
        <p className="lead">Cómo cambia cada variable en las subdivisiones del territorio ({START}–{END}). El rayado indica que no hay evidencia de cambio.</p>
        <div className="atlas-picker">
          <TerritoryPicker geo={parentGeo.data}
            onPick={(id) => router.replace(id === DEFAULT_PARENT ? pathname : `${pathname}?territorio=${encodeURIComponent(id)}`, { scroll: false })} />
        </div>
      </header>
      <div className="atlas-grid">
        {VARIABLES.map((v) => (
          <AtlasMap key={`${parent.id}-${v.variable_id}`} parentId={parent.id} v={v} fc={features.data} />
        ))}
      </div>
    </main>
  );
}

function AtlasMap({ parentId, v, fc }: { parentId: string; v: (typeof VARIABLES)[number]; fc?: FeatureCollection }) {
  const theme = useResolvedTheme();
  const router = useRouter();
  const body = { parent_geo_id: parentId, dataset_id: v.dataset_id, variable_id: v.variable_id, start_year: START, end_year: END };
  const q = useQuery<AtlasResult, ApiError>({ queryKey: ["atlas", body], queryFn: () => api.atlas(body), retry: false, staleTime: Infinity });
  const r = q.data;
  const results: Record<string, UnitResult> = {};
  r?.items.forEach((it) => { results[it.geo_id] = { geoId: it.geo_id, st: it.statistics, error: it.error?.code }; });
  const ok = r?.items.filter((it) => it.statistics) ?? [];
  const kinds = ok.map((it) => verdictOf(it.statistics!).kind);
  const up = kinds.filter((k) => k === "up").length, down = kinds.filter((k) => k === "down").length;
  const failedItems = r?.items.filter((it) => it.status === "failed") ?? [];
  const noPixels = failedItems.filter((it) => it.error?.code === "insufficient_coverage").length;
  const notComputed = failedItems.length - noPixels;
  const perDecade = ok[0] ? unitPerDecade(ok[0].statistics!.estimate_unit) : "";
  const explorar = (geoId: string) =>
    `/explorar?focus=${encodeURIComponent(parentId)}&selected=${encodeURIComponent(geoId)}&datasetId=${v.dataset_id}&variableId=${v.variable_id}`;
  return (
    <section className="panel atlas-card" aria-labelledby={`h-${v.variable_id}`} data-variable={v.variable_id}>
      <h2 id={`h-${v.variable_id}`}>{v.label}</h2>
      {q.isPending && <p className="state" role="status">Calculando una tendencia por unidad…</p>}
      {q.error && (
        <div className="state" role="alert">
          {q.error.problem.title === "token_required" && <p><b>Sin calcular todavía: requiere un token de API.</b></p>}
          <p>{q.error.problem.detail}</p>
          {q.error.problem.cost && <p className="hint">Coste estimado: {q.error.problem.cost.source_images.toLocaleString("es-PE")} imágenes fuente por unidad.</p>}
        </div>
      )}
      {r && (
        <>
          <p className="atlas-summary">
            <b>{up}</b> con evidencia de aumento, <b>{down}</b> de disminución y <b>{ok.length - up - down}</b> sin evidencia
            de {r.n_units} {r.n_units === 1 ? "unidad" : "unidades"}{noPixels > 0 ? `; ${noPixels} sin píxeles válidos` : ""}
            {notComputed > 0 ? `; ${notComputed} sin calcular (fuente no disponible ahora)` : ""}.
          </p>
          {fc && (
            <TerritoryMap key={`${theme}-${parentId}`} fc={fc} results={results} selected="" pixelKm2={r.pixel_km2}
              onSelect={(id) => router.push(explorar(id))} />
          )}
          <AtlasLegend max={r.scale.max_abs_estimate} unit={perDecade} theme={theme} pixelKm2={r.pixel_km2} />
          <details className="atlas-table">
            <summary>Tabla de las {r.n_units} unidades</summary>
            <table className="table">
              <caption className="sr-only">Pendiente por unidad con IC 95 % y q-valor</caption>
              <thead><tr><th scope="col">Unidad</th><th scope="col">{perDecade || "pendiente"}</th><th scope="col">IC 95 %</th><th scope="col">q</th><th scope="col">Veredicto</th></tr></thead>
              <tbody>
                {[...r.items].sort((a, b) => (b.statistics?.estimate ?? -Infinity) - (a.statistics?.estimate ?? -Infinity)).map((it) => {
                  const s = it.statistics, vd = s ? verdictOf(s) : null, d = digitsFor(s?.estimate);
                  return (
                    <tr key={it.geo_id}>
                      <th scope="row"><Link href={explorar(it.geo_id)}>{it.name}</Link></th>
                      <td className="num">{s ? signed(s.estimate, d) : "sin dato"}</td>
                      <td className="num">{s ? `${signed(s.ci_lower, d)} a ${signed(s.ci_upper, d)}` : "—"}</td>
                      <td className="num">{s ? fmtP(s.q_value) : "—"}</td>
                      <td>{vd ? <span className="tag" data-kind={vd.kind}>{vd.label}</span> : <span className="muted">{it.error?.code === "insufficient_coverage" ? "sin píxeles válidos" : "sin calcular"}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        </>
      )}
    </section>
  );
}

function AtlasLegend({ max, unit, theme, pixelKm2 }: { max: number | null; unit: string; theme: string; pixelKm2: number }) {
  const [stops, setStops] = useState<string[]>([]);
  useEffect(() => setStops(divergentStops()), [theme]);
  const d = digitsFor(max);
  return (
    <div className="map-legend">
      <div className="ramp" aria-hidden="true">{stops.map((c) => <span key={c} style={{ background: c }} />)}</div>
      <div className="ramp-labels num"><span>{max != null ? signed(-max, d) : ""}</span><span>0</span><span>{max != null ? signed(max, d) : ""}</span></div>
      <p>{unit}. Escala propia de este mapa (centrada en 0): compara unidades, no variables.</p>
      <p><span className="key hatch-k" />Rayado: sin evidencia de cambio (q ≥ 0,05 o IC que incluye 0) · <span className="key sub-k" />menor que un píxel (~{fmt(pixelKm2, 0)} km²)</p>
    </div>
  );
}
