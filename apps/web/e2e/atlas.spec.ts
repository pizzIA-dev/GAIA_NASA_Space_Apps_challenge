// Atlas: un mapa por variable; cada resumen y tabla coincide con POST /atlas (misma especificación que Explorar).
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const TRUJILLO = "pe-ign2020:1301";

test("atlas de la provincia de Trujillo: resumen y tabla = API, enlace a Explorar", async ({ page, request }) => {
  await page.goto(`/atlas?territorio=${encodeURIComponent(TRUJILLO)}`);
  await expect(page.locator(".atlas-card")).toHaveCount(4);
  await expect(page.locator(".atlas-head h1")).toContainText("Trujillo");

  const r = await (await request.post(`${API}/atlas`, { data: {
    parent_geo_id: TRUJILLO, dataset_id: "nasa-gpm-imerg-monthly-v07", variable_id: "precipitation_mm_month",
    start_year: 2003, end_year: 2024 } })).json();
  expect(r.n_units).toBe(11);
  const rain = page.locator('.atlas-card[data-variable="precipitation_mm_month"]');
  await expect(rain.locator(".atlas-summary")).toContainText(`de ${r.n_units} unidades`);
  await expect(rain.locator(".ramp-labels")).toContainText("0");
  await rain.locator(".atlas-table summary").click();
  await expect(rain.locator(".atlas-table tbody tr")).toHaveCount(r.n_units);
  // Las tarjetas sin datos en caché muestran un estado honesto (cálculo, token o error), nunca un mapa vacío sin explicación
  for (const v of ["air_temperature_2m_c", "soil_moisture_0_10cm_kgm2", "ndvi"]) {
    await expect(page.locator(`.atlas-card[data-variable="${v}"] .atlas-summary, .atlas-card[data-variable="${v}"] [role=alert]`).first())
      .toBeVisible({ timeout: 60_000 });
  }
  const first = rain.locator(".atlas-table tbody tr th a").first();
  const name = await first.textContent();
  await first.click();
  await expect(page).toHaveURL(/\/explorar\?.*selected=pe-ign2020%3A1301\d\d/);
  await expect(page.locator(".crumb")).toContainText("Trujillo");
  expect(name).toBeTruthy();
});
