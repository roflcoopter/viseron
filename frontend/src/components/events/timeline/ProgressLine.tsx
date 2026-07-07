import Box from "@mui/material/Box";
import Hls from "hls.js";
import { memo, useEffect, useRef } from "react";

import { getYPosition, useReferencePlayerStore } from "components/events/utils";
import { getDayjsFromDate, getTimeStringFromDayjs } from "lib/helpers/dates";

const useTimeUpdate = (
  hls: Hls | null,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  containerHeightRef: React.MutableRefObject<number>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
  ref: React.MutableRefObject<HTMLDivElement | null>,
  timeRef: React.MutableRefObject<HTMLDivElement | null>,
) => {
  useEffect(() => {
    if (!hls) {
      return () => {};
    }
    const onTimeUpdate = () => {
      if (!hls) {
        return;
      }
      const currentTime = hls.media?.currentTime;
      if (!currentTime) {
        return;
      }
      if (hls.playingDate && containerRef.current) {
        const playingTimestamp = getDayjsFromDate(hls.playingDate).unix();
        const containerHeight = containerHeightRef.current;
        if (containerHeight <= 0) {
          return;
        }
        const y = Math.floor(
          getYPosition(
            startRef.current,
            endRef.current,
            playingTimestamp,
            containerHeight,
          ),
        );
        const transform = `translateY(${y}px)`;
        const timeText = getTimeStringFromDayjs(
          getDayjsFromDate(hls.playingDate),
        );
        if (timeRef.current && timeText !== timeRef.current.textContent) {
          timeRef.current.textContent = timeText;
        }
        if (ref.current) {
          if (transform !== ref.current.style.transform) {
            ref.current.style.transform = transform;
          }
          ref.current.style.visibility = "visible";
        }
      }
    };

    const interval = setInterval(() => {
      if (hls) {
        hls.media?.addEventListener("timeupdate", onTimeUpdate);
        clearInterval(interval);
      }
    }, 100);

    return () => {
      if (hls) {
        hls.media?.removeEventListener("timeupdate", onTimeUpdate);
      }
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [containerHeightRef, containerRef, endRef, hls, ref, startRef, timeRef]);
};

const useContainerHeightObserver = (
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
) => {
  const heightRef = useRef(0);
  const resizeObserver = useRef<ResizeObserver>(undefined);
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      heightRef.current = container.getBoundingClientRect().height;
      resizeObserver.current = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (entry) {
          heightRef.current = entry.contentRect.height;
        }
      });
      resizeObserver.current.observe(container);
    }
    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [containerRef]);
  return heightRef;
};

type ProgressLineProps = {
  containerRef: React.MutableRefObject<HTMLDivElement | null>;
  startRef: React.MutableRefObject<number>;
  endRef: React.MutableRefObject<number>;
};
export const ProgressLine = memo(
  ({ containerRef, startRef, endRef }: ProgressLineProps) => {
    const ref = useRef<HTMLDivElement | null>(null);
    const timeRef = useRef<HTMLDivElement | null>(null);
    const hls = useReferencePlayerStore((state) => state.referencePlayer);
    const containerHeightRef = useContainerHeightObserver(containerRef);

    useTimeUpdate(
      hls,
      containerRef,
      containerHeightRef,
      startRef,
      endRef,
      ref,
      timeRef,
    );

    return (
      <Box
        ref={ref}
        sx={(theme) => ({
          visibility: "hidden", // Hide div initially
          pointerEvents: "none",
          position: "absolute",
          left: 0,
          right: 0,
          height: "1px",
          backgroundColor: theme.palette.primary[900],
          zIndex: 90,
          transition: "transform 0.2s linear",
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
            backgroundColor: theme.palette.primary[900],
            fontSize: "0.7rem",
          })}
        />
      </Box>
    );
  },
);
