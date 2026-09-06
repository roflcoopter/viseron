import { defineConfig, devices } from "@playwright/test";

// Exercises the production demo build: the app is served from dist/ and mocked
// by the MSW service worker, with no @msw/playwright fixture involved.
export default defineConfig({
  testDir: "./tests",
  testMatch: "demo.spec.ts",
  fullyParallel: true,
  use: {
    baseURL: "http://localhost:4173",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    locale: "en-US",
    timezoneId: "UTC",
    video: "off",
  },
  expect: {
    timeout: 30000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run build && npm run serve -- --port 4173 --strictPort",
    cwd: "../",
    url: "http://localhost:4173",
    env: { VITE_MOCK_API: "true" },
    reuseExistingServer: false,
    timeout: 180000,
    stdout: "pipe",
  },
});
