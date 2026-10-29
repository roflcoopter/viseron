import { defineConfig, devices } from "@playwright/test";
import { FIXED_TIME } from "e2e/const";

process.env.PLAYWRIGHT_FIXED_TIME = FIXED_TIME;

export default defineConfig({
  testDir: "./tests",
  // demo.spec.ts targets the mocked demo build and has its own config.
  testIgnore: "demo.spec.ts",
  fullyParallel: true,
  // Resolved relative to this files location
  snapshotPathTemplate: "../../docs/static/img/ui/{arg}{ext}",
  updateSnapshots: process.env.CI ? "none" : "changed",
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    locale: "en-US",
    timezoneId: "UTC",
    video: "off",
  },
  expect: {
    timeout: 30000,
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.001,
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run start",
    cwd: "../",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    stdout: "pipe",
  },
});
