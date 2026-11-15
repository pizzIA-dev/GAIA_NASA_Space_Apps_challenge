"use client";
// Estudio (plan §4.3, §5.3): lienzo de paneles. Arrastrar una variable a un panel lo reemplaza; al hueco final, crea uno.
// Alternativa completa por teclado: botones «Añadir panel», «Subir/Bajar», «Quitar» y sensor de teclado de dnd-kit.
import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { digitsFor, fmt, fmtP, signed, verdictOf } from "@/lib/format";
import { buildSpec, METHOD_LABEL, type Method } from "@/lib/study";
import { LINE_TYPES, MAX_PANELS, MAX_TERRITORIES, splitKey, studioFromUrl, studioToUrl, useStudio } from "@/lib/studio";
import { useResolvedTheme } from "@/lib/theme";
import type { CompareResult, Geography, Variable } from "@/lib/types";
import { CompareChart } from "./CompareChart";

const cleanQuantity = (q: string) => q.replace(/\s*\(.*?\)\s*/g, " ").trim();
const keyOf = (v: Variable) => `${v.dataset_id}/${v.variable_id}`;
const SOURCE: Record<string, string> = {
  "nasa-gpm-imerg-monthly-v07": "IMERG", "nasa-gldas-noah-v21-3h": "GLDAS", "nasa-merra2-slv": "MERRA-2",
  "nasa-modis-mod13q1-061": "MODIS", "nasa-modis-aqua-sst-l3smi": "MODIS-Aqua",
};

export function Studio() {
  const st = useStudio();
  const theme = useResolvedTheme();
  const router = useRouter(), pathname = usePathname(), params = useSearchParams();
  const hydrated = useRef(false);
  useEffect(() => {
    if (!hydrated.current) { st.set(studioFromUrl(params.toString())); hydrated.current = true; return; }
    router.replace(`${pathname}${studioToUrl(st)}`, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.panels, st.geos, st.method, st.start, st.end]);

  const variables = useQuery({ queryKey: ["variables"], queryFn: api.variables });
  const byKey = useMemo(() => Object.fromEntries((variables.data ?? []).map((v) => [keyOf(v), v])), [variables.data]);
  const geoInfo = useQuery({
    queryKey: ["geo-names", st.geos],
    queryFn: async () => Promise.all(st.geos.map((g) => api.geography(g))),
  });
  const names: Record<string, string> = Object.fromEntries((geoInfo.data ?? []).map((g) => [g.geo_id, g.name]));

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));
  const [dragging, setDragging] = useState<string | null>(null);
  const onDragStart = (e: DragStartEvent) => setDragging(String(e.active.id));
  const onDragEnd = (e: DragEndEvent) => {
    setDragging(null);
    const key = String(e.active.id), target = e.over?.id;
    if (target == null) return;
    if (target === "nuevo-panel") st.addPanel(key);
    else if (String(target).startsWith("panel-")) st.replacePanel(Number(String(target).slice(6)), key);
  };
  const name = (key: string) => (byKey[key] ? cleanQuantity(byKey[key].physical_quantity) : key);

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}
      accessibility={{
        announcements: {
          onDragStart: ({ active }) => `Variable ${name(String(active.id))} tomada. Usa las flechas para elegir un panel y Espacio para soltar.`,
          onDragOver: ({ over }) => (over ? `Sobre ${over.id === "nuevo-panel" ? "el hueco para un panel nuevo" : `el panel ${Number(String(over.id).slice(6)) + 1}`}.` : "Fuera de los paneles."),
          onDragEnd: ({ over }) => (over ? "Variable colocada." : "Cancelado: la variable no se colocó."),
          onDragCancel: () => "Arrastre cancelado.",
        },
        screenReaderInstructions: { draggable: "Para arrastrar una variable pulsa Espacio, muévete con las flechas y suelta con Espacio. También puedes usar el botón «Añadir panel»." },
      }}>
      <div className="layout" id="contenido">
        <aside className="rail" aria-label="Configuración del estudio">
          <section>
            <h2>Variables</h2>
            <p className="hint">Arrastra una variable a un panel para cambiarla, o al hueco final para añadir otra.</p>
            <div className="palette">
              {variables.data?.map((v) => (
                <VariableChip key={keyOf(v)} id={keyOf(v)} label={cleanQuantity(v.physical_quantity)} source={SOURCE[v.dataset_id] ?? ""}
                  inUse={st.panels.includes(keyOf(v))} canAdd={st.panels.length < MAX_PANELS} onAdd={() => st.addPanel(keyOf(v))} />
              ))}
            </div>
          </section>
          <section>
            <h2>Territorios ({st.geos.length} de {MAX_TERRITORIES})</h2>
            <ul className="geo-list">
              {st.geos.map((g, i) => (
                <li key={g}>
                  <LineKey index={i} />
                  <span>{names[g] ?? g}</span>
                  <button type="button" className="btn small" onClick={() => st.removeGeo(g)} disabled={st.geos.length <= 1}
                    aria-label={`Quitar ${names[g] ?? g}`}>Quitar</button>
                </li>
              ))}
            </ul>
            {st.geos.length < MAX_TERRITORIES && <GeoAdder onAdd={(g) => st.addGeo(g.geo_id)} exclude={st.geos} />}
          </section>
          <section>
            <h2>Periodo y método</h2>
            <div className="years">
              <label>Desde <select value={st.start} onChange={(e) => st.set({ start: Number(e.target.value) })}>
                {range(2001, st.end - 9).map((y) => <option key={y}>{y}</option>)}</select></label>
              <label>hasta <select value={st.end} onChange={(e) => st.set({ end: Number(e.target.value) })}>
                {range(st.start + 9, 2024).map((y) => <option key={y}>{y}</option>)}</select></label>
            </div>
            <div className="seg" role="group" aria-label="Método">
              {(Object.keys(METHOD_LABEL) as Method[]).map((m) => (
                <button key={m} type="button" aria-pressed={st.method === m} onClick={() => st.set({ method: m })}>{METHOD_LABEL[m]}</button>
              ))}
            </div>
            <p className="hint">Mismo método e intervalo para todas las comparaciones. Los q-valores corrigen por pruebas múltiples (BH-FDR) dentro de cada panel, y el veredicto se basa en q.</p>
          </section>
        </aside>

        <main className="main">
          <h1 className="page-title">Estudio comparativo</h1>
          <p className="lead">Compara cómo cambia cada variable en varios territorios, con el mismo periodo y el mismo método. Pasa el cursor sobre un panel para ver la misma fecha en todos.</p>
          {st.panels.map((key, i) => (
            <PanelDrop key={key} index={i}>
              <StudioPanel index={i} total={st.panels.length} variable={byKey[key]} panelKey={key} names={names} theme={theme} />
            </PanelDrop>
          ))}
          {st.panels.length < MAX_PANELS && <NewPanelDrop active={dragging != null} />}
        </main>
      </div>
      <DragOverlay>{dragging ? <span className="chip dragging">{name(dragging)}</span> : null}</DragOverlay>
    </DndContext>
  );
}

function range(a: number, b: number) { return Array.from({ length: Math.max(0, b - a + 1) }, (_, i) => a + i); }

function LineKey({ index }: { index: number }) {
  const t = LINE_TYPES[index % 4];
  const dash = t === "dashed" ? "6 3" : t === "dotted" ? "2 3" : Array.isArray(t) ? t.join(" ") : undefined;
  return (
    <svg width="26" height="10" aria-hidden="true" className="line-key">
      <line x1="0" y1="5" x2="26" y2="5" stroke={`var(--cat-${(index % 4) + 1})`} strokeWidth="2.4" strokeDasharray={dash} />
    </svg>
  );
}

function VariableChip({ id, label, source, inUse, canAdd, onAdd }:
  { id: string; label: string; source: string; inUse: boolean; canAdd: boolean; onAdd: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id });
  return (
    <div className="palette-row">
      <button ref={setNodeRef} type="button" className="chip draggable" data-in-use={inUse || undefined} data-dragging={isDragging || undefined}
        {...listeners} {...attributes} aria-roledescription="variable arrastrable">
        {label} <small>{source}</small>
      </button>
      <button type="button" className="btn small" onClick={onAdd} disabled={inUse || !canAdd}>
        {inUse ? "En uso" : "Añadir panel"}<span className="sr-only"> {inUse ? `: ${label}` : `de ${label}`}</span>
      </button>
    </div>
  );
}

function PanelDrop({ index, children }: { index: number; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `panel-${index}` });
  return <section ref={setNodeRef} className="panel studio-panel" data-over={isOver || undefined}>{children}</section>;
}

function NewPanelDrop({ active }: { active: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: "nuevo-panel" });
  return (
    <div ref={setNodeRef} className="new-panel" data-over={isOver || undefined} data-active={active || undefined}>
      Suelta aquí una variable para añadir un panel ({MAX_PANELS} como máximo)
    </div>
  );
}

function GeoAdder({ onAdd, exclude }: { onAdd: (g: Geography) => void; exclude: string[] }) {
  const [q, setQ] = useState("");
  const search = useQuery({ queryKey: ["search", q], queryFn: () => api.searchGeographies(q), enabled: q.trim().length >= 2 });
  return (
    <div className="search-wrap">
      <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="Añadir distrito, provincia o UBIGEO" aria-label="Añadir territorio a la comparación" />
      {q.trim().length >= 2 && search.data && (
        <ul className="results" aria-label="Resultados">
          {search.data.items.filter((g) => !exclude.includes(g.geo_id)).map((g) => (
            <li key={g.geo_id}>
              <button type="button" className="terr" onClick={() => { onAdd(g); setQ(""); }}>
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

function StudioPanel({ index, total, variable, panelKey, names, theme }:
  { index: number; total: number; variable?: Variable; panelKey: string; names: Record<string, string>; theme: string }) {
  const st = useStudio();
  const { datasetId, variableId } = splitKey(panelKey);
  const specs = useMemo(() => st.geos.map((g) => buildSpec(
    { focus: g, selected: g, datasetId, variableId, view: "annual", method: st.method, start: st.start, end: st.end, context: false }, g, "annual",
  )), [st.geos, st.method, st.start, st.end, datasetId, variableId]);
  const fam = useQuery<CompareResult, ApiError>({ queryKey: ["compare", specs], queryFn: () => api.compare(specs, `estudio:${panelKey}`), enabled: !!variable });
  const label = variable ? cleanQuantity(variable.physical_quantity) : panelKey;
  const unit = variable?.unit_display ?? "";
  return (
    <>
      <div className="panel-head">
        <h2>{label} <small className="muted">{SOURCE[datasetId] ?? datasetId} · valor anual</small></h2>
        <div className="toolbar" role="group" aria-label={`Panel ${index + 1}`}>
          <button type="button" className="btn small" onClick={() => st.movePanel(index, -1)} disabled={index === 0}>Subir</button>
          <button type="button" className="btn small" onClick={() => st.movePanel(index, 1)} disabled={index === total - 1}>Bajar</button>
          <button type="button" className="btn small" onClick={() => st.removePanel(index)} disabled={total <= 1}>Quitar</button>
        </div>
      </div>
      {fam.isPending && <p className="state" role="status">Calculando {st.geos.length} territorios con datos NASA…</p>}
      {fam.error && <p className="state" role="alert">{fam.error.problem.detail}</p>}
      {fam.data && (
        <>
          <CompareChart items={fam.data.items} names={names} unit={unit} theme={theme}
            label={`${label}: serie anual y tendencia en ${st.geos.length} territorios, ${st.start}–${st.end}`} />
          <table className="table compare-table">
            <caption className="sr-only">Tendencia de {label} por territorio</caption>
            <thead>
              <tr><th scope="col">Territorio</th><th scope="col">Cambio por década</th><th scope="col">IC 95 %</th>
                <th scope="col">p</th><th scope="col" title="Corregido por pruebas múltiples (BH-FDR) en este panel">q</th><th scope="col">Veredicto</th></tr>
            </thead>
            <tbody>
              {fam.data.items.map((it, i) => {
                const s = it.statistics, v = s ? verdictOf(s) : null, d = digitsFor(s?.estimate);
                return (
                  <tr key={it.geo_id}>
                    <th scope="row"><LineKey index={i} /> {names[it.geo_id] ?? it.geo_id}
                      {it.geography?.area_km2 != null && <small className="muted"> · {fmt(it.geography.area_km2, 0)} km²</small>}</th>
                    {s ? (<>
                      <td className="num">{signed(s.estimate, d)} <small className="muted">{s.estimate_unit.split("/")[0]}</small></td>
                      <td className="num">{signed(s.ci_lower, d)} a {signed(s.ci_upper, d)}</td>
                      <td className="num">{fmtP(s.p_value)}</td>
                      <td className="num">{fmtP(s.q_value)}</td>
                      <td><span className="tag" data-kind={v?.kind}>{v?.label}</span>
                        {s.warnings.some((w) => w.includes("píxel")) && <small className="muted"> · menor que un píxel</small>}</td>
                    </>) : (
                      <td colSpan={5} className="muted">{it.error?.code === "token_required" ? "Requiere token (análisis pesado). " : ""}{it.error?.detail}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="hint">{fam.data.note} <Link href="/metodos">Cómo leer estos resultados</Link>.</p>
        </>
      )}
    </>
  );
}
