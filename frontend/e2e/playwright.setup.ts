import { type NetworkFixture, defineNetworkFixture } from "@msw/playwright";
import { Page, expect, test as testBase } from "@playwright/test";
import { FIXED_TIME } from "e2e/const";
import { API_BASE_URL, createHandlers } from "tests/mocks/handlers";
import { nodeSnapshotLoader } from "tests/mocks/nodeSnapshotLoader";
import { wsHandlers } from "tests/mocks/wsHandlers";

interface Fixtures {
  network: NetworkFixture;
}

export const test = testBase.extend<Fixtures>({
  network: [
    async ({ context }, use) => {
      const network = defineNetworkFixture({
        context,
        handlers: [...createHandlers(nodeSnapshotLoader), ...wsHandlers],
      });

      await network.enable();
      await use(network);
      await network.disable();
    },
    { auto: true },
  ],
});

test.beforeEach(async ({ page, context }) => {
  await page.clock.setFixedTime(new Date(FIXED_TIME));

  // Listen to console logs
  page.on("console", (msg) => console.log(`[console] ${msg.text()}`));

  // Log network responses
  page.on("response", (res) => {
    if (res.url().includes(API_BASE_URL) || res.url().includes("/files/"))
      console.log(
        `[response] ${res.status()} ${res.url()} (${res.request().method()})`,
      );
  });

  // Set cookies for spoofing authentication
  await context.addCookies([
    {
      name: "user",
      value: "123456789",
      path: "/",
      domain: "localhost",
      httpOnly: false,
    },
  ]);

  // Set selected cameras in local storage
  await page.addInitScript(() => {
    localStorage.setItem(
      "camera-store",
      JSON.stringify({
        state: {
          cameras: {
            camera1: true,
            camera2: true,
            camera3: true,
          },
          selectedCameras: ["camera1", "camera2", "camera3"],
          selectionOrder: ["camera1", "camera2", "camera3"],
        },
        version: 0,
      }),
    );
  });
});

// Camera cards render a placeholder until the snapshot request resolves, then swap in
// an <img>. Capturing before every image has decoded produces a different screenshot
// on every run.
export async function waitForCameraSnapshots(page: Page) {
  await expect(page.getByTestId("camera-snapshot-loading")).toHaveCount(0);
  await page.waitForFunction(() =>
    Array.from(document.images).every(
      (img) => img.complete && img.naturalWidth > 0,
    ),
  );
}

// The video players are lazy loaded, so the play buttons rendering is delayed.
//  It also fades in, which puts it in the DOM before it is actually painted,
// so wait for the fade to have finished as well.
export async function waitForPlayButtons(page: Page, count: number) {
  await expect(page.getByTestId("player-play-pause-button")).toHaveCount(count);
  await page.waitForFunction(
    (expected) =>
      Array.from(
        document.querySelectorAll('[data-testid="player-play-pause-button"]'),
      ).filter((button) => {
        for (let el: Element | null = button; el; el = el.parentElement) {
          if (Number(getComputedStyle(el).opacity) < 1) return false;
        }
        return true;
      }).length === expected,
    count,
  );
}

// Monaco renders text with the default `mtk1` class until the language
// tokenizer has loaded.
// More than one token class in use means YAML syntax highlighting has loaded.
export async function waitForSyntaxHighlighting(page: Page) {
  await page.waitForFunction(() => {
    const tokenClasses = new Set<string>();
    document
      .querySelectorAll(".monaco-editor .view-line span")
      .forEach((span) => {
        span.classList.forEach((cls) => {
          if (/^mtk\d+$/.test(cls)) tokenClasses.add(cls);
        });
      });
    return tokenClasses.size > 1;
  });
}
