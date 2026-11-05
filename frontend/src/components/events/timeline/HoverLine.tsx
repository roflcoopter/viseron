import Box from "@mui/material/Box";
import { memo, useEffect, useRef } from "react";

import { getDateAtPosition } from "components/events/utils";
import { getDayjs, getTimeStringFromDayjs } from "lib/helpers/dates";

const useSetPosition = (
  ref: React.MutableRefObject<HTMLDivElement | null>,
  timeRef: React.MutableRefObject<HTMLDivElement | null>,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => {
  // Listen to mouse move event on the container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return () => {};
    const boundsRef = {
      current: container.getBoundingClientRect(),
    };
    let cursorY: number | null = null;

    const updateBounds = () => {
      const bounds = container.getBoundingClientRect();
      boundsRef.current = bounds;
      if (ref.current) {
        ref.current.style.left = `${bounds.left}px`;
        ref.current.style.width = `${bounds.width}px`;
      }
    };
    updateBounds();
    const resizeObserver = new ResizeObserver(updateBounds);
    resizeObserver.observe(container);

    const updateLine = (clientY: number) => {
      const bounds = boundsRef.current;
      const y = clientY - bounds.top;
      if (y === 0) {
        return;
      }

      const dateAtCursor = getDateAtPosition(
        y,
        bounds.height,
        startRef,
        endRef,
      );
      if (dateAtCursor.unix() > getDayjs().unix()) {
        return;
      }
      const timeAtCursor = getTimeStringFromDayjs(dateAtCursor);

      // Position the line and display the time
      if (ref.current) {
        ref.current.style.transform = `translateY(${clientY}px)`;
      }
      if (timeRef.current && timeRef.current.textContent !== timeAtCursor) {
        timeRef.current.textContent = timeAtCursor;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      cursorY = e.clientY;
      updateLine(e.clientY);
    };

    const onMouseEnter = (e: MouseEvent) => {
      updateBounds();
      cursorY = e.clientY;
      if (ref.current) {
        ref.current.style.visibility = "visible";
      }
    };
    const onMouseLeave = (_e: MouseEvent) => {
      cursorY = null;
      if (ref.current) {
        ref.current.style.visibility = "hidden";
      }
    };

    const onScroll = () => {
      updateBounds();
      if (cursorY !== null) {
        updateLine(cursorY);
      }
    };

    container.addEventListener("mousemove", onMouseMove);
    container.addEventListener("mouseenter", onMouseEnter);
    container.addEventListener("mouseleave", onMouseLeave);
    // Capture to also see the scrolling of ancestors, since scroll does not bubble
    window.addEventListener("scroll", onScroll, {
      capture: true,
      passive: true,
    });
    window.addEventListener("resize", updateBounds);
    return () => {
      resizeObserver.disconnect();
      container.removeEventListener("mousemove", onMouseMove);
      container.removeEventListener("mouseenter", onMouseEnter);
      container.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", updateBounds);
    };
  }, [containerRef, endRef, ref, startRef, timeRef]);
};

/*
  For performance reasons, update the calculated time directly instead of using state.
*/
export const HoverLine = memo(
  ({
    containerRef,
    startRef,
    endRef,
  }: {
    containerRef: React.MutableRefObject<HTMLDivElement | null>;
    startRef: React.MutableRefObject<number>;
    endRef: React.MutableRefObject<number>;
  }) => {
    const ref = useRef<HTMLDivElement | null>(null);
    const timeRef = useRef<HTMLDivElement | null>(null);

    useSetPosition(ref, timeRef, containerRef, startRef, endRef);

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          visibility: "hidden",
          pointerEvents: "none",
          position: "fixed",
          top: 0,
          height: "1px",
          backgroundColor: theme.palette.primary.main,
          zIndex: 100,
          willChange: "transform",
        })}
      >
        <Box
          ref={timeRef}
          sx={(theme) => ({
            display: "inline-block",
            marginLeft: "2px",
            marginTop: "2px",
            padding: "2px 4px 2px 4px",
            width: "auto",
            borderRadius: "8px",
            color: "white",
            backgroundColor: theme.palette.primary.main,
            fontSize: "0.7rem",
          })}
        />
      </Box>
    );
  },
);
