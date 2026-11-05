import { ThemeProvider, createTheme } from "@mui/material/styles";
import { render } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it, vi } from "vitest";

import { Layout } from "components/events/Layouts";
import { getDayjs } from "lib/helpers/dates";

const panelHeights = vi.hoisted(() => ({ timeline: null as string | null }));

vi.mock("components/camera/useCameraStore", () => ({
  useFilteredCameras: () => ({ camera1: {} }),
}));
vi.mock("components/events/FilterMenu", () => ({ FilterMenu: () => null }));
vi.mock("components/events/FloatingMenu", () => ({ FloatingMenu: () => null }));
vi.mock("components/events/PlayerCard", () => ({ PlayerCard: () => null }));
vi.mock("components/events/events/EventTable", () => ({
  EventTable: () => null,
}));
vi.mock("components/events/timeline/TimelineTable", () => ({
  TimelineTable: function TimelineTable({
    parentRef,
  }: {
    parentRef: React.RefObject<HTMLDivElement | null>;
  }) {
    // Runs when VirtualList would look for its scroll element after mounting
    useEffect(() => {
      panelHeights.timeline = parentRef.current!.style.height;
    }, [parentRef]);
    return null;
  },
}));

describe("Layout", () => {
  it("sizes the panel before the children read its height on mount", () => {
    render(
      <ThemeProvider theme={createTheme({ headerHeight: 56 })}>
        <Layout
          date={getDayjs()}
          setDate={() => {}}
          selectedTab="timeline"
          setSelectedTab={() => {}}
        />
      </ThemeProvider>,
    );

    expect(panelHeights.timeline).toContain("dvh");
  });
});
