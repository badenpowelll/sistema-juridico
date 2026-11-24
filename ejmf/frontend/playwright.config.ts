import { defineConfig, devices } from "@playwright/test";

/**
 * E2E real: sobe a API (FastAPI) num banco descartável ejmf_e2e e o Next em modo produção.
 * Pré-requisito: PostgreSQL acessível em EJMF_E2E_DB_ADMIN (padrão: o contêiner de desenvolvimento na porta 5433).
 */
const API_PORTA = 8010;
const WEB_PORTA = 3010;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${WEB_PORTA}`, trace: "off", locale: "pt-BR", timezoneId: "America/Fortaleza" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "celular", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `bash ../scripts/e2e-api.sh ${API_PORTA}`,
      url: `http://localhost:${API_PORTA}/api/v1/saude`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `EJMF_API_INTERNA=http://localhost:${API_PORTA} npx next build && npx next start -p ${WEB_PORTA}`,
      url: `http://localhost:${WEB_PORTA}/entrar`,
      reuseExistingServer: false,
      timeout: 300_000,
    },
  ],
});
