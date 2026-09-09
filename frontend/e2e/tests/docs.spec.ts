import { Page, expect } from "@playwright/test";
import {
  test,
  waitForCameraSnapshots,
  waitForPlayButtons,
  waitForSyntaxHighlighting,
} from "e2e/playwright.setup";
import { resetSetupStatusMock, setupStatusMock } from "tests/mocks/wsHandlers";
import { MOCK_SETUP_STATUS_COMPONENTS } from "tests/utils/const";

const SCREENSHOT_OPTIONS = { fullPage: true, timeout: 15000 } as const;

test.describe("Screenshot cameras page", () => {
  test.beforeEach(async ({ page }: { page: Page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
    await waitForCameraSnapshots(page);
  });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await expect(page).toHaveScreenshot(
      ["cameras", "main.png"],
      SCREENSHOT_OPTIONS,
    );
  });

  test("camera toggle button screenshot", async ({ page }: { page: Page }) => {
    // Add a green highlight border around the camera toggle button
    const cameraToggleButton = page.getByTestId("camera-toggle-button").first();
    await cameraToggleButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });
    await expect(page).toHaveScreenshot(
      ["cameras", "camera-toggle-button.png"],
      SCREENSHOT_OPTIONS,
    );
  });
});

test("Screenshot recordings page", async ({ page }: { page: Page }) => {
  await page.goto("/#/recordings", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
  await expect(page.getByText(/Latest recording/)).toHaveCount(2);
  await waitForCameraSnapshots(page);
  // Camera 1 and 2 have recordings, camera 3 does not
  await waitForPlayButtons(page, 2);
  await expect(page).toHaveScreenshot(
    ["recordings", "main.png"],
    SCREENSHOT_OPTIONS,
  );
});

test.describe("Screenshot live page", () => {
  test.beforeEach(async ({ page }: { page: Page }) => {
    await page.goto("/#/live", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
    await waitForCameraSnapshots(page);
  });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await expect(page).toHaveScreenshot(
      ["live", "main.png"],
      SCREENSHOT_OPTIONS,
    );
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

    await expect(page).toHaveScreenshot(
      ["live", "manual-recording-button.png"],
      SCREENSHOT_OPTIONS,
    );
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
    await expect(page).toHaveScreenshot(
      ["live", "context-menu.png"],
      SCREENSHOT_OPTIONS,
    );
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
    await waitForCameraSnapshots(page);
    await expect(page).toHaveScreenshot(
      ["tune", "main.png"],
      SCREENSHOT_OPTIONS,
    );
  });

  test("camera tuning button screenshot", async ({ page }: { page: Page }) => {
    // Add a green highlight border around the camera tuning button
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await waitForCameraSnapshots(page);
    const cameraTuningButton = page.getByTestId("camera-tuning-button").first();
    await cameraTuningButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });
    await expect(page).toHaveScreenshot(
      ["tune", "camera-tuning-button.png"],
      SCREENSHOT_OPTIONS,
    );
  });
});

test.describe("Screenshot profile page", () => {
  test.use({ viewport: { width: 1440, height: 1200 } });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.goto("/#/profile", { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/Profile/)).toHaveCount(1);
    await expect(page.getByText(/Test User/)).toHaveCount(1);
    await expect(page).toHaveScreenshot(
      ["profile", "main.png"],
      SCREENSHOT_OPTIONS,
    );
  });
});

test.describe("Screenshot config editor page", () => {
  test.beforeEach(async ({ page }: { page: Page }) => {
    await page.goto("/#/settings/configuration", {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByText(/ffmpeg/)).toHaveCount(1);
    await waitForSyntaxHighlighting(page);
  });
  test.afterEach(async () => {
    // Reset the setup status mock to its default state after each test
    resetSetupStatusMock();
  });

  test("main view screenshot", async ({ page }: { page: Page }) => {
    await expect(page).toHaveScreenshot(
      ["config", "main.png"],
      SCREENSHOT_OPTIONS,
    );
  });

  test("config editor reload button screenshot", async ({
    page,
  }: {
    page: Page;
  }) => {
    // Add a green highlight border around the config editor reload button
    const reloadButton = page
      .getByTestId("config-editor-reload-button")
      .first();
    await reloadButton.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "3px";
    });

    await expect(page).toHaveScreenshot(
      ["config", "reload-button.png"],
      SCREENSHOT_OPTIONS,
    );
  });

  test("config editor YAML syntax error screenshot", async ({
    page,
  }: {
    page: Page;
  }) => {
    // Introduce a YAML syntax error by deleting a colon from the config
    const editor = page.locator(".monaco-editor");
    await editor.click();
    await page.keyboard.press("PageUp");
    await page.keyboard.press("ControlOrMeta+F");
    await page.keyboard.type("viseron_camera2");
    await page.keyboard.press("Escape");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Backspace");
    await page.waitForTimeout(1000);

    // Add a green highlight border around the YAML syntax error markers list
    const markersList = page.getByTestId("config-editor-markers-list");
    await markersList.waitFor({ state: "visible" });
    await markersList.evaluate((el) => {
      el.style.outline = "3px solid #00ff00";
      el.style.outlineOffset = "-3px";
    });

    await expect(page).toHaveScreenshot(
      ["config", "yaml-syntax-error.png"],
      SCREENSHOT_OPTIONS,
    );
  });

  test("setup errors sidebar screenshot", async ({ page }: { page: Page }) => {
    // Show example errors covering every source type the sidebar handles
    setupStatusMock.components = MOCK_SETUP_STATUS_COMPONENTS;
    // Reload the page to trigger the setup status update
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForSyntaxHighlighting(page);

    await expect(page).toHaveScreenshot(
      ["config", "setup-errors.png"],
      SCREENSHOT_OPTIONS,
    );
  });
});

test.describe("Screenshot logs page", () => {
  test("main view screenshot", async ({ page }: { page: Page }) => {
    await page.goto("/#/settings/logs", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("System Logs")).toBeVisible();
    await expect(
      page.getByText(/Starting webserver on port 8888/).first(),
    ).toBeVisible();
    await expect(page).toHaveScreenshot(
      ["logs", "main.png"],
      SCREENSHOT_OPTIONS,
    );
  });
});
