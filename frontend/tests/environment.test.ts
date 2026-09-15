import { describe, expect, test } from "vitest";

// Guards the execArgv workaround in vite.config.ts. Without it Node >= 22
// shadows jsdom's storage and every test touching localStorage throws.
describe("test environment", () => {
  test.each(["localStorage", "sessionStorage"] as const)(
    "%s is jsdom's Storage",
    (key) => {
      const storage = globalThis[key];

      expect(storage).toBeInstanceOf(Storage);

      storage.setItem("probe", "value");
      expect(storage.getItem("probe")).toBe("value");
      storage.removeItem("probe");
      expect(storage.getItem("probe")).toBeNull();
    },
  );
});
