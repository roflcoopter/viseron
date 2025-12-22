import { Page } from "@playwright/test";
import { test } from "e2e/playwright.setup";

test("Screenshot cameras page", async ({ page }: { page: Page }) => {
  await page.goto("/");
  await page.waitForSelector('text="Camera 1"');
  await page.screenshot({
    path: "../docs/static/img/ui/cameras/main.png",
    fullPage: true,
  });
});
