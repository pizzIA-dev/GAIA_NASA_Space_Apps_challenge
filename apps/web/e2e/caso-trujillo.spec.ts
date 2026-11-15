// Caso Trujillo: capa de eventos SINPAD + episodios ENFEN. Datos oficiales versionados (data/case-trujillo).
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

test("la capa muestra los registros oficiales del periodo y nunca afirma causa", async ({ page, request }) => {
  const api = await (await request.get(`${API}/cases/trujillo-el-nino/events?geo_id=pe-ign2020:1301&year_from=2003&year_to=2024`)).json();
  await page.goto("/explorar?context=true");
  const panel = page.getByRole("region", { name: "Eventos SINPAD y episodios ENFEN" });
  await expect(panel.locator(".events-table tbody tr")).toHaveCount(api.count);
  await expect(panel).toContainText("0 tienen atribución causal verificada");
  await expect(panel).toContainText("no demuestra que El Niño los causara");
  await expect(panel.locator("tbody .swatch.ev-verified")).toHaveCount(0);
  await expect(panel.locator("tbody tr", { hasText: "84509" })).toContainText("EN-COSTERO-2017");
});

test("la capa solo se ofrece en territorios del caso y filtra por distrito", async ({ page }) => {
  await page.goto("/explorar?context=true&selected=pe-ign2020%3A130111&start=2017");
  const rows = page.getByRole("region", { name: "Eventos SINPAD y episodios ENFEN" }).locator(".events-table tbody tr");
  await expect(rows).toHaveCount(5); // Víctor Larco 2017–2024: 4 en 2017 + 1 en 2020
  await page.goto("/explorar?focus=pe-ign2020%3A1501&selected=pe-ign2020%3A1501");
  await expect(page.getByText("Eventos SINPAD y episodios El Niño Costero")).toHaveCount(0);
});

test("axe sin violaciones con la capa de contexto activada", async ({ page }) => {
  await page.goto("/explorar?context=true");
  await expect(page.locator(".events-table tbody tr").first()).toBeVisible();
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).exclude(".maplibregl-canvas").analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});
