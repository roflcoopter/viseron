import { render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VirtualList } from "components/events/timeline/VirtualList";

vi.mock("components/events/timeline/Row", () => ({
  Row: () => <div data-testid="row" />,
}));

function Parent() {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const startRef = useRef(3600);
  const endRef = useRef(0);
  return (
    <div ref={parentRef}>
      <VirtualList
        parentRef={parentRef}
        startRef={startRef}
        endRef={endRef}
        timelineItems={{}}
      />
    </div>
  );
}

describe("VirtualList", () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(100);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders rows when mounted in the same commit as its scroll element", () => {
    render(<Parent />);

    expect(screen.getAllByTestId("row").length).toBeGreaterThan(0);
  });
});
