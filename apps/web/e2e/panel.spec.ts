// Panel ambiental (experiencia principal): varias variables de un territorio, con método y nivel de confianza
// elegidos por el usuario. Cada número mostrado coincide con la API para la misma especificación (paridad web/API/SDK).
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const GEO = "pe-ign2020:1301";
const RAIN = "nasa-gpm-imerg-monthly-v07/precipitation_mm_month";
const NDVI = "nasa-modis-mod13q1-061/ndvi";

function spec(varKey: string, statistics: object) {
  const [dataset_id, variable_id] = varKey.split("/");
  return { data: { dataset_id, variable_id }, geography: { geo_ids: [GEO] },
    time: { start: "2003-01-01", end_exclusive: "2025-01-01", granularity: "year" }, statistics };
}
const sign = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");
const card = (page: import("@playwright/test").Page, variable: string) => page.locator(`.dash-card[data-variable="${variable}"]`);

test("la portada es el panel: varias variables del territorio, sin preparar un estudio", async ({ page, request }) => {
  await page.goto("/?territorio=pe-ign2020%3A1301");
  await expect(page.locator("nav.primary a").first()).toHaveText("Panel");
  await expect(page.locator(".dash-card")).toHaveCount(4);
  const rain = card(page, "precipitation_mm_month");
  await expect(rain.locator(".dash-value")).toBeVisible();
  const r = await (await request.post(`${API}/analyses`, { data: spec(RAIN,
    { estimator: "theil_sen", interval_method: "theil_sen_ar1", significance_test: "mann_kendall_ar1" }) })).json();
  const st = r.statistics;
  await expect(rain.locator(".dash-stats")).toContainText(`IC ${Math.round(st.confidence_level * 100)} %`);
  await expect(rain.locator(".dash-value")).toContainText(sign(st.estimate));
  // Las variables que no se pueden calcular sin token lo dicen (motivo y coste), sin inventar un valor
  for (const v of ["air_temperature_2m_c", "soil_moisture_0_10cm_kgm2"]) {
    await expect(card(page, v).locator(".dash-value, [role=alert]").first()).toBeVisible({ timeout: 60_000 });
  }
  // Procedencia y cobertura temporal a un clic
  await rain.getByRole("button", { name: "Fuente y detalles" }).click();
  await expect(rain.locator(".prov")).toContainText("NASA/GPM_L3/IMERG_MONTHLY_V07");
  await expect(rain).toContainText("Disponible desde 1998-01-01");
  await expect(rain).toContainText(`Años con dato: ${st.n_observations} de ${st.n_observations + st.n_missing}`);
});

test("nivel de confianza y método elegidos por el usuario = API (IC 90 %, Theil–Sen con IC analítico)", async ({ page, request }) => {
  await page.goto(`/?territorio=pe-ign2020%3A1301&variables=${encodeURIComponent(`${RAIN},${NDVI}`)}`);
  const ndvi = card(page, "ndvi");
  await expect(ndvi.locator(".dash-value")).toBeVisible();
  await page.getByLabel("Nivel de confianza").selectOption("0.9");
  await page.getByText("Opciones avanzadas").click();
  await page.getByLabel("Intervalo de confianza").selectOption("theil_sen_analytic");
  await expect(page).toHaveURL(/confianza=0\.9/);
  await expect(page).toHaveURL(/ic=theil_sen_analytic/);
  await expect(page.locator(".warn-hint")).toContainText("no corrige la autocorrelación");
  await expect(ndvi.locator(".dash-stats")).toContainText("IC 90 %");
  const r = await (await request.post(`${API}/analyses`, { data: spec(NDVI,
    { estimator: "theil_sen", interval_method: "theil_sen_analytic", significance_test: "mann_kendall_ar1", confidence_level: 0.9 }) })).json();
  const st = r.statistics;
  expect(st.confidence_level).toBe(0.9);
  // Veredicto con α = 1 − nivel (p < 0,10 e IC sin 0)
  const evidence = st.p_value < 0.1 && (st.ci_lower > 0 || st.ci_upper < 0);
  await expect(ndvi.locator(".tag")).toHaveText(evidence ? (st.estimate > 0 ? "evidencia de aumento" : "evidencia de disminución") : "no concluyente");
  await expect(ndvi.locator(".dash-stats")).toContainText(sign(st.ci_lower));
});

test("«Ver detalle» abre Explorar con la misma configuración y el mismo resultado", async ({ page }) => {
  await page.goto(`/?territorio=pe-ign2020%3A1301&variables=${encodeURIComponent(RAIN)}&estimador=ols`);
  const rain = card(page, "precipitation_mm_month");
  await expect(rain.locator(".dash-stats")).toContainText("t (n efectivo)");
  const value = await rain.locator(".dash-value").textContent();
  await rain.getByRole("link", { name: "Ver detalle" }).click();
  await expect(page).toHaveURL(/\/explorar\?.*method=ols/);
  await expect(page.locator(".verdict .facts dd").first()).toHaveText(value!.trim());
});

test("quitar una variable quita su tarjeta y queda en la URL", async ({ page }) => {
  await page.goto("/?territorio=pe-ign2020%3A1301");
  await expect(page.locator(".dash-card")).toHaveCount(4);
  await page.getByRole("group", { name: "Variables NASA" }).getByRole("button", { name: /vegetación/i }).click();
  await expect(page.locator(".dash-card")).toHaveCount(3);
  await expect(page).toHaveURL(/variables=/);
});
