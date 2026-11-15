import { defineConfig } from "@playwright/test";

// E2E contra la API y la web reales (plan §16). Usa Microsoft Edge instalado (canal msedge): sin descargar navegadores.
// Si los servidores ya están levantados (p. ej. desde .claude/launch.json) se reutilizan.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 60_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    channel: "msedge",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
  },
  webServer: [
    {
      command: "..\\api\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../api --port 8000",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    { command: "npm run dev", url: "http://localhost:3000/explorar", reuseExistingServer: true, timeout: 120_000 },
  ],
});
