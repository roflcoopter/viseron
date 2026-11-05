import { act, render } from "@testing-library/react";
import Hls from "hls.js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProgressLine } from "components/events/timeline/ProgressLine";
import { getYPosition, useReferencePlayerStore } from "components/events/utils";

describe("ProgressLine", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    useReferencePlayerStore.setState({ referencePlayer: null });
    vi.useRealTimers();
  });

  it("follows the playing date without reading the layout on each update", () => {
    const start = 2000;
    const end = 1000;
    const media = Object.assign(new EventTarget(), { currentTime: 5 });
    useReferencePlayerStore.setState({
      referencePlayer: {
        media,
        playingDate: new Date(1500 * 1000),
      } as unknown as Hls,
    });
    const container = document.createElement("div");
    const getBounds = vi
      .spyOn(container, "getBoundingClientRect")
      .mockReturnValue({ height: 1000 } as DOMRect);
    const { container: root } = render(
      <ProgressLine
        containerRef={{ current: container }}
        startRef={{ current: start }}
        endRef={{ current: end }}
      />,
    );
    const line = root.firstElementChild as HTMLElement;
    // The player's media is attached by polling
    act(() => {
      vi.advanceTimersByTime(100);
    });
    getBounds.mockClear();

    media.dispatchEvent(new Event("timeupdate"));
    media.dispatchEvent(new Event("timeupdate"));

    const y = Math.floor(getYPosition(start, end, 1500, 1000));
    expect(line.style.transform).toBe(`translateY(${y}px)`);
    expect(line.style.visibility).toBe("visible");
    expect(line.textContent).not.toBe("");
    expect(getBounds).not.toHaveBeenCalled();
  });
});
