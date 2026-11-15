// E2E y paridad web ↔ API (plan §12A.4 «test_web_api_sdk_parity», parte web).
// Usa datos NASA reales: requiere la API con Earth Engine configurado (resultados de IMERG en caché tras la primera vez).
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";
const es = (v: number, d: number) =>
  (v > 0 ? "+" : v < 0 ? "−" : "") + new Intl.NumberFormat("es-PE", { minimumFractionDigits: d, maximumFractionDigits: d }).format(Math.abs(v));

async function runId(page: import("@playwright/test").Page) {
  const code = page.locator(".runrow code");
  await expect(code).toHaveText(/^run_[0-9a-f]{20}$/);
  return (await code.textContent())!;
}

test("el estudio por defecto muestra el mismo resultado que la API", async ({ page, request }) => {
  await page.goto("/explorar");
  await expect(page.locator(".verdict h1")).toContainText("provincia de Trujillo");
  const id = await runId(page);
  const st = await (await request.get(`${API}/analyses/${id}/statistics`)).json();
  // La cifra mostrada es exactamente la del motor (mismo run_id, mismo valor formateado).
  await expect(page.locator(".facts")).toContainText(es(st.estimate, 1));
  await expect(page.locator(".facts")).toContainText(`p = ${new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(st.p_value)}`);
  const verdict = st.p_value < 0.05 && (st.ci_lower > 0 || st.ci_upper < 0) ? /evidencia de/ : /no concluyente/;
  await expect(page.locator(".verdict .tag")).toHaveText(verdict);
});

test("la exportación CSV contiene la serie y el run_id mostrado", async ({ page }) => {
  await page.goto("/explorar");
  const id = await runId(page);
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "CSV" }).click()]);
  const text = await (await import("node:fs/promises")).readFile((await dl.path())!, "utf8");
  const lines = text.trim().split("\n");
  expect(lines[0]).toContain("time_start_utc,value,unit");
  expect(lines.length).toBe(1 + 22); // 22 años 2003–2024
  expect(lines.slice(1).every((l) => l.includes(id))).toBe(true);
});

test("elegir un distrito y cambiar de método recalcula y queda en la URL", async ({ page, request }) => {
  await page.goto("/explorar");
  await page.getByRole("group", { name: "Elegir territorio" }).getByRole("button", { name: /Laredo/ }).click();
  await expect(page).toHaveURL(/selected=pe-ign2020%3A130106/);
  await expect(page.locator(".verdict h1")).toContainText("distrito de Laredo");
  const senId = await runId(page);
  await page.getByRole("button", { name: "OLS (n efectivo)" }).click();
  await expect(page).toHaveURL(/method=ols/);
  await expect(page.locator(".runrow code")).not.toHaveText(senId);
  const olsId = await runId(page);
  const st = await (await request.get(`${API}/analyses/${olsId}/statistics`)).json();
  expect(st.estimator).toBe("ols");
  expect(st.test_method).toBe("ols_ar1_t");
});

test("un análisis pesado sin token muestra el motivo y el coste, no un error genérico", async ({ page }) => {
  // MERRA-2 horario 1981–2024 (≈ 385 000 imágenes) sigue siendo «pesado» con el umbral de 2026-11-15
  await page.goto("/explorar?datasetId=nasa-merra2-slv&variableId=air_temperature_2m_c&start=1981");
  const err = page.locator("section.panel.error[role=alert]");
  await expect(err).toContainText("requiere un token de API");
  await expect(err).toContainText("imágenes fuente");
});

test("el tema se puede cambiar y se recuerda", async ({ page }) => {
  await page.goto("/explorar");
  await page.getByRole("group", { name: "Tema de color" }).getByRole("button", { name: "Oscuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("group", { name: "Tema de color" }).getByRole("button", { name: "Sistema" }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.+/);
});

test("Fuentes y Métodos muestran el catálogo y las combinaciones reales de la API", async ({ page, request }) => {
  const datasets = await (await request.get(`${API}/catalog/datasets`)).json();
  await page.goto("/fuentes");
  await expect(page.locator("article.source")).toHaveCount(datasets.length + 2); // + 2 conjuntos de fronteras
  await expect(page.getByText("NASA/GPM_L3/IMERG_MONTHLY_V07")).toBeVisible();
  await page.goto("/metodos");
  await expect(page.locator(".table tbody tr")).toHaveCount(2);
  await expect(page.getByRole("row", { name: /Theil–Sen/ })).not.toContainText("HAC");
});

test("sin scroll horizontal en 1024, 768 y 390 px", async ({ page }) => {
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/explorar");
    await expect(page.locator(".verdict h1")).toBeVisible();
    const { sw, cw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    expect(sw, `ancho ${width}`).toBeLessThanOrEqual(cw);
  }
});

test("JSON y SVG exportados llevan run_id, estadística y fuente", async ({ page }) => {
  await page.goto("/explorar");
  const id = await runId(page);
  const fs = await import("node:fs/promises");
  const [j] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "JSON" }).click()]);
  const json = JSON.parse(await fs.readFile((await j.path())!, "utf8"));
  expect(json.run_id).toBe(id);
  expect(json.statistics.estimate).toEqual(expect.any(Number));
  expect(json.source_versions[0].ee_collection_id).toBe("NASA/GPM_L3/IMERG_MONTHLY_V07");
  expect(json.request.geography.geo_ids).toEqual(["pe-ign2020:1301"]);
  const [s] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "SVG" }).click()]);
  const svg = await fs.readFile((await s.path())!, "utf8");
  expect(svg.startsWith("<svg")).toBe(true);
  expect(svg).toContain(id);
  expect(svg).toContain("IMERG");
  const [p] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "PNG" }).click()]);
  const png = await fs.readFile((await p.path())!);
  expect(png.subarray(1, 4).toString()).toBe("PNG");
});

test("el ciclo estacional muestra la climatología y los extremos que calcula la API", async ({ page, request }) => {
  await page.goto("/explorar");
  const id = await runId(page);
  const s = await (await request.get(`${API}/analyses/${id}/seasonal`)).json();
  const panel = page.getByRole("region", { name: "Ciclo estacional" });
  await expect(panel).toContainText(`Mes más alto en promedio: ${s.peak_month}`);
  const rows = panel.locator(".extremes tbody tr");
  await expect(rows).toHaveCount(s.extremes.length);
  await expect(rows.first()).toContainText(s.extremes[0].label);
  await expect(panel.locator(".chart.heat svg")).toBeVisible();
});
