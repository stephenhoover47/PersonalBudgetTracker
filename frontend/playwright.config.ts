import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  projects: [
    { name: "desktop", grep: /desktop:/ },
    { name: "iphone", grep: /iphone:/ },
  ],
  fullyParallel: false,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    browserName: "chromium",
    launchOptions: process.env.CHROMIUM_PATH
      ? {
          executablePath: process.env.CHROMIUM_PATH,
          args: [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--single-process",
            "--no-zygote",
            "--disable-gpu",
            "--disable-software-rasterizer",
          ],
        }
      : {},
  },
  webServer: {
    command: `${process.env.PYTHON || "python"} ../backend/tests/e2e_server.py`,
    url: "http://127.0.0.1:8765/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
