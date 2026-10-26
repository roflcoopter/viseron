import { Locator, Page, expect, test } from "@playwright/test";

// The app awaits worker.start() before rendering, so its own requests are
// always mocked. A raw fetch issued from the test can still outrun the service
// worker taking control, so wait for it explicitly.
const waitForServiceWorker = async (page: Page) => {
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
};

test("renders the cameras page against the mocked backend", async ({
  page,
}: {
  page: Page;
}) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
});

test("renders entities from the mocked websocket", async ({
  page,
}: {
  page: Page;
}) => {
  await page.goto("/#/entities", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByText("binary_sensor.camera1_object_detected"),
  ).toBeVisible();
});

test("shows the demo mode banner", async ({ page }: { page: Page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByText("Demo | Data is mocked, nothing is saved"),
  ).toBeVisible();
});

test("serves mocked camera snapshots", async ({ page }: { page: Page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await waitForServiceWorker(page);

  // Fetched from inside the page so the request passes through the service
  // worker. Playwright's request context would bypass it entirely.
  const snapshot = await page.evaluate(async () => {
    const response = await fetch("/api/v1/camera/camera1/snapshot");
    return {
      status: response.status,
      contentType: response.headers.get("Content-Type"),
      byteLength: (await response.arrayBuffer()).byteLength,
    };
  });

  expect(snapshot.status).toBe(200);
  expect(snapshot.contentType).toBe("image/jpeg");
  expect(snapshot.byteLength).toBeGreaterThan(0);
});

test("renders the mocked snapshots on the camera cards", async ({
  page,
}: {
  page: Page;
}) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const snapshots = page.locator('img[src*="/snapshot?"]');
  await expect(snapshots).toHaveCount(3);

  // naturalWidth is only non-zero once the browser has decoded the response,
  // so this fails if the endpoint serves anything that is not a real image.
  await expect
    .poll(async () =>
      snapshots.evaluateAll<boolean[], void, HTMLImageElement>((images) =>
        images.map((image) => image.complete && image.naturalWidth > 0),
      ),
    )
    .toEqual([true, true, true]);
});

test("renders the mocked thumbnails on the recording cards", async ({
  page,
}: {
  page: Page;
}) => {
  // A poster has no load state to poll, so check the response it requested.
  const thumbnail = page.waitForResponse(/\/files\/tier1\/thumbnails\//);
  await page.goto("/#/recordings", { waitUntil: "domcontentloaded" });

  const response = await thumbnail;
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("image/jpeg");
});

const currentTime = (video: Locator) =>
  video.evaluate((element: HTMLVideoElement) => element.currentTime);

test("plays a mocked recording", async ({ page }: { page: Page }) => {
  await page.goto("/#/recordings", { waitUntil: "domcontentloaded" });

  await page.getByTestId("player-play-pause-button").first().click();

  // currentTime only advances once the browser has decoded the segments.
  await expect
    .poll(() => currentTime(page.locator("video").first()))
    .toBeGreaterThan(0);
});

test("plays the mocked events timeline", async ({ page }: { page: Page }) => {
  const timestamp = Math.floor(Date.now() / 1000);
  await page.goto(`/#/events?tab=timeline&timestamp=${timestamp}`, {
    waitUntil: "domcontentloaded",
  });
  const video = page.locator("video").first();

  // The player seeks to the requested timestamp before it starts playing.
  await expect.poll(() => currentTime(video)).toBeGreaterThan(0);
  const start = await currentTime(video);

  await expect.poll(() => currentTime(video)).toBeGreaterThan(start + 5);
});
