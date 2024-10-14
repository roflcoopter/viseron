import Box from "@mui/material/Box";
import dayjs from "dayjs";
import DOMPurify from "dompurify";
import { memo, useEffect, useRef } from "react";

import { getDateAtPosition } from "components/events/utils";
import { dateToTimestamp, getTimeFromDate } from "lib/helpers";

const useSetPosition = (
  ref: React.MutableRefObject<HTMLInputElement | null>,
  timeRef: React.MutableRefObject<HTMLInputElement | null>,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => {
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
      const top = e.clientY + window.scrollY;

      const dateAtCursor = getDateAtPosition(
        y,
        bounds.height,
        startRef,
        endRef,
      );
      if (dateToTimestamp(dateAtCursor) > dayjs().unix()) {
        return;
      }
      const timeAtCursor = getTimeFromDate(dateAtCursor);

      // Position the line and display the time
      if (ref.current) {
        ref.current.style.top = `${top}px`;
        ref.current.style.width = `${bounds.width}px`;
      }
      if (timeRef.current && timeRef.current.innerHTML !== timeAtCursor) {
        timeRef.current.innerHTML = DOMPurify.sanitize(timeAtCursor);
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
  }, [containerRef, endRef, ref, startRef, timeRef]);
};

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
    const timeRef = useRef<HTMLInputElement | null>(null);

    useSetPosition(ref, timeRef, containerRef, startRef, endRef);

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          display: "none",
          pointerEvents: "none",
          position: "absolute",
          width: "350px",
          height: "1px",
          backgroundColor: theme.palette.primary.main,
          zIndex: 100,
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
        ></Box>
      </Box>
    );
  },
);
