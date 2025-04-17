/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import {
  afterAll, // codespell-ignore
  afterEach,
  beforeAll,
} from "vitest";

import { server } from "./mocks/server";

// Start the server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" });
});

// Reset handlers after each test to avoid test interference
afterEach(() => server.resetHandlers());

// Close the server after all tests
afterAll(() => server.close()); // codespell-ignore

export {};
