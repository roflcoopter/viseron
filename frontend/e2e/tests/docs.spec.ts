import { Page, expect } from "@playwright/test";
import { test } from "e2e/playwright.setup";

test.describe("Screenshot cameras page", () => {
  test.beforeEach(async ({ page }: { page: Page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
  });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.screenshot({
      path: "../docs/static/img/ui/cameras/main.png",
      fullPage: true,
    });
  });

  test("camera toggle button screenshot", async ({ page }: { page: Page }) => {
    // Add a green highlight border around the camera toggle button
    const cameraToggleButton = page.getByTestId("camera-toggle-button").first();
    await cameraToggleButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });
    await page.screenshot({
      path: "../docs/static/img/ui/cameras/camera-toggle-button.png",
      fullPage: true,
    });
  });
});

test("Screenshot recordings page", async ({ page }: { page: Page }) => {
  await page.goto("/#/recordings", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
  await expect(page.getByText(/Latest recording/)).toHaveCount(2);
  await page.screenshot({
    path: "../docs/static/img/ui/recordings/main.png",
    fullPage: true,
  });
});

test.describe("Screenshot live page", () => {
  test.beforeEach(async ({ page }: { page: Page }) => {
    await page.goto("/#/live", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
  });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.screenshot({
      path: "../docs/static/img/ui/live/main.png",
      fullPage: true,
    });
  });

  test("manual recording button screenshot", async ({
    page,
  }: {
    page: Page;
  }) => {
    // Hover the first video player container to reveal custom controls
    await page.waitForSelector("video", { state: "visible" });
    await page
      .locator('[role="button"]:has(video)')
      .first()
      .hover({ force: true });
    await page.waitForTimeout(300);

    // Add a green highlight border around the manual recording button
    const recordingButton = page.getByTestId("manual-recording-button").first();
    await recordingButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });

    // Hover the button to reveal its tooltip
    await recordingButton.hover({ force: true });
    await page.waitForTimeout(300);

    await page.screenshot({
      path: "../docs/static/img/ui/live/manual-recording-button.png",
      fullPage: true,
    });
  });

  test("context menu screenshot", async ({ page }: { page: Page }) => {
    await page.waitForSelector("video", { state: "visible" });
    await page
      .locator('[role="button"]:has(video)')
      .first()
      .click({ button: "right", force: true });
    await page.waitForTimeout(300);

    // Add a green highlight border around the context menu
    const contextMenu = page
      .getByTestId("live-player-context-menu-paper")
      .first();
    await contextMenu.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });
    await page.screenshot({
      path: "../docs/static/img/ui/live/context-menu.png",
      fullPage: true,
    });
  });
});

test.describe("Screenshot tune page", () => {
  test.use({ viewport: { width: 1440, height: 1200 } });
  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.goto("/#/cameras/camera1", { waitUntil: "domcontentloaded" });
    // Wait for tune config to load (domain tabs appear)
    await expect(page.getByText("Object Detector")).toBeVisible();
    await expect(page.getByText("Motion Detector")).toBeVisible();

    // Click into the Object Detector > darknet tab to show more UI elements
    await page.getByText("Object Detector").click({ force: true });
    await page.getByText("darknet").click({ force: true });

    // Wait for the UI to update with the new tab content
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "../docs/static/img/ui/tune/main.png",
      fullPage: true,
    });
  });

  test("camera tuning button screenshot", async ({ page }: { page: Page }) => {
    // Add a green highlight border around the camera tuning button
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const cameraTuningButton = page.getByTestId("camera-tuning-button").first();
    await cameraTuningButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });
    await page.screenshot({
      path: "../docs/static/img/ui/tune/camera-tuning-button.png",
      fullPage: true,
    });
  });
});

test.describe("Screenshot profile page", () => {
  test.use({ viewport: { width: 1440, height: 1200 } });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.goto("/#/profile", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Profile/)).toHaveCount(1);
    await expect(page.getByText(/Test User/)).toHaveCount(1);
    await page.screenshot({
      path: "../docs/static/img/ui/profile/main.png",
      fullPage: true,
    });
  });
});
