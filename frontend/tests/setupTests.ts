/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./mocks/server";

configure({ asyncUtilTimeout: 5000 });

// Start the server before all tests
beforeAll(() => {
  server.listen({ onUnhandledFrame: "warn" });
});

// Reset handlers after each test to avoid test interference
afterEach(() => server.resetHandlers());

// Close the server after all tests
afterAll(() => server.close()); // codespell-ignore

// Mock ResizeObserver for tests since it is not available in the test environment
class ResizeObserverMock {
  observe = vitest.fn();

  unobserve = vitest.fn();

  disconnect = vitest.fn();
}

global.ResizeObserver = ResizeObserverMock as typeof ResizeObserver;

export {};
