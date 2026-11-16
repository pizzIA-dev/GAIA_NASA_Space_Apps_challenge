// Idioma de la interfaz: español por defecto; el selector ES/EN cambia los textos (también los de la API) sin cambiar
// la URL ni los números, y la elección se recuerda al recargar.
import { expect, test } from "@playwright/test";

const URL = "/?territorio=pe-ign2020%3A1301&variables=nasa-gpm-imerg-monthly-v07%2Fprecipitation_mm_month";

test("español por defecto; EN traduce la interfaz y se recuerda, con los mismos números", async ({ page }) => {
  await page.goto(URL);
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.locator("nav.primary a").first()).toHaveText("Panel");
  const rain = page.locator('.dash-card[data-variable="precipitation_mm_month"]');
  await expect(rain.locator(".dash-value")).toBeVisible();
  const valueEs = (await rain.locator(".dash-value").textContent())!;

  await page.getByRole("group", { name: "Idioma" }).getByRole("button", { name: "English" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("nav.primary a").first()).toHaveText("Dashboard");
  await expect(page.getByRole("heading", { name: "Rainfall" })).toBeVisible();
  await expect(rain.locator(".dash-stats")).toContainText("CI 95 %");
  await expect(rain.locator(".dash-value")).toContainText("per decade");
  // Mismo número: solo cambia el separador decimal y la redacción de la unidad
  const num = (s: string) => s.replace(/[^\d−+]/g, "");
  expect(num((await rain.locator(".dash-value").textContent())!)).toBe(num(valueEs));
  await expect(page).toHaveURL(/territorio=pe-ign2020%3A1301/);

  await page.reload();
  await expect(page.locator("nav.primary a").first()).toHaveText("Dashboard");
  await page.getByRole("group", { name: "Language" }).getByRole("button", { name: "Español" }).click();
  await expect(page.locator("nav.primary a").first()).toHaveText("Panel");
});

test("en inglés, Fuentes traduce también los textos del catálogo de la API", async ({ page }) => {
  await page.goto("/fuentes");
  await page.getByRole("group", { name: "Idioma" }).getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Data sources");
  await expect(page.getByText("Modelled product, not a direct observation.")).toBeVisible();
  await expect(page.getByText("NASA Earth Science data: open use with attribution").first()).toBeVisible();
});
