import { Page, expect, test } from "@playwright/test";

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
