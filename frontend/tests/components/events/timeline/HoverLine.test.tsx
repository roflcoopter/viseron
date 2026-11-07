import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoverLine } from "components/events/timeline/HoverLine";
import { getDateAtPosition } from "components/events/utils";
import { getDayjs, getTimeStringFromDayjs } from "lib/helpers/dates";

const createContainer = (top: number) => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const getBounds = vi
    .spyOn(container, "getBoundingClientRect")
    .mockReturnValue({ top, height: 1000 } as DOMRect);
  return { container, getBounds };
};

const renderLine = (container: HTMLDivElement) => {
  const now = getDayjs().unix();
  const startRef = { current: now };
  const endRef = { current: now - 3600 };
  const { container: root } = render(
    <HoverLine
      containerRef={{ current: container }}
      startRef={startRef}
      endRef={endRef}
    />,
  );
  const line = root.firstElementChild as HTMLElement;
  const timeAt = (y: number) =>
    getTimeStringFromDayjs(getDateAtPosition(y, 1000, startRef, endRef));
  return { line, timeAt };
};

describe("HoverLine", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("follows the cursor without reading the layout on each move", () => {
    const { container, getBounds } = createContainer(100);
    const { line } = renderLine(container);
    fireEvent.mouseEnter(container);
    getBounds.mockClear();

    fireEvent.mouseMove(container, { clientY: 150 });
    fireEvent.mouseMove(container, { clientY: 160 });

    expect(line.style.transform).toBe("translateY(160px)");
    expect(line.style.visibility).toBe("visible");
    expect(line.textContent).not.toBe("");
    expect(getBounds).not.toHaveBeenCalled();
  });

  it("stays under the cursor and updates the time when an ancestor scrolls", () => {
    const { container, getBounds } = createContainer(100);
    const { line, timeAt } = renderLine(container);
    const scroller = document.createElement("div");
    document.body.appendChild(scroller);
    fireEvent.mouseEnter(container, { clientY: 150 });
    fireEvent.mouseMove(container, { clientY: 150 });
    expect(line.textContent).toBe(timeAt(50));

    getBounds.mockReturnValue({ top: -100, height: 1000 } as DOMRect);
    fireEvent.scroll(scroller);

    expect(line.style.transform).toBe("translateY(150px)");
    expect(line.textContent).toBe(timeAt(250));
  });

  it("does not update the time on scroll when the cursor is elsewhere", () => {
    const { container, getBounds } = createContainer(100);
    const { line } = renderLine(container);
    const scroller = document.createElement("div");
    document.body.appendChild(scroller);
    fireEvent.mouseEnter(container, { clientY: 150 });
    fireEvent.mouseMove(container, { clientY: 150 });
    fireEvent.mouseLeave(container);
    const time = line.textContent;

    getBounds.mockReturnValue({ top: -100, height: 1000 } as DOMRect);
    fireEvent.scroll(scroller);

    expect(line.textContent).toBe(time);
  });

  it("aligns horizontally with the container", () => {
    const { container, getBounds } = createContainer(100);
    getBounds.mockReturnValue({
      top: 100,
      height: 1000,
      left: 20,
      width: 300,
    } as DOMRect);
    const { line } = renderLine(container);

    expect(line.style.left).toBe("20px");
    expect(line.style.width).toBe("300px");
  });

  it("hides when the cursor leaves", () => {
    const { container } = createContainer(100);
    const { line } = renderLine(container);

    fireEvent.mouseEnter(container);
    fireEvent.mouseLeave(container);

    expect(line.style.visibility).toBe("hidden");
  });
});
