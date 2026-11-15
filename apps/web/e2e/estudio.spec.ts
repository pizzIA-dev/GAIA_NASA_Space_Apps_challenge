// Estudio: comparar territorios con q-valores, arrastrar variables a paneles y alternativa por botones.
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

/** Arrastre realista (dnd-kit necesita movimiento progresivo del puntero, no un salto). */
async function drag(page: import("@playwright/test").Page, from: import("@playwright/test").Locator, to: import("@playwright/test").Locator) {
  // Origen y destino a la vista ANTES de pulsar: desplazar la página con el botón pulsado depende del navegador
  // (falló en Chromium/Linux cuando el destino quedaba justo bajo el borde de la ventana).
  await to.scrollIntoViewIfNeeded();
  await from.scrollIntoViewIfNeeded();
  const a = (await from.boundingBox())!;
  const b = (await to.boundingBox())!;
  const vh = page.viewportSize()!.height;
  if (a.y < 0 || a.y + a.height > vh || b.y < 0 || b.y + b.height > vh) {
    throw new Error(`Origen (y=${Math.round(a.y)}) o destino (y=${Math.round(b.y)}) fuera de la ventana (${vh}px)`);
  }
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2 + 12, { steps: 4 });
  // Al activarse el arrastre, el destino puede cambiar de tamaño/posición: se mide de nuevo antes de soltar.
  await page.waitForTimeout(100);
  const b2 = (await to.boundingBox()) ?? b;
  await page.mouse.move(b2.x + b2.width / 2, b2.y + b2.height / 2, { steps: 20 });
  await page.waitForTimeout(100);
  await page.mouse.up();
}

test("compara Huanchaco y Moche con los mismos números que /analyses/compare", async ({ page, request }) => {
  await page.goto("/estudio?geos=pe-ign2020:130104,pe-ign2020:130107");
  const rows = page.locator(".compare-table tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Huanchaco");
  await expect(rows.nth(1)).toContainText("menor que un píxel"); // Moche, 28 km²
  const specs = ["pe-ign2020:130104", "pe-ign2020:130107"].map((g) => ({
    data: { dataset_id: "nasa-gpm-imerg-monthly-v07", variable_id: "precipitation_mm_month" },
    geography: { geo_ids: [g] },
    time: { start: "2003-01-01", end_exclusive: "2025-01-01", granularity: "year" },
    statistics: { estimator: "theil_sen", interval_method: "theil_sen_ar1", significance_test: "mann_kendall_ar1" },
  }));
  const fam = await (await request.post(`${API}/analyses/compare`, { data: { specs, multiple_testing: "BH_FDR" } })).json();
  const q = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(fam.items[0].statistics.q_value);
  await expect(rows.nth(0).locator("td").nth(3)).toHaveText(q);
});

test("arrastrar una variable al hueco crea un panel y a un panel lo reemplaza", async ({ page }) => {
  // Ventana alta: origen (columna izquierda) y destino (hueco bajo el panel) visibles a la vez, sin desplazar la
  // página durante el arrastre (con las fuentes de Linux la página es más alta y el desplazamiento los separaba).
  await page.setViewportSize({ width: 1440, height: 1800 });
  await page.goto("/estudio?geos=pe-ign2020:130104,pe-ign2020:130107");
  await expect(page.locator(".studio-panel")).toHaveCount(1);
  const ndvi = page.locator(".chip.draggable", { hasText: "Vegetación (verdor)" });
  await drag(page, ndvi, page.locator(".new-panel"));
  await expect(page.locator(".studio-panel")).toHaveCount(2);
  await expect(page.locator(".studio-panel").nth(1)).toContainText("Vegetación (verdor)");
  await expect(page).toHaveURL(/panels=.*ndvi/);
  const t2m = page.locator(".chip.draggable", { hasText: "Temperatura del aire" });
  await drag(page, t2m, page.locator(".studio-panel").nth(1));
  await expect(page.locator(".studio-panel").nth(1)).toContainText("Temperatura del aire");
});

test("alternativa sin arrastrar: añadir, mover y quitar paneles con botones", async ({ page }) => {
  await page.goto("/estudio?geos=pe-ign2020:130104,pe-ign2020:130107");
  await page.getByRole("button", { name: /Añadir panel de Humedad del suelo/ }).click();
  await expect(page.locator(".studio-panel")).toHaveCount(2);
  await page.getByRole("group", { name: "Panel 2" }).getByRole("button", { name: "Subir" }).click();
  await expect(page.locator(".studio-panel").first()).toContainText("Humedad del suelo");
  await page.getByRole("group", { name: "Panel 1" }).getByRole("button", { name: "Quitar" }).click();
  await expect(page.locator(".studio-panel")).toHaveCount(1);
  await expect(page.locator(".studio-panel").first()).toContainText("Lluvia");
});

test("en una familia de comparaciones el veredicto usa q (BH-FDR), no p", async ({ page }) => {
  // Caso real (motor 0.2, n efectivo AR(1)): NDVI de Víctor Larco Herrera tiene p ≈ 0,02 sola, pero q ≈ 0,09 al
  // compararla con Huanchaco, El Porvenir y La Esperanza (familia de 4).
  await page.goto("/estudio?panels=nasa-modis-mod13q1-061/ndvi&geos=pe-ign2020:130111,pe-ign2020:130104,pe-ign2020:130102,pe-ign2020:130105");
  const vlh = page.locator(".compare-table tbody tr", { hasText: "Victor Larco" });
  await expect(vlh).toBeVisible();
  const [p, q] = await Promise.all([vlh.locator("td").nth(2).textContent(), vlh.locator("td").nth(3).textContent()]);
  const num = (s: string | null) => Number((s ?? "").replace("<", "").replace(",", ".").trim());
  expect(num(p)).toBeLessThan(0.05);
  expect(num(q)).toBeGreaterThanOrEqual(0.05);
  await expect(vlh.locator(".tag")).toHaveText("no concluyente");
});

test("diferencia de pendientes A − B con IC propio: el texto coincide con la API", async ({ page }) => {
  const resp = page.waitForResponse((r) => r.url().includes("/analyses/difference") && r.request().method() === "POST");
  await page.goto("/estudio?geos=pe-ign2020:130104,pe-ign2020:130107");
  const body = await (await resp).json();
  const d = body.difference;
  expect(d.status).toBe("ok");
  const block = page.locator(".slope-diff").first();
  await expect(block.locator(".diff-result")).toBeVisible();
  await expect(block).toContainText(`${d.n_paired_observations} años comparados`);
  await expect(block).toContainText("pares de periodos");
  const sign = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "");
  const txt = await block.locator(".diff-result b").textContent();
  expect(txt).toContain(sign(d.estimate));
  expect(txt).toContain("por década");
  const excludes0 = d.ci_lower > 0 || d.ci_upper < 0;
  await expect(block.locator(".diff-result")).toContainText(excludes0 ? "cambia más" : "no hay evidencia");
});
