import Box from "@mui/material/Box";
import DOMPurify from "dompurify";
import Hls from "hls.js";
import { memo, useEffect, useRef } from "react";

import { TICK_HEIGHT, getYPosition } from "components/events/timeline/utils";
import { dateToTimestamp, getTimeFromDate } from "lib/helpers";

const useTimeUpdate = (
  hlsRef: React.MutableRefObject<Hls | null>,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
  ref: React.MutableRefObject<HTMLDivElement | null>,
  timeRef: React.MutableRefObject<HTMLDivElement | null>,
) => {
  useEffect(() => {
    const onTimeUpdate = () => {
      if (!hlsRef.current) {
        return;
      }
      const currentTime = hlsRef.current.media?.currentTime;
      if (!currentTime) {
        return;
      }
      if (hlsRef.current.playingDate && containerRef.current) {
        const playingTimestamp = dateToTimestamp(hlsRef.current.playingDate);
        const bounds = containerRef.current.getBoundingClientRect();
        const top = `${Math.floor(
          getYPosition(
            startRef.current,
            endRef.current,
            playingTimestamp,
            bounds.height,
          ) +
            TICK_HEIGHT / 2,
        )}px`;
        const innerHTML = DOMPurify.sanitize(
          getTimeFromDate(hlsRef.current.playingDate),
        );
        if (timeRef.current && innerHTML !== timeRef.current.innerHTML) {
          timeRef.current.innerHTML = innerHTML;
        }
        if (ref.current) {
          if (top !== ref.current.style.top) {
            ref.current.style.top = top;
          }
          ref.current.style.display = "block";
          ref.current.style.width = `${containerRef.current.offsetWidth}px`;
        }
      }
    };

    const interval = setInterval(() => {
      if (hlsRef.current) {
        hlsRef.current.media?.addEventListener("timeupdate", onTimeUpdate);
        clearInterval(interval);
      }
    }, 1000);

    const hls = hlsRef.current;
    return () => {
      if (hls) {
        hls.media?.removeEventListener("timeupdate", onTimeUpdate);
      }
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [containerRef, endRef, hlsRef, ref, startRef, timeRef]);
};

const useWidthObserver = (
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  ref: React.MutableRefObject<HTMLDivElement | null>,
) => {
  const resizeObserver = useRef<ResizeObserver>();
  useEffect(() => {
    if (containerRef.current) {
      resizeObserver.current = new ResizeObserver(() => {
        ref.current!.style.width = `${containerRef.current!.offsetWidth}px`;
      });
      resizeObserver.current.observe(containerRef.current);
    }
    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [containerRef, ref]);
};

type ProgressLineProps = {
  containerRef: React.MutableRefObject<HTMLDivElement | null>;
  hlsRef: React.MutableRefObject<Hls | null>;
  startRef: React.MutableRefObject<number>;
  endRef: React.MutableRefObject<number>;
};
export const ProgressLine = memo(
  ({ containerRef, hlsRef, startRef, endRef }: ProgressLineProps) => {
    const ref = useRef<HTMLInputElement | null>(null);
    const timeRef = useRef<HTMLInputElement | null>(null);

    useTimeUpdate(hlsRef, containerRef, startRef, endRef, ref, timeRef);
    useWidthObserver(containerRef, ref);

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          display: "none", // Hide div initially
          pointerEvents: "none",
          position: "absolute",
          width: `${
            containerRef.current ? containerRef.current.offsetWidth : 0
          }px`,
          height: "1px",
          backgroundColor: theme.palette.text.secondary,
          zIndex: 90,
          transition: "top 0.2s linear",
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
            backgroundColor: theme.palette.primary[900],
            fontSize: "0.7rem",
          })}
        ></Box>
      </Box>
    );
  },
);
