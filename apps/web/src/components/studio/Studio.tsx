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
import { digitsFor, fmt, fmtP, signed, unitPerDecade, verdictOf } from "@/lib/format";
import { apiText, useT } from "@/lib/i18n";
import { simpleName, simpleUnit } from "@/lib/variables";
import { buildSpec, methodLabel, METHODS_ORDER, type Method } from "@/lib/study";
import { LINE_TYPES, MAX_PANELS, MAX_TERRITORIES, splitKey, studioFromUrl, studioToUrl, useStudio } from "@/lib/studio";
import { useResolvedTheme } from "@/lib/theme";
import type { CompareResult, Geography, SlopeDifference, Variable } from "@/lib/types";
import { CompareChart } from "./CompareChart";

const keyOf = (v: Variable) => `${v.dataset_id}/${v.variable_id}`;

export function Studio() {
  const t = useT();
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
  const name = (key: string) => (byKey[key] ? simpleName(byKey[key].dataset_id, byKey[key].variable_id, byKey[key].physical_quantity) : key);

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}
      accessibility={{
        announcements: {
          onDragStart: ({ active }) => t(`Variable ${name(String(active.id))} tomada. Usa las flechas para elegir un panel y Espacio para soltar.`,
            `Variable ${name(String(active.id))} picked up. Use the arrows to choose a panel and Space to drop.`),
          onDragOver: ({ over }) => (over
            ? (over.id === "nuevo-panel" ? t("Sobre el hueco para un panel nuevo.", "Over the slot for a new panel.")
              : t(`Sobre el panel ${Number(String(over.id).slice(6)) + 1}.`, `Over panel ${Number(String(over.id).slice(6)) + 1}.`))
            : t("Fuera de los paneles.", "Outside the panels.")),
          onDragEnd: ({ over }) => (over ? t("Variable colocada.", "Variable placed.") : t("Cancelado: la variable no se colocó.", "Cancelled: the variable was not placed.")),
          onDragCancel: () => t("Arrastre cancelado.", "Drag cancelled."),
        },
        screenReaderInstructions: { draggable: t("Para arrastrar una variable pulsa Espacio, muévete con las flechas y suelta con Espacio. También puedes usar el botón «Añadir panel».",
          "To drag a variable press Space, move with the arrows and drop with Space. You can also use the “Add panel” button.") },
      }}>
      <div className="layout" id="contenido">
        <aside className="rail" aria-label={t("Configuración del estudio", "Study settings")}>
          <section>
            <h2>{t("Variables", "Variables")}</h2>
            <p className="hint">{t("Arrastra una variable a un panel para cambiarla, o al hueco final para añadir otra.", "Drag a variable onto a panel to change it, or onto the final slot to add another.")}</p>
            <div className="palette">
              {variables.data?.map((v) => (
                <VariableChip key={keyOf(v)} id={keyOf(v)} label={simpleName(v.dataset_id, v.variable_id, v.physical_quantity)}
                  inUse={st.panels.includes(keyOf(v))} canAdd={st.panels.length < MAX_PANELS} onAdd={() => st.addPanel(keyOf(v))} />
              ))}
            </div>
          </section>
          <section>
            <h2>{t("Territorios", "Territories")} ({st.geos.length} {t("de", "of")} {MAX_TERRITORIES})</h2>
            <ul className="geo-list">
              {st.geos.map((g, i) => (
                <li key={g}>
                  <LineKey index={i} />
                  <span>{names[g] ?? g}</span>
                  <button type="button" className="btn small" onClick={() => st.removeGeo(g)} disabled={st.geos.length <= 1}
                    aria-label={`${t("Quitar", "Remove")} ${names[g] ?? g}`}>{t("Quitar", "Remove")}</button>
                </li>
              ))}
            </ul>
            {st.geos.length < MAX_TERRITORIES && <GeoAdder onAdd={(g) => st.addGeo(g.geo_id)} exclude={st.geos} />}
          </section>
          <section>
            <h2>{t("Periodo y método", "Period and method")}</h2>
            <div className="years">
              <label>{t("Desde", "From")} <select value={st.start} onChange={(e) => st.set({ start: Number(e.target.value) })}>
                {range(2001, st.end - 9).map((y) => <option key={y}>{y}</option>)}</select></label>
              <label>{t("hasta", "to")} <select value={st.end} onChange={(e) => st.set({ end: Number(e.target.value) })}>
                {range(st.start + 9, 2024).map((y) => <option key={y}>{y}</option>)}</select></label>
            </div>
            <div className="seg" role="group" aria-label={t("Método", "Method")}>
              {METHODS_ORDER.map((m: Method) => (
                <button key={m} type="button" aria-pressed={st.method === m} onClick={() => st.set({ method: m })}>{methodLabel(m)}</button>
              ))}
            </div>
            <p className="hint">{t("Mismo método e intervalo para todas las comparaciones. Los q-valores corrigen por pruebas múltiples (BH-FDR) dentro de cada panel, y el veredicto se basa en q.", "Same method and interval for every comparison. The q-values correct for multiple testing (BH-FDR) within each panel, and the verdict is based on q.")}</p>
          </section>
        </aside>

        <main className="main">
          <h1 className="page-title">{t("Análisis avanzado", "Advanced analysis")}</h1>
          <p className="lead">{t("Compara cómo cambia cada variable en varios territorios, con el mismo periodo y el mismo método. Pasa el cursor sobre un panel para ver la misma fecha en todos.", "Compare how each variable changes across several territories, with the same period and the same method. Hover over a panel to see the same date in all of them.")}</p>
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

function VariableChip({ id, label, inUse, canAdd, onAdd }:
  { id: string; label: string; inUse: boolean; canAdd: boolean; onAdd: () => void }) {
  const t = useT();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id });
  return (
    <div className="palette-row">
      <button ref={setNodeRef} type="button" className="chip draggable" data-in-use={inUse || undefined} data-dragging={isDragging || undefined}
        {...listeners} {...attributes} aria-roledescription={t("variable arrastrable", "draggable variable")}>
        {label}
      </button>
      <button type="button" className="btn small" onClick={onAdd} disabled={inUse || !canAdd}>
        {inUse ? t("En uso", "In use") : t("Añadir panel", "Add panel")}<span className="sr-only"> {inUse ? `: ${label}` : `${t("de", "of")} ${label}`}</span>
      </button>
    </div>
  );
}

function PanelDrop({ index, children }: { index: number; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `panel-${index}` });
  return <section ref={setNodeRef} className="panel studio-panel" data-over={isOver || undefined}>{children}</section>;
}

function NewPanelDrop({ active }: { active: boolean }) {
  const t = useT();
  const { setNodeRef, isOver } = useDroppable({ id: "nuevo-panel" });
  return (
    <div ref={setNodeRef} className="new-panel" data-over={isOver || undefined} data-active={active || undefined}>
      {t(`Suelta aquí una variable para añadir un panel (${MAX_PANELS} como máximo)`, `Drop a variable here to add a panel (${MAX_PANELS} at most)`)}
    </div>
  );
}

function GeoAdder({ onAdd, exclude }: { onAdd: (g: Geography) => void; exclude: string[] }) {
  const t = useT();
  const [q, setQ] = useState("");
  const search = useQuery({ queryKey: ["search", q], queryFn: () => api.searchGeographies(q), enabled: q.trim().length >= 2 });
  return (
    <div className="search-wrap">
      <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder={t("Añadir distrito, provincia o UBIGEO", "Add district, province or UBIGEO")} aria-label={t("Añadir territorio a la comparación", "Add territory to the comparison")} />
      {q.trim().length >= 2 && search.data && (
        <ul className="results" aria-label={t("Resultados", "Results")}>
          {search.data.items.filter((g) => !exclude.includes(g.geo_id)).map((g) => (
            <li key={g.geo_id}>
              <button type="button" className="terr" onClick={() => { onAdd(g); setQ(""); }}>
                <span>{g.name} <small className="muted">{g.path?.slice(1).join(" › ")}</small></span>
                <span className="muted">{g.admin_level === "ADM3" ? t("distrito", "district") : g.admin_level === "ADM2" ? t("provincia", "province") : t("departamento", "department")}</span>
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
  const t = useT();
  const st = useStudio();
  const { datasetId, variableId } = splitKey(panelKey);
  const specs = useMemo(() => st.geos.map((g) => buildSpec(
    { focus: g, selected: g, datasetId, variableId, view: "annual", method: st.method, start: st.start, end: st.end }, g, "annual",
  )), [st.geos, st.method, st.start, st.end, datasetId, variableId]);
  const fam = useQuery<CompareResult, ApiError>({ queryKey: ["compare", specs], queryFn: () => api.compare(specs, `estudio:${panelKey}`), enabled: !!variable });
  const label = variable ? simpleName(variable.dataset_id, variable.variable_id, variable.physical_quantity) : panelKey;
  const unit = simpleUnit(variable?.unit_display ?? "");
  return (
    <>
      <div className="panel-head">
        <h2>{label} <small className="muted">· {t("valor anual", "annual value")}</small></h2>
        <div className="toolbar" role="group" aria-label={`Panel ${index + 1}`}>
          <button type="button" className="btn small" onClick={() => st.movePanel(index, -1)} disabled={index === 0}>{t("Subir", "Up")}</button>
          <button type="button" className="btn small" onClick={() => st.movePanel(index, 1)} disabled={index === total - 1}>{t("Bajar", "Down")}</button>
          <button type="button" className="btn small" onClick={() => st.removePanel(index)} disabled={total <= 1}>{t("Quitar", "Remove")}</button>
        </div>
      </div>
      {fam.isPending && <p className="state" role="status">{t(`Calculando ${st.geos.length} territorios con datos NASA…`, `Computing ${st.geos.length} territories with NASA data…`)}</p>}
      {fam.error && <p className="state" role="alert">{apiText(fam.error.problem.detail)}</p>}
      {fam.data && (
        <>
          <CompareChart items={fam.data.items} names={names} unit={unit} theme={theme}
            label={t(`${label}: serie anual y tendencia en ${st.geos.length} territorios, ${st.start}–${st.end}`, `${label}: annual series and trend in ${st.geos.length} territories, ${st.start}–${st.end}`)} />
          <table className="table compare-table">
            <caption className="sr-only">{t(`Tendencia de ${label} por territorio`, `${label} trend by territory`)}</caption>
            <thead>
              <tr><th scope="col">{t("Territorio", "Territory")}</th><th scope="col">{t("Cambio por década", "Change per decade")}</th><th scope="col">{t("IC", "CI")} 95 %</th>
                <th scope="col">p</th><th scope="col" title={t("Corregido por pruebas múltiples (BH-FDR) en este panel", "Corrected for multiple testing (BH-FDR) in this panel")}>q</th><th scope="col">{t("Veredicto", "Verdict")}</th></tr>
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
                      <td className="num">{signed(s.ci_lower, d)} {t("a", "to")} {signed(s.ci_upper, d)}</td>
                      <td className="num">{fmtP(s.p_value)}</td>
                      <td className="num">{fmtP(s.q_value)}</td>
                      <td><span className="tag" data-kind={v?.kind}>{v?.label}</span>
                        {s.warnings.some((w) => w.includes("píxel")) && <small className="muted"> · {t("menor que un píxel", "smaller than a pixel")}</small>}</td>
                    </>) : (
                      <td colSpan={5} className="muted">{it.error?.code === "token_required" ? t("Requiere token (análisis pesado). ", "Requires a token (heavy analysis). ") : ""}{apiText(it.error?.detail)}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <SlopeDiff specs={specs} items={fam.data.items} names={names} method={st.method} />
          <p className="hint">{apiText(fam.data.note)} <Link href="/metodos">{t("Cómo leer estos resultados", "How to read these results")}</Link>.</p>
        </>
      )}
    </>
  );
}

function SlopeDiff({ specs, items, names, method }:
  { specs: object[]; items: CompareResult["items"]; names: Record<string, string>; method: string }) {
  const t = useT();
  const ok = items.map((it, i) => ({ it, i })).filter((x) => x.it.statistics?.estimate != null);
  const [pick, setPick] = useState<[number, number]>([0, 1]);
  const ia = ok[pick[0]]?.i ?? ok[0]?.i, ib = ok[pick[1]]?.i ?? ok[1]?.i;
  const enabled = method !== "ols" && ia != null && ib != null && ia !== ib;
  const q = useQuery<SlopeDifference, ApiError>({ queryKey: ["difference", specs[ia ?? 0], specs[ib ?? 0]],
    queryFn: () => api.difference(specs[ia!]!, specs[ib!]!), enabled });
  if (ok.length < 2) return null;
  const name = (i: number) => names[items[i]!.geo_id] ?? items[i]!.geo_id;
  const d = q.data?.difference, dg = digitsFor(d?.estimate);
  const excludes0 = d?.ci_lower != null && d?.ci_upper != null && (d.ci_lower > 0 || d.ci_upper < 0);
  return (
    <section className="slope-diff" aria-label={t("Diferencia de pendientes", "Slope difference")}>
      <h3>{t("Diferencia de pendientes", "Slope difference")}</h3>
      {method === "ols" ? (
        <p className="hint">{t("La diferencia de pendientes solo se ofrece con Theil–Sen: con series anuales cortas, los intervalos de OLS cubren bastante menos del 95 % declarado. Cambia el método para compararlas.",
          "The slope difference is only offered with Theil–Sen: with short annual series, OLS intervals cover well below the stated 95 %. Change the method to compare them.")}</p>
      ) : (
        <>
          <div className="diff-pick">
            {(["A", "B"] as const).map((lbl, k) => (
              <label key={lbl}>{lbl}{" "}
                <select value={pick[k]} onChange={(e) => setPick((p) => (k === 0 ? [Number(e.target.value), p[1]] : [p[0], Number(e.target.value)]))}>
                  {ok.map((x, j) => <option key={x.it.geo_id} value={j}>{name(x.i)}</option>)}
                </select>
              </label>
            ))}
          </div>
          {ia === ib && <p className="hint">{t("Elige dos territorios distintos.", "Choose two different territories.")}</p>}
          {q.isPending && enabled && <p className="state" role="status">{t("Calculando la diferencia con su propio intervalo…", "Computing the difference with its own interval…")}</p>}
          {q.error && <p className="state" role="alert">{apiText(q.error.problem.detail)}</p>}
          {d && d.status === "ok" && (
            <>
              <p className="diff-result">
                <b className="num">{signed(d.estimate, dg)} {unitPerDecade(d.estimate_unit)}</b>{" "}
                ({t("IC", "CI")} 95 % <span className="num">{signed(d.ci_lower, dg)} {t("a", "to")} {signed(d.ci_upper, dg)}</span>, p ≈ {fmtP(d.p_value)}):{" "}
                {excludes0
                  ? `${name(ia!)} ${d.estimate! > 0 ? t("cambia más (hacia arriba)", "changes more (upwards)") : t("cambia más hacia abajo", "changes more downwards")} ${t("que", "than")} ${name(ib!)}.`
                  : t(`no hay evidencia de que ${name(ia!)} y ${name(ib!)} cambien a ritmos distintos.`, `there is no evidence that ${name(ia!)} and ${name(ib!)} change at different rates.`)}
              </p>
              <p className="hint">{d.n_paired_observations} {t("años comparados", "years compared")} · {apiText(d.ci_method)}.{" "}
                {d.residual_correlation != null && `${t("Correlación entre territorios", "Correlation between territories")}: ${fmt(d.residual_correlation, 2)}. `}
                {apiText(q.data!.interpretation)}</p>
            </>
          )}
          {d && d.status !== "ok" && <p className="state">{d.warnings.map(apiText).join(" ")}</p>}
        </>
      )}
    </section>
  );
}
