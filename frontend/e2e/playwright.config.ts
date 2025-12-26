import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    locale: "en-US",
    timezoneId: "UTC",
    video: "off",
  },
  expect: {
    timeout: 10000,
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
