import { VirtualItem, useVirtualizer } from "@tanstack/react-virtual";
import dayjs, { Dayjs } from "dayjs";
import { memo, useContext, useEffect, useMemo, useRef, useState } from "react";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { ActivityLine } from "components/events/timeline/ActivityLine";
import { HoverLine } from "components/events/timeline/HoverLine";
import { ObjectEvent } from "components/events/timeline/ObjectEvent";
import { TimeTick } from "components/events/timeline/TimeTick";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import queryClient from "lib/api/client";
import { useEvents } from "lib/api/events";
import { useHlsAvailableTimespans } from "lib/api/hls";
import { dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

export const TICK_HEIGHT = 8;
export const SCALE = 5;
export const EXTRA_TICKS = 10;
const DEFAULT_ITEM: TimelineItem = {
  time: 0,
  timedEvent: null,
  snapshotEvent: null,
  availableTimespan: null,
  activityLineVariant: null,
};

type TimelineItem = {
  time: number;
  timedEvent: null | types.CameraMotionEvent | types.CameraRecordingEvent;
  snapshotEvent: null | types.CameraObjectEvent;
  availableTimespan: null | types.HlsAvailableTimespan;
  activityLineVariant: "first" | "middle" | "last" | "round" | null;
};

type TimelineItems = {
  [key: string]: TimelineItem;
};

const round = (num: number) => Math.ceil(num / SCALE) * SCALE;

// Calculate the start time of the timeline, called on first render
const calculateStart = (date: Dayjs | null) => {
  if (!date) {
    return round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS);
  }
  // if date is today, start at current time
  if (date.isSame(dayjs(), "day")) {
    return round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS);
  }
  // Otherwise start at midnight the next day
  return dateToTimestamp(
    new Date(date.add(1, "day").toDate().setHours(0, 0, 0, 0)),
  );
};

// Calculate the end time of the timeline, called on first render
const calculateEnd = (date: Dayjs | null) =>
  dateToTimestamp(
    date
      ? new Date(date.toDate().setHours(0, 0, 0, 0))
      : new Date(new Date().setHours(0, 0, 0, 0)),
  );

// Calculate the number of items to render in the virtual list
const calculateItemCount = (
  startRef: React.MutableRefObject<number>,
  endRef: React.MutableRefObject<number>,
) => (startRef.current - endRef.current) / SCALE + 1;

// Calculate the time from the index
const calculateTimeFromIndex = (
  startRef: React.MutableRefObject<number>,
  index: number,
) => startRef.current - index * SCALE;

const calculateIndexFromTime = (
  startRef: React.MutableRefObject<number>,
  timestamp: number | null,
) => Math.round((startRef.current - (timestamp || dayjs().unix())) / SCALE);

// Common logic for items that affect the activity line
const createActivityLineItem = (
  startRef: React.MutableRefObject<number>,
  indexStart: number,
  indexEnd: number,
  event: types.CameraEvent | types.HlsAvailableTimespan,
  eventType: "availableTimespan" | "timedEvent",
) => {
  const timelineItems: TimelineItems = {};

  let time = calculateTimeFromIndex(startRef, indexStart);
  timelineItems[time] = {
    ...DEFAULT_ITEM,
    time,
    [eventType]: event,
    activityLineVariant: indexStart === indexEnd ? "round" : "first",
  };

  if (indexStart !== indexEnd) {
    time = calculateTimeFromIndex(startRef, indexEnd);
    timelineItems[time] = {
      ...DEFAULT_ITEM,
      time,
      [eventType]: event,
      activityLineVariant: "last",
    };

    for (let i = indexStart + 1; i < indexEnd; i++) {
      time = calculateTimeFromIndex(startRef, i);
      timelineItems[time] = {
        ...DEFAULT_ITEM,
        time,
        [eventType]: event,
        activityLineVariant: "middle",
      };
    }
  }

  return timelineItems;
};

// Get the timeline items from the events and available timespans
const getTimelineItems = (
  startRef: React.MutableRefObject<number>,
  eventsData: types.CameraEvent[],
  availableTimespansData: types.HlsAvailableTimespan[],
) => {
  let timelineItems: TimelineItems = {};

  // Loop over available HLS files
  availableTimespansData.forEach((timespan) => {
    const indexEnd = calculateIndexFromTime(startRef, timespan.start);
    const indexStart = calculateIndexFromTime(startRef, timespan.end);

    timelineItems = {
      ...timelineItems,
      ...createActivityLineItem(
        startRef,
        indexStart,
        indexEnd,
        timespan,
        "availableTimespan",
      ),
    };
  });

  // Loop over events where type is motion or recording
  eventsData
    .filter(
      (cameraEvent): cameraEvent is types.CameraTimedEvents =>
        cameraEvent.type === "motion" || cameraEvent.type === "recording",
    )
    // Create a copy of the array and sort it by type
    .slice()
    .sort((cameraEvent, _) => (cameraEvent.type === "recording" ? 1 : -1))
    .forEach((cameraEvent) => {
      const indexEnd = calculateIndexFromTime(
        startRef,
        cameraEvent.start_timestamp,
      );
      const indexStart = calculateIndexFromTime(
        startRef,
        cameraEvent.end_timestamp,
      );

      timelineItems = {
        ...timelineItems,
        ...createActivityLineItem(
          startRef,
          indexStart,
          indexEnd,
          cameraEvent,
          "timedEvent",
        ),
      };
    });

  // Loop over events where type is object
  eventsData
    .filter(
      (cameraEvent): cameraEvent is types.CameraObjectEvent =>
        cameraEvent.type === "object",
    )
    .forEach((cameraEvent) => {
      const index = calculateIndexFromTime(startRef, cameraEvent.timestamp);
      const time = calculateTimeFromIndex(startRef, index);
      timelineItems[time] = {
        ...DEFAULT_ITEM,
        ...timelineItems[time],
        time,
        snapshotEvent: cameraEvent,
      };
    });

  return timelineItems;
};

const getItem = (time: number, items: TimelineItems) =>
  time.toString() in items ? items[time] : { ...DEFAULT_ITEM, time };

// Move startRef.current forward every SCALE seconds
const useAddTicks = (
  date: Dayjs | null,
  startRef: React.MutableRefObject<number>,
) => {
  const { connected } = useContext(ViseronContext);
  const [_, setStart] = useState<number>(startRef.current);
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
        startRef.current = timeTick;
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

const itemEqual = (
  prevItem: Readonly<ItemProps>,
  nextItem: Readonly<ItemProps>,
) =>
  prevItem.item.time === nextItem.item.time &&
  prevItem.item.availableTimespan === nextItem.item.availableTimespan &&
  prevItem.item.activityLineVariant === nextItem.item.activityLineVariant &&
  prevItem.item.timedEvent?.start_timestamp ===
    nextItem.item.timedEvent?.start_timestamp &&
  prevItem.item.timedEvent?.end_timestamp ===
    nextItem.item.timedEvent?.end_timestamp &&
  prevItem.item.snapshotEvent?.timestamp ===
    nextItem.item.snapshotEvent?.timestamp;

type ItemProps = {
  item: TimelineItem;
};
const Item = memo(
  ({ item }: ItemProps): JSX.Element => (
    <>
      <TimeTick key={`tick-${item.time}`} time={item.time} />
      <ActivityLine
        key={`line-${item.time}`}
        active={!!item.activityLineVariant}
        cameraEvent={item.timedEvent}
        variant={item.activityLineVariant}
        availableTimespan={!!item.availableTimespan}
      />
      {item.snapshotEvent ? (
        <ObjectEvent
          key={`object-${item.time}`}
          objectEvent={item.snapshotEvent}
        />
      ) : null}
    </>
  ),
  itemEqual,
);

const rowEqual = (prevItem: Readonly<RowProps>, nextItem: Readonly<RowProps>) =>
  prevItem.virtualItem === nextItem.virtualItem &&
  itemEqual({ item: prevItem.item }, { item: nextItem.item });

type RowProps = {
  virtualItem: VirtualItem;
  item: TimelineItem;
};
const Row = memo(({ virtualItem, item }: RowProps): JSX.Element => {
  const [hover, setHover] = useState(false);

  return (
    <div
      key={item.time}
      onMouseEnter={() => {
        if (!item.snapshotEvent) {
          return;
        }
        setHover(true);
      }}
      onMouseLeave={() => {
        if (!item.snapshotEvent) {
          return;
        }
        setHover(false);
      }}
      style={{
        display: "flex",
        justifyContent: "start",
        position: "absolute",
        top: 0,
        left: 0,
        height: `${virtualItem.size}px`,
        width: "100%",
        transform: `translateY(${virtualItem.start}px)`,
        transition: "transform 0.2s linear",
        zIndex:
          item.snapshotEvent && hover ? 999 : item.snapshotEvent ? 998 : 1,
      }}
    >
      <Item item={item} />
    </div>
  );
}, rowEqual);

type VirtualListProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  startRef: React.MutableRefObject<number>;
  endRef: React.MutableRefObject<number>;
  timelineItems: TimelineItems;
};
const VirtualList = memo(
  ({
    parentRef,
    startRef,
    endRef,
    timelineItems,
  }: VirtualListProps): JSX.Element => {
    const rowVirtualizer = useVirtualizer({
      count: calculateItemCount(startRef, endRef),
      getScrollElement: () => parentRef!.current,
      estimateSize: () => TICK_HEIGHT,
      overscan: 10,
    });

    return (
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          position: "relative",
          width: "100%",
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualItem) => {
          const time = calculateTimeFromIndex(startRef, virtualItem.index);
          const item = getItem(time, timelineItems);
          return (
            <Row
              key={`item-${item.time}`}
              virtualItem={virtualItem}
              item={item}
            />
          );
        })}
      </div>
    );
  },
);

type TimelineTableProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  camera: types.Camera;
  date: Dayjs | null;
  setSource: (source: string | null) => void;
};
export const TimelineTable = memo(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ({ parentRef, camera, date, setSource }: TimelineTableProps) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const startRef = useRef<number>(calculateStart(date));
    const endRef = useRef<number>(calculateEnd(date));

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
    const timelineItems = useMemo(
      () =>
        getTimelineItems(
          startRef,
          eventsQuery.data?.events || [],
          availableTimespansQuery.data?.timespans || [],
        ),
      [eventsQuery.data, availableTimespansQuery.data],
    );

    // Add timeticks every SCALE seconds
    useAddTicks(date, startRef);

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
        onClick={() => queryClient.invalidateQueries(["events"])}
      >
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
