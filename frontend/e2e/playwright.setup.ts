import { type NetworkFixture, createNetworkFixture } from "@msw/playwright";
import { test as testBase } from "@playwright/test";
import { API_BASE_URL, handlers } from "tests/mocks/handlers";
import { wsHandlers } from "tests/mocks/wsHandlers";

interface Fixtures {
  network: NetworkFixture;
}

export const test = testBase.extend<Fixtures>({
  network: createNetworkFixture({
    initialHandlers: [...handlers, ...wsHandlers],
  }),
});

test.beforeEach(async ({ page, context }) => {
  // Listen to console logs
  page.on("console", (msg) => console.log(`[console] ${msg.text()}`));

  // Log network responses
  page.on("response", (res) => {
    if (res.url().includes(API_BASE_URL) || res.url().includes("/files/"))
      console.log(
        `[response] ${res.status()} ${res.url()} (${res.request().method()})`,
      );
  });

  // Set cookies for spoofin authentication
  await context.addCookies([
    {
      name: "user",
      value: "123456789",
      path: "/",
      domain: "localhost",
      httpOnly: false,
    },
  ]);
});
