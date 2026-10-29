import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DemoBanner from "components/DemoBanner";

const BANNER_TEXT = "Demo | Data is mocked, nothing is saved";

describe("DemoBanner", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the banner when VITE_MOCK_API is enabled", () => {
    vi.stubEnv("VITE_MOCK_API", "true");

    render(<DemoBanner />);

    expect(screen.getByText(BANNER_TEXT)).toBeInTheDocument();
  });

  it("renders nothing when VITE_MOCK_API is unset", () => {
    vi.stubEnv("VITE_MOCK_API", "");

    render(<DemoBanner />);

    expect(screen.queryByText(BANNER_TEXT)).not.toBeInTheDocument();
  });
});
