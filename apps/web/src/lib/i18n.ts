"use client";
// Idioma de la interfaz: español (por defecto) o inglés. Se guarda en el navegador; las URL no cambian.
// Los textos se escriben en pares t("español", "English") junto a su uso, para no perder el contexto.
// Los textos que devuelve la API (advertencias, errores, notas) se traducen con apiText(): el motor y sus cifras no
// cambian, solo la redacción; un texto desconocido se muestra tal cual.
import { useCallback } from "react";
import { create } from "zustand";

export type Lang = "es" | "en";
export const LANG_KEY = "gaia-lang";

interface LangStore { lang: Lang; setLang: (l: Lang) => void }

export const useLangStore = create<LangStore>((set) => ({
  lang: "es",
  setLang: (lang) => {
    try { if (lang === "es") localStorage.removeItem(LANG_KEY); else localStorage.setItem(LANG_KEY, lang); } catch { /* sin almacenamiento */ }
    document.documentElement.lang = lang;
    set({ lang });
  },
}));

/** Idioma guardado (se aplica tras montar para no romper la hidratación: el servidor siempre pinta en español). */
export function readStoredLang(): Lang {
  try { return localStorage.getItem(LANG_KEY) === "en" ? "en" : "es"; } catch { return "es"; }
}

// Idioma del render en curso. Zustand usa useSyncExternalStore: mientras React hidrata (también los bloques Suspense
// que hidratan después de la cabecera) cada componente recibe el valor del servidor («es») y luego se vuelve a pintar
// con el idioma guardado. Las funciones de lib/ (tr, fmt, verdictOf…) leen este valor para coincidir siempre con el
// render del componente que las llama; por eso todo componente que muestre texto llama antes a useT() o useLang().
let renderLang: Lang | null = null;

/** Idioma vigente (el del render en curso, o el guardado si se llama fuera de un render). */
export const currentLang = (): Lang => renderLang ?? useLangStore.getState().lang;

/** Elige el texto del idioma vigente. Fuera de un componente suscrito no se redibuja solo. */
export const tr = (es: string, en: string) => (currentLang() === "en" ? en : es);

/** Hook: suscribe el componente al idioma (seguro para la hidratación). */
export function useLang(): Lang {
  const lang = useLangStore((s) => s.lang);
  renderLang = lang;
  return lang;
}

/** Hook: suscribe el componente al idioma y devuelve t(es, en). */
export function useT() {
  const lang = useLang();
  return useCallback((es: string, en: string) => (lang === "en" ? en : es), [lang]);
}

/** Configuración regional para números y fechas. */
export const locale = () => (currentLang() === "en" ? "en-US" : "es-PE");

// ── Textos de la API ────────────────────────────────────────────────────────────────────────────────────────────
const MONTHS_EN: Record<string, string> = {
  ene: "Jan", feb: "Feb", mar: "Mar", abr: "Apr", may: "May", jun: "Jun",
  jul: "Jul", ago: "Aug", sep: "Sep", oct: "Oct", nov: "Nov", dic: "Dec",
};

const EXACT: Record<string, string> = {
  // Catálogo
  "precipitación total": "total precipitation",
  "humedad del suelo 0–10 cm (modelo)": "soil moisture 0–10 cm (model)",
  "temperatura del aire (forzante del modelo)": "air temperature (model forcing)",
  "temperatura del aire a 2 m (reanálisis)": "air temperature at 2 m (reanalysis)",
  "vapor de agua precipitable total": "total precipitable water vapour",
  "viento zonal a 10 m": "zonal wind at 10 m",
  "viento meridional a 10 m": "meridional wind at 10 m",
  "índice de vegetación de diferencia normalizada": "normalized difference vegetation index",
  "temperatura superficial del mar": "sea surface temperature",
  "adimensional": "dimensionless",
  "NASA Earth Science data: uso abierto con atribución": "NASA Earth Science data: open use with attribution",
  "0.1° (~11 km en el ecuador)": "0.1° (~11 km at the equator)",
  "Útil para lluvia regional; no resuelve microcuencas ni calles.": "Useful for regional rainfall; it does not resolve small catchments or streets.",
  "Producto modelado, no observación directa.": "Modelled product, not a direct observation.",
  "Malla gruesa: varios distritos pueden compartir celda.": "Coarse grid: several districts may share a cell.",
  "Celdas costeras pueden quedar enmascaradas (océano).": "Coastal cells may be masked (ocean).",
  "Reanálisis atmosférico de gran escala; no caracteriza microcuencas.": "Large-scale atmospheric reanalysis; it does not characterize small catchments.",
  "QA: solo píxeles con SummaryQA ≤ 1 (bueno o marginal).": "QA: only pixels with SummaryQA ≤ 1 (good or marginal).",
  "Extracción a 500 m para controlar coste; resolución nativa 250 m.": "Extracted at 500 m to control cost; native resolution 250 m.",
  "Usar una región oceánica real; sobre tierra no hay datos (cobertura insuficiente).": "Use a real ocean region; there are no data over land (insufficient coverage).",
  "Nubes reducen píxeles válidos: revisar valid_pixel_count.": "Clouds reduce valid pixels: check valid_pixel_count.",
  // Notas de respuestas
  "q-valores BH-FDR sobre los ítems con p-valor de esta familia. Un solapamiento de IC no equivale a una prueba de diferencia: para comparar dos pendientes usa POST /analyses/difference (IC propio).":
    "BH-FDR q-values over the items with a p-value in this family. Overlapping CIs are not a test of difference: to compare two slopes use POST /analyses/difference (its own CI).",
  "Diferencia = pendiente de A menos pendiente de B, con su propio IC. Que los IC de A y B se solapen no implica que la diferencia sea cero, ni lo contrario.":
    "Difference = slope of A minus slope of B, with its own CI. Overlapping CIs for A and B do not imply that the difference is zero, nor the opposite.",
  "Climatología descriptiva del periodo extraído (media, mediana y rango intercuartílico P25–P75 por mes calendario). Los meses sin dato no se rellenan. No es un pronóstico.":
    "Descriptive climatology of the extracted period (mean, median and P25–P75 interquartile range per calendar month). Months without data are not filled in. It is not a forecast.",
  // Advertencias y errores fijos
  "Serie constante: no hay variación para estimar tendencia": "Constant series: there is no variation to estimate a trend",
  "Climatología base incompleta para algún mes: esas anomalías quedan nulas": "Incomplete baseline climatology for some month: those anomalies are left empty",
  "IC OLS clásico con residuos autocorrelacionados: preferir HAC o bootstrap por bloques": "Classic OLS CI with autocorrelated residuals: prefer HAC or block bootstrap",
  "Prueba t iid con autocorrelación sustancial: p-valor no fiable": "iid t-test with substantial autocorrelation: unreliable p-value",
  "IC analítico Theil–Sen asume independencia; considerar bootstrap por bloques": "Analytic Theil–Sen CI assumes independence; consider block bootstrap",
  "Mann–Kendall sin corrección con autocorrelación: p-valor puede ser optimista": "Uncorrected Mann–Kendall with autocorrelation: the p-value may be optimistic",
  "Una diferencia de pendientes describe cuánto más cambia A que B en el periodo; no explica por qué.": "A slope difference describes how much more A changes than B over the period; it does not explain why.",
  "Earth Engine está ocupado con otras extracciones; reintenta en unos segundos": "Earth Engine is busy with other extractions; retrying in a few seconds",
  "Este servidor exige token para nuevos análisis": "This server requires a token for new analyses",
  "El atlas requiere al menos 10 años (end_year − start_year ≥ 9)": "The atlas needs at least 10 years (end_year − start_year ≥ 9)",
  "A y B son el mismo territorio": "A and B are the same territory",
  "La extracción mensual de este run ya no está en caché; vuelve a ejecutarlo.": "This run's monthly extraction is no longer cached; run it again.",
  "El servidor de GaIA está despertando; reintentando…": "The GaIA server is waking up; retrying…",
  "Resultado ya calculado": "Result already computed",
  "Extracción ligera": "Light extraction",
  "Extracción pesada en Earth Engine (requiere token de API)": "Heavy Earth Engine extraction (requires an API token)",
};

const COVERAGE_TAIL_SMALL = (area: string, res: string, px: string) =>
  ` The territory (${area} km²) is much smaller than a ${res} cell (~${px} km²) or falls in a masked cell (e.g. ocean in land products). ` +
  "Try the next administrative level up or a larger ROI; nothing is extrapolated from neighbouring cells.";

const PATTERNS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)( \d{4})?$/, (m) => `${MONTHS_EN[m[1]!]}${m[2] ?? ""}`],
  [/^N=(\d+) menor al mínimo (\d+) para inferencia$/, (m) => `N=${m[1]} is below the minimum of ${m[2]} for inference`],
  [/^Cobertura (.+) inferior al umbral (.+): resultado exploratorio$/, (m) => `Coverage ${m[1]} below the ${m[2]} threshold: exploratory result`],
  [/^Autocorrelación alta \(ρ ≈ ([\d.,]+)\): aun corregida, con series cortas la prueba puede rechazar algo más del 5 % nominal \(medido ≈ 9 % con φ = 0,6 y n = 22\)$/,
    (m) => `High autocorrelation (ρ ≈ ${m[1]}): even corrected, with short series the test may reject somewhat more than the nominal 5 % (measured ≈ 9 % with φ = 0.6 and n = 22)`],
  [/^IC HAC con solo (\d+) observaciones: medido, cubre bastante menos del nominal; preferir el IC con n efectivo AR\(1\)$/,
    (m) => `HAC CI with only ${m[1]} observations: as measured, it covers well below nominal; prefer the AR(1) effective-n CI`],
  [/^Anomalía mensual respecto a climatología (.+)–(.+) \(exclusivo\)$/, (m) => `Monthly anomaly relative to the ${m[1]}–${m[2]} climatology (exclusive)`],
  [/^(\d+) año\(s\) incompletos excluidos del total\/medio anual \(no se rellenan\)$/,
    (m) => `${m[1]} incomplete year(s) excluded from the annual total/mean (not filled in)`],
  [/^El territorio \(([\d.,]+) km²\) es menor que un píxel nativo \(~([\d.,]+) km²\): el valor representa una celda que excede el territorio, no una medición interna$/,
    (m) => `The territory (${m[1]} km²) is smaller than a native pixel (~${m[2]} km²): the value represents a cell larger than the territory, not a measurement inside it`],
  [/^El territorio \(([\d.,]+) km²\) es menor que un píxel nativo \(~([\d.,]+) km²\)\.$/,
    (m) => `The territory (${m[1]} km²) is smaller than a native pixel (~${m[2]} km²).`],
  [/^Sin píxeles válidos en el territorio para el periodo: cobertura insuficiente\. El territorio \(([\d.,]+) km²\) es mucho menor que una celda de (.+) \(~([\d.,]+) km²\) o cae en una celda enmascarada .*$/,
    (m) => `No valid pixels in the territory for the period: insufficient coverage.${COVERAGE_TAIL_SMALL(m[1]!, apiText(m[2]!), m[3]!)}`],
  [/^Sin píxeles válidos en el territorio para el periodo: cobertura insuficiente\. Revisa que el producto cubra este territorio .*$/,
    () => "No valid pixels in the territory for the period: insufficient coverage. Check that the product covers this territory (e.g. SST only over the ocean)."],
  [/^El producto empieza en (.+)$/, (m) => `The product starts on ${m[1]}`],
  [/^geo_id no encontrado: (.+)$/, (m) => `geo_id not found: ${m[1]}`],
  [/^run no encontrado: (.+)$/, (m) => `run not found: ${m[1]}`],
  [/^Límite de (\d+) extracciones nuevas por hora alcanzado$/, (m) => `Limit of ${m[1]} new extractions per hour reached`],
  [/^Análisis pesado \(~(.+) s estimados, (.+) imágenes fuente\): requiere token de API\. .*$/,
    (m) => `Heavy analysis (~${m[1]} s estimated, ${m[2]} source images): requires an API token. Token-free alternatives: a shorter period or a monthly product.`],
  [/^La comparación requiere (\d+) extracciones nuevas y tu cupo restante esta hora es (\d+)\. .*$/,
    (m) => `The comparison needs ${m[1]} new extractions and your remaining quota this hour is ${m[2]}. Use a token or fewer territories.`],
  [/^El atlas requiere (\d+) extracciones de tu cupo y te quedan (\d+) esta hora\. .*$/,
    (m) => `The atlas needs ${m[1]} extractions from your quota and you have ${m[2]} left this hour. Use a token or a smaller territory.`],
  [/^(.+) no tiene subunidades en el sistema de fronteras$/, (m) => `${m[1]} has no subunits in the boundary system`],
  [/^(\d+) subunidades superan el máximo de (\d+) por atlas$/, (m) => `${m[1]} subunits exceed the maximum of ${m[2]} per atlas`],
  [/^Solo (\d+) periodos: el IC bootstrap es poco fiable con series tan cortas$/, (m) => `Only ${m[1]} periods: the bootstrap CI is unreliable with such short series`],
  [/^Los residuos de A y B están correlacionados \(r = ([\d.,-]+)\): .*$/,
    (m) => `The residuals of A and B are correlated (r = ${m[1]}): comparing their CIs separately would be misleading; that is why the difference has its own CI.`],
  [/^bootstrap de bloques móviles sobre pares de periodos \(b=(\d+), R=(\d+), semilla=(\d+)\)$/,
    (m) => `moving-block bootstrap over pairs of periods (b=${m[1]}, R=${m[2]}, seed=${m[3]})`],
  [/^No se pudo contactar la API en (.+)\. ¿Está levantado el backend\?$/, (m) => `Could not reach the API at ${m[1]}. Is the backend running?`],
  [/^Error (\d+)$/, (m) => `Error ${m[1]}`],
  [/^(A|B): (.+)$/, (m) => `${m[1]}: ${apiText(m[2]!)}`],
  [/^Límites: (.+)$/, (m) => `Boundaries: ${m[1]!.replace("Instituto Geográfico Nacional (IGN) del Perú, vía", "National Geographic Institute (IGN) of Peru, via").replace("válido desde", "valid from")}`],
];

Object.assign(EXACT, {
  "GLDAS Noah Land Surface Model L4 3-hourly 0.25° V2.1 (media mensual)": "GLDAS Noah Land Surface Model L4 3-hourly 0.25° V2.1 (monthly mean)",
  "MERRA-2 M2T1NXSLV single-level diagnostics horario (media mensual)": "MERRA-2 M2T1NXSLV single-level diagnostics, hourly (monthly mean)",
  "MODIS Terra Vegetation Indices 16-Day 250 m (media mensual)": "MODIS Terra Vegetation Indices 16-Day 250 m (monthly mean)",
  "MODIS-Aqua Ocean L3 SMI SST diaria 4 km (media mensual; no MUR)": "MODIS-Aqua Ocean L3 SMI SST, daily 4 km (monthly mean; not MUR)",
});

/** Traduce un texto de la API al idioma actual (en español lo devuelve igual). */
export function apiText(s: string | null | undefined): string {
  if (s == null) return "";
  if (currentLang() === "es") return s;
  const exact = EXACT[s];
  if (exact) return exact;
  for (const [re, f] of PATTERNS) {
    const m = s.match(re);
    if (m) return f(m);
  }
  return s;
}
