import { defineConfig } from "@playwright/test";

// E2E contra la API y la web (plan §16). Configurable por entorno para correr igual en Windows local y en CI Linux:
//  PW_CHANNEL  navegador del sistema ("msedge" por defecto en local; vacío = Chromium de Playwright, usado en CI)
//  API_CMD     comando para levantar la API si no está corriendo
//  WEB_CMD     comando para levantar la web si no está corriendo
const isWin = process.platform === "win32";
const channel = process.env.PW_CHANNEL ?? (isWin ? "msedge" : undefined);
const apiCmd = process.env.API_CMD ??
  (isWin ? "..\\api\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../api --port 8000"
         : "../api/.venv/bin/python -m uvicorn app.main:app --app-dir ../api --port 8000");

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 120_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    ...(channel ? { channel } : {}),
    headless: true,
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
    trace: process.env.CI ? "retain-on-failure" : "off",
  },
  webServer: [
    { command: apiCmd, url: "http://localhost:8000/api/v1/health", reuseExistingServer: true, timeout: 60_000 },
    { command: process.env.WEB_CMD ?? "npm run dev", url: "http://localhost:3000/explorar", reuseExistingServer: true, timeout: 180_000 },
  ],
});
