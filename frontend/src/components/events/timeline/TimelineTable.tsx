import dayjs, { Dayjs } from "dayjs";
import Hls from "hls.js";
import { memo, useContext, useEffect, useMemo, useRef, useState } from "react";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { HoverLine } from "components/events/timeline/HoverLine";
import { ProgressLine } from "components/events/timeline/ProgressLine";
import { VirtualList } from "components/events/timeline/VirtualList";
import {
  EXTRA_TICKS,
  SCALE,
  calculateEnd,
  calculateStart,
  getDateAtPosition,
  getTimelineItems,
  useFilterStore,
} from "components/events/utils";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { useEvents } from "lib/api/events";
import { useHlsAvailableTimespans } from "lib/api/hls";
import { dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

// Move startRef.current forward every SCALE seconds
const useAddTicks = (
  date: Dayjs | null,
  startRef: React.MutableRefObject<number>,
  setStart: React.Dispatch<React.SetStateAction<number>>,
) => {
  const { connected } = useContext(ViseronContext);
  const timeout = useRef<NodeJS.Timeout>();

  useEffect(() => {
    // If date is not today, don't add ticks
    if (!date || !date.isSame(dayjs(), "day")) {
      return () => {};
    }
    const addTicks = (ticksToAdd: number) => {
      if (!connected) {
        return;
      }
      let timeTick = 0;
      setStart((prevStart) => {
        timeTick = prevStart + ticksToAdd * SCALE;
        return timeTick;
      });
    };

    const recursiveTimeout = () => {
      const timeDiff =
        dayjs().unix() - (startRef.current - SCALE * EXTRA_TICKS);
      if (timeDiff >= SCALE) {
        const ticksToAdd = Math.floor(timeDiff / SCALE);
        addTicks(ticksToAdd);
      }
      timeout.current = setTimeout(recursiveTimeout, SCALE * 1000);
    };
    recursiveTimeout();
    return () => {
      if (timeout.current) {
        clearTimeout(timeout.current);
      }
    };
  }, [connected, date, setStart, startRef]);
};

const timelineClick = (
  event: React.MouseEvent<HTMLDivElement, MouseEvent>,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
  setRequestedTimestamp: (timestamp: number) => void,
) => {
  if (!containerRef.current) return;
  const bounds = containerRef.current.getBoundingClientRect();
  const y = event.clientY - bounds.top;

  const timestamp = dateToTimestamp(
    getDateAtPosition(y, bounds.height, startRef, endRef),
  );
  if (timestamp > dayjs().unix()) {
    return;
  }

  // Position the line and display the time
  setRequestedTimestamp(timestamp);
};

type TimelineTableProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  hlsRef: React.MutableRefObject<Hls | null>;
  camera: types.Camera | types.FailedCamera;
  date: Dayjs | null;
  setRequestedTimestamp: (timestamp: number | null) => void;
};
export const TimelineTable = memo(
  ({
    parentRef,
    hlsRef,
    camera,
    date,
    setRequestedTimestamp,
  }: TimelineTableProps) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const startRef = useRef<number>(calculateStart(date));
    const endRef = useRef<number>(calculateEnd(date));

    // Add timeticks every SCALE seconds
    // Components mostly use startRef.current for performance reasons,
    // but the state is used to trigger a re-render when the time changes
    const [start, setStart] = useState<number>(startRef.current);
    useAddTicks(date, startRef, setStart);
    startRef.current = start;

    const eventsQuery = useEvents({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
      configOptions: {
        keepPreviousData: true,
      },
    });
    const availableTimespansQuery = useHlsAvailableTimespans({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
      configOptions: {
        keepPreviousData: true,
      },
    });

    const { filters } = useFilterStore();
    const timelineItems = useMemo(
      () =>
        getTimelineItems(
          startRef,
          eventsQuery.data?.events || [],
          availableTimespansQuery.data?.timespans || [],
          filters,
        ),
      [eventsQuery.data, availableTimespansQuery.data, filters],
    );

    if (eventsQuery.error || availableTimespansQuery.error) {
      const subtext = eventsQuery.error
        ? eventsQuery.error.message
        : availableTimespansQuery.error
          ? availableTimespansQuery.error.message
          : "Unknown error";
      return (
        <ErrorMessage
          text={"Error loading events and/or timespans"}
          subtext={subtext}
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }
    if (
      eventsQuery.isInitialLoading ||
      availableTimespansQuery.isInitialLoading
    ) {
      return <Loading text="Loading Timeline" fullScreen={false} />;
    }

    return (
      <div
        ref={containerRef}
        onClick={(event) =>
          timelineClick(
            event,
            containerRef,
            startRef,
            endRef,
            setRequestedTimestamp,
          )
        }
      >
        <div style={{ position: "relative" }}>
          <ProgressLine
            containerRef={containerRef}
            startRef={startRef}
            endRef={endRef}
            hlsRef={hlsRef}
          />
        </div>
        <HoverLine
          containerRef={containerRef}
          startRef={startRef}
          endRef={endRef}
        />
        <VirtualList
          parentRef={parentRef}
          startRef={startRef}
          endRef={endRef}
          timelineItems={timelineItems}
        />
      </div>
    );
  },
);
