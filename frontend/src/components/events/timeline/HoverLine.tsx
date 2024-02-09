import Box from "@mui/material/Box";
import dayjs from "dayjs";
import DOMPurify from "dompurify";
import { memo, useEffect, useRef } from "react";

import { dateToTimestamp, getTimeFromDate } from "lib/helpers";

import { SCALE } from "./TimelineTable";

/*
  For performance reasons, we update the calculated time with innerHTML instead of using state.
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
    const ref = useRef<HTMLInputElement | null>(null);

    // Listen to mouse move event on the container
    useEffect(() => {
      const container = containerRef.current;
      if (!container) return () => {};

      const onMouseMove = (e: MouseEvent) => {
        const bounds = container.getBoundingClientRect();
        const y = e.clientY - bounds.top;
        if (y === 0) {
          return;
        }
        const top = e.clientY;
        // Calculate the percentage of cursor position within the container
        const percentage = y / bounds.height;

        // First time tick is preceded by a margin of half the time tick height
        // so we add half the scale to get the correct time
        const _start = startRef.current * 1000 + (SCALE * 1000) / 2;
        // Last time tick is followed by a margin of half the time tick height
        // so we subtract half the scale to get the correct time
        const _end = endRef.current * 1000 - (SCALE * 1000) / 2;
        // Calculate the time difference in milliseconds between start and end dates
        const timeDifference = _end - _start;

        // Calculate the time corresponding to the cursor position
        const dateAtCursor = new Date(_start + percentage * timeDifference);
        if (dateToTimestamp(dateAtCursor) > dayjs().unix()) {
          return;
        }
        const timeAtCursor = getTimeFromDate(dateAtCursor);

        // Position the line and display the time
        if (ref.current) {
          ref.current.style.top = `${top}px`;
          ref.current.style.width = `${bounds.width}px`;
        }
        if (ref.current && ref.current.innerHTML !== timeAtCursor) {
          ref.current.innerHTML = DOMPurify.sanitize(timeAtCursor);
        }
      };

      const onMouseEnter = (_e: MouseEvent) => {
        if (ref.current) {
          ref.current.style.display = "block";
        }
      };
      const onMouseLeave = (_e: MouseEvent) => {
        if (ref.current) {
          ref.current.style.display = "none";
        }
      };

      container.addEventListener("mousemove", onMouseMove);
      container.addEventListener("mouseenter", onMouseEnter);
      container.addEventListener("mouseleave", onMouseLeave);
      return () => {
        container.removeEventListener("mousemove", onMouseMove);
        container.removeEventListener("mouseenter", onMouseEnter);
        container.removeEventListener("mouseleave", onMouseLeave);
      };
    }, [containerRef, endRef, ref, startRef]);

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          display: "none",
          pointerEvents: "none",
          position: "absolute",
          width: "350px",
          height: "1px",
          backgroundColor: theme.palette.divider,
          textShadow: "rgba(0, 0, 0, 0.88) 0px 0px 4px",
          fontSize: "0.7rem",
          zIndex: 100,
        })}
      ></Box>
    );
  },
);
