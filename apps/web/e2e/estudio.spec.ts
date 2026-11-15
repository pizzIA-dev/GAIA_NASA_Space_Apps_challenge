// Estudio: comparar territorios con q-valores, arrastrar variables a paneles y alternativa por botones.
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

/** Arrastre realista (dnd-kit necesita movimiento progresivo del puntero, no un salto). */
async function drag(page: import("@playwright/test").Page, from: import("@playwright/test").Locator, to: import("@playwright/test").Locator) {
  await from.scrollIntoViewIfNeeded();
  const a = (await from.boundingBox())!;
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2 + 12, { steps: 4 });
  await to.scrollIntoViewIfNeeded();
  const b = (await to.boundingBox())!;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 20 });
  await page.mouse.up();
}

test("compara Huanchaco y Moche con los mismos números que /analyses/compare", async ({ page, request }) => {
  await page.goto("/estudio");
  const rows = page.locator(".compare-table tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Huanchaco");
  await expect(rows.nth(1)).toContainText("menor que un píxel"); // Moche, 28 km²
  const specs = ["pe-ign2020:130104", "pe-ign2020:130107"].map((g) => ({
    data: { dataset_id: "nasa-gpm-imerg-monthly-v07", variable_id: "precipitation_mm_month" },
    geography: { geo_ids: [g] },
    time: { start: "2003-01-01", end_exclusive: "2025-01-01", granularity: "year" },
    statistics: { estimator: "theil_sen", interval_method: "theil_sen_analytic", significance_test: "mann_kendall" },
  }));
  const fam = await (await request.post(`${API}/analyses/compare`, { data: { specs, multiple_testing: "BH_FDR" } })).json();
  const q = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(fam.items[0].statistics.q_value);
  await expect(rows.nth(0).locator("td").nth(3)).toHaveText(q);
});

test("arrastrar una variable al hueco crea un panel y a un panel lo reemplaza", async ({ page }) => {
  await page.goto("/estudio");
  await expect(page.locator(".studio-panel")).toHaveCount(1);
  const ndvi = page.locator(".chip.draggable", { hasText: "índice de vegetación" });
  await drag(page, ndvi, page.locator(".new-panel"));
  await expect(page.locator(".studio-panel")).toHaveCount(2);
  await expect(page.locator(".studio-panel").nth(1)).toContainText("índice de vegetación");
  await expect(page).toHaveURL(/panels=.*ndvi/);
  const t2m = page.locator(".chip.draggable", { hasText: "temperatura del aire a 2 m" });
  await drag(page, t2m, page.locator(".studio-panel").nth(1));
  await expect(page.locator(".studio-panel").nth(1)).toContainText("temperatura del aire a 2 m");
});

test("alternativa sin arrastrar: añadir, mover y quitar paneles con botones", async ({ page }) => {
  await page.goto("/estudio");
  await page.getByRole("button", { name: /Añadir panel de humedad del suelo/ }).click();
  await expect(page.locator(".studio-panel")).toHaveCount(2);
  await page.getByRole("group", { name: "Panel 2" }).getByRole("button", { name: "Subir" }).click();
  await expect(page.locator(".studio-panel").first()).toContainText("humedad del suelo");
  await page.getByRole("group", { name: "Panel 1" }).getByRole("button", { name: "Quitar" }).click();
  await expect(page.locator(".studio-panel")).toHaveCount(1);
  await expect(page.locator(".studio-panel").first()).toContainText("precipitación");
});

test("en una familia de comparaciones el veredicto usa q (BH-FDR), no p", async ({ page }) => {
  // Caso real: NDVI de Laredo tiene p ≈ 0,04 sola, pero q ≈ 0,06 al compararla con Huanchaco y Moche.
  await page.goto("/estudio?panels=nasa-modis-mod13q1-061/ndvi&geos=pe-ign2020:130104,pe-ign2020:130107,pe-ign2020:130106");
  const laredo = page.locator(".compare-table tbody tr", { hasText: "Laredo" });
  await expect(laredo).toBeVisible();
  const [p, q] = await Promise.all([laredo.locator("td").nth(2).textContent(), laredo.locator("td").nth(3).textContent()]);
  const num = (s: string | null) => Number((s ?? "").replace("<", "").replace(",", ".").trim());
  expect(num(p)).toBeLessThan(0.05);
  expect(num(q)).toBeGreaterThanOrEqual(0.05);
  await expect(laredo.locator(".tag")).toHaveText("no concluyente");
  await expect(page.locator(".compare-table tbody tr", { hasText: "Moche" }).locator(".tag")).toHaveText("evidencia de disminución");
});
