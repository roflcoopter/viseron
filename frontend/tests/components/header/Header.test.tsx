import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test } from "vitest";

import AppHeader from "components/header/Header";

describe("Loading Component", () => {
  test("renders app header with auth", () => {
    const setDrawerOpen = vi.fn();

    const { getByRole } = renderWithContext(
      <AppHeader setDrawerOpen={setDrawerOpen} />
    );
    expect(
      getByRole("button", {
        name: "Logout",
      })
    ).toBeDefined();
  });

  test("renders app header without auth", () => {
    const setDrawerOpen = vi.fn();

    const { queryByRole } = renderWithContext(
      <AppHeader setDrawerOpen={setDrawerOpen} />,
      { enabled: false, onboarding_complete: false }
    );
    expect(
      queryByRole("button", {
        name: "Logout",
      })
    ).toBeNull();
  });
});
