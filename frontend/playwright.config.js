import { defineConfig } from "@playwright/test";

const sharedServer = {
  reuseExistingServer: !process.env.CI,
  timeout: 30_000,
  stdout: "pipe",
  stderr: "pipe",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 7_500 },
  reporter: [["line"]],
  use: {
    browserName: "chromium",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      ...sharedServer,
      command: "node server.js --port 3101 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3101/runtime-config.js",
      env: {
        FRONTEND_DATA_MODE: "mock",
        FRONTEND_STUDY_MODE: "C1_MANUAL",
        FRONTEND_STUDY_ORDER: "C1_MANUAL,C2_VERIFY_ALL",
      },
    },
    {
      ...sharedServer,
      command: "node server.js --port 3102 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3102/runtime-config.js",
      env: {
        FRONTEND_DATA_MODE: "mock",
        FRONTEND_STUDY_MODE: "C2_VERIFY_ALL",
        FRONTEND_STUDY_ORDER: "C2_VERIFY_ALL,C1_MANUAL",
      },
    },
    {
      ...sharedServer,
      command: "node server.js --port 3103 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3103/runtime-config.js",
      env: { FRONTEND_DATA_MODE: "api" },
    },
  ],
});
