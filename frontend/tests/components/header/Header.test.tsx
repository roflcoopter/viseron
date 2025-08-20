import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test } from "vitest";

import AppHeader from "components/header/Header";

describe("Loading Component", () => {
  test("renders app header with auth", () => {
    const { getByRole } = renderWithContext(<AppHeader />);
    expect(
      getByRole("button", {
        name: "Logout",
      }),
    ).toBeDefined();
  });

  test("renders app header without auth", () => {
    const { queryByRole } = renderWithContext(<AppHeader />, {
      auth: { enabled: false, onboarding_complete: false },
      user: null,
    });
    expect(
      queryByRole("button", {
        name: "Logout",
      }),
    ).toBeNull();
  });
});
