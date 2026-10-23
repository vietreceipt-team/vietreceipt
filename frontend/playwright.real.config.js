import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-real", workers: 1, fullyParallel: false, timeout: 900_000,
  expect: {timeout: 15_000}, reporter: [["line"], ["json", {outputFile: "real-results/playwright.json"}]],
  outputDir: "real-results/browser", use: {
    baseURL: "http://127.0.0.1:3104", browserName: "chromium", headless: true,
    actionTimeout: 15_000, navigationTimeout: 30_000,
    viewport: {width: 1500, height: 1000}, screenshot: "only-on-failure", video: "on", trace: "retain-on-failure",
  },
  webServer: {
    command: "node server.js --port 3104 --hostname 127.0.0.1",
    url: "http://127.0.0.1:3104/runtime-config.js", reuseExistingServer: false,
    env: {FRONTEND_DATA_MODE: "api", BACKEND_API_ORIGIN: process.env.TV6_BACKEND_URL || "http://127.0.0.1:18000"},
  },
});
