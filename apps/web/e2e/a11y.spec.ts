// Auditoría automática de accesibilidad (WCAG 2.1 A/AA) con axe-core en ambos temas.
// No sustituye la prueba con lector de pantalla, pero bloquea regresiones detectables automáticamente.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = [
  // Territorio de prueba explícito: CI no tiene Earth Engine y sus fixtures cubren solo ese territorio.
  { path: "/?territorio=pe-ign2020%3A1301", ready: ".dash-card .dash-value" },
  { path: "/explorar?focus=pe-ign2020%3A1301&selected=pe-ign2020%3A1301", ready: ".verdict h1" },
  { path: "/estudio?geos=pe-ign2020:130104,pe-ign2020:130107", ready: ".compare-table tbody tr" },
  { path: "/fuentes", ready: "article.source" },
  { path: "/metodos", ready: ".table tbody tr" },
  { path: "/atlas?territorio=pe-ign2020%3A1301", ready: ".atlas-summary" },
];

for (const theme of ["light", "dark"] as const) {
  for (const p of PAGES) {
    test(`axe sin violaciones: ${p.path} (${theme === "light" ? "claro" : "oscuro"})`, async ({ page }) => {
      await page.addInitScript((t) => { try { localStorage.setItem("ets-theme", t); } catch { /* */ } }, theme);
      await page.goto(p.path);
      await expect(page.locator(p.ready).first()).toBeVisible();
      await page.waitForTimeout(500); // gráficos y mapa terminan de pintarse
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        // El lienzo WebGL de MapLibre y el SVG de ECharts tienen alternativa textual propia (lista de territorios y tabla).
        .exclude(".maplibregl-canvas")
        .analyze();
      const summary = results.violations.map((v) =>
        `${v.id} [${v.impact}] ${v.help} → ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
      expect(summary, summary.join("\n")).toEqual([]);
    });
  }
}
