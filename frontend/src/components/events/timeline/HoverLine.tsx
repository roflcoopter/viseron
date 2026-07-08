import Box from "@mui/material/Box";
import { memo, useEffect, useRef } from "react";

import { getDateAtPosition } from "components/events/utils";
import { getDayjs, getTimeStringFromDayjs } from "lib/helpers/dates";

const useSetPosition = (
  ref: React.MutableRefObject<HTMLDivElement | null>,
  timeRef: React.MutableRefObject<HTMLDivElement | null>,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  parentRef: React.MutableRefObject<HTMLDivElement | null>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => {
  // Listen to mouse move event on the container
  useEffect(() => {
    const container = containerRef.current;
    const parent = parentRef.current;
    if (!container) return () => {};
    const boundsRef = {
      current: container.getBoundingClientRect(),
    };
    const updateBounds = () => {
      boundsRef.current = container.getBoundingClientRect();
    };
    const resizeObserver = new ResizeObserver(updateBounds);
    resizeObserver.observe(container);

    const onMouseMove = (e: MouseEvent) => {
      const bounds = boundsRef.current;
      const y = e.clientY - bounds.top;
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
        ref.current.style.transform = `translateY(${y}px)`;
      }
      if (timeRef.current && timeRef.current.textContent !== timeAtCursor) {
        timeRef.current.textContent = timeAtCursor;
      }
    };

    const onMouseEnter = (_e: MouseEvent) => {
      updateBounds();
      if (ref.current) {
        ref.current.style.visibility = "visible";
      }
    };
    const onMouseLeave = (_e: MouseEvent) => {
      if (ref.current) {
        ref.current.style.visibility = "hidden";
      }
    };

    container.addEventListener("mousemove", onMouseMove);
    container.addEventListener("mouseenter", onMouseEnter);
    container.addEventListener("mouseleave", onMouseLeave);
    parent?.addEventListener("scroll", updateBounds, { passive: true });
    window.addEventListener("resize", updateBounds);
    return () => {
      resizeObserver.disconnect();
      container.removeEventListener("mousemove", onMouseMove);
      container.removeEventListener("mouseenter", onMouseEnter);
      container.removeEventListener("mouseleave", onMouseLeave);
      parent?.removeEventListener("scroll", updateBounds);
      window.removeEventListener("resize", updateBounds);
    };
  }, [containerRef, endRef, parentRef, ref, startRef, timeRef]);
};

/*
  For performance reasons, update the calculated time directly instead of using state.
*/
export const HoverLine = memo(
  ({
    containerRef,
    parentRef,
    startRef,
    endRef,
  }: {
    containerRef: React.MutableRefObject<HTMLDivElement | null>;
    parentRef: React.MutableRefObject<HTMLDivElement | null>;
    startRef: React.MutableRefObject<number>;
    endRef: React.MutableRefObject<number>;
  }) => {
    const ref = useRef<HTMLDivElement | null>(null);
    const timeRef = useRef<HTMLDivElement | null>(null);

    useSetPosition(ref, timeRef, containerRef, parentRef, startRef, endRef);

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          visibility: "hidden",
          pointerEvents: "none",
          position: "absolute",
          left: 0,
          right: 0,
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
