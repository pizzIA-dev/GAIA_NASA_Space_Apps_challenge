/* Renderizador compartido de las propuestas visuales F1. Datos: window.DATA (NASA IMERG real, ver data.json).
   Sin dependencias. SVG accesible: foco por teclado, títulos, sin depender solo del color. */
(function () {
  "use strict";
  const D = window.DATA;
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const NF = (d) => new Intl.NumberFormat("es-PE", { maximumFractionDigits: d, minimumFractionDigits: d });
  const fmt = (v, d = 1) => (v == null || Number.isNaN(v) ? "sin dato" : NF(d).format(v));
  const sgn = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + NF(d).format(Math.abs(v));
  const svgNS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(svgNS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  const $ = (s) => document.querySelector(s);
  const PIXEL_KM2 = Math.pow(D.dataset.native_scale_m / 1000, 2);
  const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  const state = { sel: "province", method: "sen", view: "annual" };

  function territory() {
    if (state.sel === "province") {
      const st = state.method === "ols" ? D.annual_ols.statistics : D.annual.statistics;
      const runId = state.method === "ols" ? D.annual_ols.run_id : D.annual.run_id;
      return { name: "Provincia de Trujillo", short: "Trujillo (provincia)", area: D.province.area_km2,
               series: D.annual.series, st, runId, olsAvailable: true };
    }
    const d = D.districts[state.sel];
    return { name: "Distrito de " + d.name, short: d.name, area: d.area_km2, series: d.series, st: d.statistics,
             runId: d.run_id, olsAvailable: false, district: d };
  }

  // ---------------------------------------------------------------- veredicto (TrendVerdict, plan §5.4)
  function verdict(st) {
    const sig = st.p_value != null && st.p_value < 0.05 && (st.ci_lower > 0 || st.ci_upper < 0);
    if (!sig) return { key: "nc", text: "no concluyente", phrase: "no muestra un cambio distinguible de cero" };
    return st.estimate > 0 ? { key: "up", text: "evidencia de aumento", phrase: "muestra evidencia de aumento" }
                           : { key: "down", text: "evidencia de disminución", phrase: "muestra evidencia de disminución" };
  }

  function renderVerdict() {
    const t = territory(), anomaly = state.view === "anomaly";
    const st = anomaly ? D.anomaly.statistics : t.st, v = verdict(st);
    const where = t.name.replace("Provincia de ", "la provincia de ").replace("Distrito de ", "el distrito de ");
    $("[data-verdict-title]").textContent = anomaly
      ? `Las anomalías mensuales de lluvia en ${where} ${v.phrase.replace("muestra", "muestran")} entre 2003 y 2024.`
      : `La lluvia anual en ${where} ${v.phrase} entre 2003 y 2024.`;
    $("[data-verdict-tag]").textContent = v.text;
    $("[data-verdict-tag]").dataset.kind = v.key;
    const method = st.estimator === "ols" ? "Regresión OLS, IC robusto HAC (Newey–West)" : "Pendiente de Theil–Sen";
    $("[data-verdict-detail]").innerHTML =
      `<dl class="facts">
        <div><dt>Cambio estimado</dt><dd class="num">${sgn(st.estimate)} mm por década</dd></div>
        <div><dt>IC ${Math.round(st.confidence_level * 100)} %</dt><dd class="num">${sgn(st.ci_lower)} a ${sgn(st.ci_upper)} mm</dd></div>
        <div><dt>Prueba</dt><dd class="num">${st.test_method === "mann_kendall" ? "Mann–Kendall" : "t con errores HAC"}, p = ${fmt(st.p_value, 2)}</dd></div>
        <div><dt>${anomaly ? "Meses con dato" : "Años con dato"}</dt><dd class="num">${st.n_observations} de ${anomaly ? 264 : 22}</dd></div>
      </dl>
      <p class="method-note">${method}. El intervalo describe el procedimiento bajo sus supuestos; no es la probabilidad de que el valor real esté dentro. Describe el periodo elegido: no es un pronóstico.</p>`;
    const warn = [...(st.warnings || [])];
    if (t.district && t.area < PIXEL_KM2) warn.unshift(`Este distrito (${fmt(t.area, 0)} km²) es menor que un píxel IMERG (~${fmt(PIXEL_KM2, 0)} km²): el valor es el de una celda compartida con distritos vecinos.`);
    $("[data-warnings]").innerHTML = warn.length ? warn.map((w) => `<li>${w}</li>`).join("") : "<li>Sin advertencias de calidad.</li>";
    $("[data-runid]").textContent = (anomaly ? D.anomaly.run_id : t.runId) || "—";
    $("[data-method-ols]").disabled = !t.olsAvailable;
    $("[data-method-ols]").title = t.olsAvailable ? "" : "En el prototipo solo la provincia tiene la variante OLS precalculada";
    if (!t.olsAvailable && state.method === "ols") { state.method = "sen"; }
    document.querySelectorAll("[data-method]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.method === state.method)));
    document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === state.view)));
    $("[data-crumb]").textContent = t.district ? `Perú › La Libertad › Trujillo › ${t.district.name}` : "Perú › La Libertad › Trujillo";
    const list = $("[data-district-list]");
    if (list) {
      list.innerHTML = "";
      const mk = (label, sel, extra) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "terr"; b.setAttribute("aria-pressed", String(state.sel === sel));
        b.innerHTML = `<span>${label}</span><span class="num muted">${extra}</span>`;
        b.addEventListener("click", () => { state.sel = sel; if (sel !== "province") state.view = "annual"; renderAll(); });
        list.appendChild(b);
      };
      mk("Provincia completa", "province", `${fmt(D.province.area_km2, 0)} km²`);
      D.districts.forEach((d, i) => mk(d.name, i, d.statistics ? `${sgn(d.statistics.estimate)}` : "—"));
    }
  }

  // ---------------------------------------------------------------- serie temporal con tendencia
  function renderChart() {
    const host = $("[data-chart]");
    host.innerHTML = "";
    const W = host.clientWidth || 720, H = Math.max(260, Math.min(360, W * 0.42));
    const m = { l: 52, r: 16, t: 14, b: 34 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", width: "100%", height: H }, host);
    const t = territory();
    const anomaly = state.view === "anomaly" && state.sel === "province";
    const pts = anomaly
      ? D.anomaly.series.map((s) => ({ x: new Date(s.time_start_utc), v: s.value }))
      : t.series.map((s) => ({ x: new Date(s.time_start_utc), v: s.value }));
    const st = anomaly ? D.anomaly.statistics : t.st;
    el("title", {}, svg).textContent = anomaly
      ? "Anomalía mensual de precipitación IMERG, provincia de Trujillo, 2003–2024, con tendencia Theil–Sen"
      : `Precipitación anual IMERG, ${t.name}, 2003–2024, con tendencia ${st.estimator === "ols" ? "OLS" : "Theil–Sen"}`;
    const dec = (d) => d.getUTCFullYear() + (d - Date.UTC(d.getUTCFullYear(), 0, 1)) / (365.2425 * 864e5);
    const x0 = 2003, x1 = anomaly ? 2025 : 2024.5;
    const vals = pts.map((p) => p.v).filter((v) => v != null);
    let y0 = Math.min(...vals), y1 = Math.max(...vals);
    const pad = (y1 - y0) * 0.12; y0 = anomaly ? y0 - pad : Math.max(0, y0 - pad); y1 += pad;
    const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
    const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
    // ejes y rejilla
    const g = el("g", { class: "axis" }, svg);
    const step = niceStep((y1 - y0) / 5);
    for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) {
      el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), class: v === 0 ? "zero" : "grid" }, g);
      el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }, g).textContent = NF(0).format(v);
    }
    for (let yr = 2003; yr <= 2024; yr += (W < 520 ? 7 : 3)) {
      el("text", { x: X(yr + (anomaly ? 0.5 : 0)), y: H - m.b + 20, "text-anchor": "middle" }, g).textContent = yr;
    }
    el("text", { x: m.l, y: m.t - 2, class: "unit" }, g).textContent = anomaly ? "mm respecto al mismo mes" : "mm por año";
    // abanico del IC de la pendiente alrededor del pivote (mediana)
    const perYear = (v) => (st.estimate_unit.endsWith("/decade") ? v / 10 : v);
    const tVals = pts.filter((p) => p.v != null).map((p) => dec(p.x));
    const tMed = median(tVals);
    const yMed = st.intercept + perYear(st.estimate) * tMed;
    const fanL = (tt) => yMed + perYear(st.ci_lower) * (tt - tMed), fanU = (tt) => yMed + perYear(st.ci_upper) * (tt - tMed);
    const ta = 2003, tb = anomaly ? 2024.95 : 2024;
    el("path", { class: "fan", d: `M${X(ta)},${Y(fanL(ta))} L${X(tb)},${Y(fanL(tb))} L${X(tb)},${Y(fanU(tb))} L${X(ta)},${Y(fanU(ta))} Z` }, svg);
    // serie (cortes en faltantes, sin interpolar)
    let d = "", pen = false;
    pts.forEach((p) => {
      if (p.v == null) { pen = false; return; }
      d += (pen ? "L" : "M") + X(dec(p.x)) + "," + Y(p.v); pen = true;
    });
    el("path", { d, class: anomaly ? "series thin" : "series" }, svg);
    // tendencia
    el("line", { x1: X(ta), y1: Y(st.intercept + perYear(st.estimate) * ta), x2: X(tb),
                 y2: Y(st.intercept + perYear(st.estimate) * tb), class: "trend" }, svg);
    // puntos interactivos (anual)
    const tip = $("[data-tip]");
    if (!anomaly) {
      pts.forEach((p) => {
        if (p.v == null) return;
        const c = el("circle", { cx: X(dec(p.x)), cy: Y(p.v), r: 3.6, class: "pt", tabindex: 0 }, svg);
        el("title", {}, c).textContent = `${p.x.getUTCFullYear()}: ${fmt(p.v, 0)} mm`;
        const show = (ev) => {
          tip.hidden = false;
          tip.innerHTML = `<b>${p.x.getUTCFullYear()}</b><br>${fmt(p.v, 0)} mm en el año<br><small>IMERG V07 · 12 meses válidos</small>`;
          const r = host.getBoundingClientRect(), cx = ev.clientX ?? (r.left + X(dec(p.x)));
          tip.style.left = Math.min(r.width - 170, Math.max(0, cx - r.left + 12)) + "px";
          tip.style.top = Math.max(0, Y(p.v) - 54) + "px";
        };
        c.addEventListener("mousemove", show); c.addEventListener("focus", show);
        c.addEventListener("mouseleave", () => (tip.hidden = true)); c.addEventListener("blur", () => (tip.hidden = true));
      });
    }
    $("[data-chart-legend]").innerHTML =
      `<span class="lg series-k"></span>${anomaly ? "anomalía mensual" : "total anual"}
       <span class="lg trend-k"></span>tendencia ${st.estimator === "ols" ? "OLS" : "Theil–Sen"}
       <span class="lg fan-k"></span>pendientes dentro del IC ${Math.round(st.confidence_level * 100)} % (no es banda de predicción)`;
  }

  // ---------------------------------------------------------------- mapa de pendientes por distrito
  function renderMap() {
    const host = $("[data-map]");
    host.innerHTML = "";
    const W = host.clientWidth || 420, H = Math.round(W * 0.92);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": "Mapa de distritos de la provincia de Trujillo coloreados por la pendiente de la lluvia anual", width: "100%", height: H }, host);
    const defs = el("defs", {}, svg);
    const pat = el("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: css("--hatch"), "stroke-width": 1.4 }, pat);
    const rings = (geom) => (geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates);
    const all = D.districts.flatMap((d) => rings(d.geometry).flat(3)); // [poly][anillo][punto][lon,lat] → números
    const lons = all.filter((_, i) => i % 2 === 0), lats = all.filter((_, i) => i % 2 === 1);
    const [mx0, mx1, my0, my1] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
    const k = Math.cos(((my0 + my1) / 2) * Math.PI / 180);
    const s = Math.min((W - 24) / ((mx1 - mx0) * k), (H - 24) / (my1 - my0));
    const P = ([lon, lat]) => [12 + (lon - mx0) * k * s, 12 + (my1 - lat) * s];
    const path = (geom) => rings(geom).map((poly) => poly.map((ring) => "M" + ring.map((c) => P(c).join(",")).join("L") + "Z").join("")).join("");
    const maxAbs = Math.max(...D.districts.filter((d) => d.statistics).map((d) => Math.abs(d.statistics.estimate)), 1);
    const color = (v) => divergent(v / maxAbs);
    D.districts.forEach((d, i) => {
      const st = d.statistics, sig = st && verdict(st).key !== "nc", small = d.area_km2 < PIXEL_KM2;
      const g = el("g", { class: "district" + (state.sel === i ? " active" : ""), tabindex: 0, role: "button",
                          "aria-pressed": String(state.sel === i),
                          "aria-label": `${d.name}: ${st ? sgn(st.estimate) + " mm por década, " + verdict(st).text : "sin dato"}` }, svg);
      const p = path(d.geometry);
      el("path", { d: p, fill: st ? color(st.estimate) : css("--nodata"), class: "fill" }, g);
      if (st && !sig) el("path", { d: p, fill: "url(#hatch)", class: "hatch" }, g);
      el("path", { d: p, class: "edge" + (small ? " subpixel" : "") }, g);
      const pick = () => { state.sel = state.sel === i ? "province" : i; renderAll(); };
      g.addEventListener("click", pick);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      el("title", {}, g).textContent = `${d.name} (${fmt(d.area_km2, 0)} km²): ${st ? sgn(st.estimate) + " mm/década, p = " + fmt(st.p_value, 2) : "sin dato"}`;
    });
    // leyenda
    const lg = $("[data-map-legend]");
    const stops = [-1, -0.5, 0, 0.5, 1].map((f) => `<span style="background:${divergent(f)}"></span>`).join("");
    lg.innerHTML = `<div class="ramp">${stops}</div>
      <div class="ramp-labels num"><span>${sgn(-maxAbs, 0)}</span><span>0</span><span>${sgn(maxAbs, 0)} mm/década</span></div>
      <p><span class="key hatch-k"></span>Rayado: sin evidencia de cambio (p ≥ 0,05 o IC incluye 0)</p>
      <p><span class="key sub-k"></span>Borde discontinuo: distrito menor que un píxel IMERG (~${fmt(PIXEL_KM2, 0)} km²)</p>`;
  }

  // ---------------------------------------------------------------- heatmap año × mes
  function renderHeat() {
    const host = $("[data-heat]");
    if (!host) return;
    host.innerHTML = "";
    const rows = D.monthly.series;
    const W = host.clientWidth || 600, cw = (W - 44) / 12, ch = Math.max(9, Math.min(14, cw * 0.32)), H = 22 * ch + 26;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", width: "100%", height: H }, host);
    el("title", {}, svg).textContent = "Precipitación mensual IMERG, provincia de Trujillo, años 2003–2024 por mes";
    const vmax = Math.max(...rows.map((r) => r.value || 0));
    rows.forEach((r) => {
      const dt = new Date(r.time_start_utc), yi = dt.getUTCFullYear() - 2003, mi = dt.getUTCMonth();
      const x = 40 + mi * cw, y = 18 + yi * ch;
      const c = el("rect", { x, y, width: cw - 1, height: ch - 1, fill: r.value == null ? "url(#hatch)" : sequential(Math.sqrt(r.value / vmax)) }, svg);
      el("title", {}, c).textContent = `${MONTHS[mi]} ${dt.getUTCFullYear()}: ${fmt(r.value, 0)} mm`;
    });
    MONTHS.forEach((mo, i) => { el("text", { x: 40 + i * cw + cw / 2, y: 12, "text-anchor": "middle", class: "tick" }, svg).textContent = mo; });
    [2003, 2008, 2013, 2017, 2023].forEach((yr) => { el("text", { x: 36, y: 18 + (yr - 2003) * ch + ch - 2, "text-anchor": "end", class: "tick" }, svg).textContent = yr; });
    $("[data-heat-legend]").innerHTML = `<div class="ramp seq">${[0, 0.25, 0.5, 0.75, 1].map((f) => `<span style="background:${sequential(f)}"></span>`).join("")}</div>
      <div class="ramp-labels num"><span>0</span><span>${fmt(vmax, 0)} mm/mes (escala raíz)</span></div>`;
  }

  // ---------------------------------------------------------------- utilidades
  function niceStep(raw) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const n = raw / p; return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p; }
  function median(a) { const s = [...a].sort((x, y) => x - y); const n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; }
  function hex2rgb(h) { const n = parseInt(h.replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function mix(a, b, f) { const A = hex2rgb(a), B = hex2rgb(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * f)).join(",")})`; }
  function divergent(f) { f = Math.max(-1, Math.min(1, f)); return f < 0 ? mix(css("--div-mid"), css("--div-dry"), -f) : mix(css("--div-mid"), css("--div-wet"), f); }
  function sequential(f) { return mix(css("--seq-0"), css("--seq-1"), Math.max(0, Math.min(1, f))); }

  function renderAll() { renderVerdict(); renderChart(); renderMap(); renderHeat(); }

  document.querySelectorAll("[data-method]").forEach((b) => b.addEventListener("click", () => { state.method = b.dataset.method; renderAll(); }));
  document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
    state.view = b.dataset.view; if (state.view === "anomaly") state.sel = "province"; renderAll();
  }));
  const reset = $("[data-reset]");
  if (reset) reset.addEventListener("click", () => { state.sel = "province"; renderAll(); });
  $("[data-copy]")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("[data-runid]").textContent); $("[data-copy]").textContent = "Copiado"; } catch { /* sin portapapeles */ }
    setTimeout(() => ($("[data-copy]").textContent = "Copiar run_id"), 1500);
  });
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderAll, 120); });
  renderAll();
})();
