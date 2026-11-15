// Historia guiada del caso Trujillo: seis escenas cuyos números vienen de la API (no escritos a mano).
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

test("seis escenas en orden y cada hallazgo coincide con la API", async ({ page, request }) => {
  await page.goto("/historias/trujillo-el-nino");
  const titles = page.locator(".scene > .scene-body > h2");
  await expect(titles).toHaveText(["¿Qué está cambiando?", "¿En qué distritos?", "¿Qué ocurrió en 2017 y 2023?",
    "¿Relación o coincidencia?", "¿Habría dado una alerta?", "¿Qué NO podemos concluir?"]);
  // Escena 3: conteos de eventos = API
  const ev = await (await request.get(`${API}/cases/trujillo-el-nino/events?geo_id=pe-ign2020:1301&year_from=2003&year_to=2024`)).json();
  const nino = ev.items.filter((e: { display_class: string }) => e.display_class === "coincidencia_el_nino").length;
  await expect(page.locator("#anios-2017-2023 .finding")).toContainText(`${ev.count} registros de huaico o inundación`);
  await expect(page.locator("#anios-2017-2023 .finding")).toContainText(`${nino} ocurrieron durante un episodio El Niño Costero`);
  await expect(page.locator("#anios-2017-2023 .finding")).toContainText("ninguno tiene atribución causal verificada");
  // Escena 1: tres tarjetas con veredicto
  await expect(page.locator(".trend-card .tag")).toHaveCount(3);
  // Escena 4 se calcula sola; escena 5 declara honestamente que está en preparación
  await expect(page.locator("#relacion .assoc-table tbody tr")).toHaveCount(4);
  await expect(page.locator("#alerta")).toContainText("En preparación");
  // Escena 6: límites desde la API
  const s = await (await request.get(`${API}/cases/trujillo-el-nino`)).json();
  await expect(page.locator("#limites .limits li")).toHaveCount(s.limitations.length);
});

test("la lista de historias enlaza al caso", async ({ page }) => {
  await page.goto("/historias");
  await page.getByRole("link", { name: /El Niño Costero/ }).click();
  await expect(page).toHaveURL(/\/historias\/trujillo-el-nino$/);
});
