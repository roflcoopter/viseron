import { type NetworkFixture, createNetworkFixture } from "@msw/playwright";
import { test as testBase } from "@playwright/test";
import { handlers } from "tests/mocks/handlers";
import { wsHandlers } from "tests/mocks/wsHandlers";

interface Fixtures {
  network: NetworkFixture;
}

export const test = testBase.extend<Fixtures>({
  network: createNetworkFixture({
    initialHandlers: [...handlers, ...wsHandlers],
  }),
});

test.beforeEach(async ({ context }) => {
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
