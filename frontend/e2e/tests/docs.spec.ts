import { Page, expect } from "@playwright/test";
import { test } from "e2e/playwright.setup";

test("Screenshot cameras page", async ({ page }: { page: Page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Camera [0-9]/)).toHaveCount(3);
  await page.screenshot({
    path: "../docs/static/img/ui/cameras/main.png",
    fullPage: true,
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
