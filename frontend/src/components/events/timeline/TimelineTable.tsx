import { VirtualItem, useVirtualizer } from "@tanstack/react-virtual";
import dayjs, { Dayjs } from "dayjs";
import { memo, useEffect, useRef, useState } from "react";

import {
  ActivityLine,
  ActivityLineProps,
} from "components/events/timeline/ActivityLine";
import { HoverLine } from "components/events/timeline/HoverLine";
import { ObjectEvent } from "components/events/timeline/ObjectEvent";
import { TimeTick } from "components/events/timeline/TimeTick";
import { Loading } from "components/loading/Loading";
import queryClient from "lib/api/client";
import { useEvents } from "lib/api/events";
import { useHlsAvailableTimespans } from "lib/api/hls";
import { dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

export const TICK_HEIGHT = 8;
export const SCALE = 60;
export const EXTRA_TICKS = 10;

type TimelineItem = {
  time: number;
  timedEvent: null | types.CameraMotionEvent | types.CameraRecordingEvent;
  snapshotEvent: null | types.CameraObjectEvent;
  availableTimespan: null | types.HlsAvailableTimespan;
  timespanVariant: "first" | "middle" | "last" | "round" | null;
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

const activityLine = (
  startRef: React.MutableRefObject<number>,
  item: TimelineItem,
  index: number,
) => {
  const { time, timedEvent, availableTimespan } = item;

  if (timedEvent || availableTimespan) {
    let startTimestamp = 0;
    let endTimestamp = 0;
    if (timedEvent) {
      startTimestamp = timedEvent.start_timestamp;
      endTimestamp = timedEvent.end_timestamp || dayjs().unix();
    }
    if (availableTimespan) {
      startTimestamp = availableTimespan.start;
      endTimestamp = availableTimespan.end || dayjs().unix();
    }
    const indexStart = Math.round((startRef.current - endTimestamp) / SCALE);
    const indexEnd = Math.round((startRef.current - startTimestamp) / SCALE);
    let variant: ActivityLineProps["variant"] = null;
    if (indexStart === indexEnd) {
      variant = "round";
    } else if (indexStart === index) {
      variant = "first";
    } else if (indexEnd === index) {
      variant = "last";
    } else if (indexStart < index && index < indexEnd) {
      variant = "middle";
    }

    return (
      <ActivityLine
        key={`line-${time}`}
        active={variant !== null}
        cameraEvent={timedEvent}
        variant={variant}
        availableTimespan={item.availableTimespan !== null}
      />
    );
  }

  return (
    <ActivityLine
      key={`line-${time}`}
      active={false}
      cameraEvent={null}
      variant={null}
      availableTimespan={false}
    />
  );
};

const objectEvent = (item: TimelineItem) => {
  const { time, snapshotEvent } = item;
  if (snapshotEvent === null) {
    return null;
  }
  return <ObjectEvent key={`object-${time}`} objectEvent={snapshotEvent} />;
};

// Generate initial timeline with no event data
// Implemented as a hook instead of initial state to quickly show the Loading Timeline message
const useInitialTimeline = (
  startRef: React.MutableRefObject<number>,
  end: number,
  setItems: React.Dispatch<React.SetStateAction<TimelineItem[]>>,
) => {
  useEffect(() => {
    let timeTick = startRef.current;
    const items: TimelineItem[] = [];
    while (timeTick >= end) {
      items.push({
        time: timeTick,
        timedEvent: null,
        snapshotEvent: null,
        availableTimespan: null,
        timespanVariant: null,
      });
      timeTick -= SCALE;
    }
    setItems(items);
    // Should only run once on initial render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
};

// Add timeticks every SCALE seconds
const useAddTicks = (
  date: Dayjs | null,
  startRef: React.MutableRefObject<number>,
  setItems: React.Dispatch<React.SetStateAction<TimelineItem[]>>,
) => {
  const timeout = useRef<NodeJS.Timeout>();

  useEffect(() => {
    // If date is not today, don't add ticks
    if (!date || !date.isSame(dayjs(), "day")) {
      return () => {};
    }
    const addTicks = (ticksToAdd: number) => {
      let timeTick = 0;
      setItems((prevItems) => {
        timeTick = prevItems[0].time;
        const newItems = [...prevItems];
        for (let i = 0; i < ticksToAdd; i++) {
          timeTick += SCALE;
          newItems.unshift({
            time: timeTick,
            timedEvent: null,
            snapshotEvent: null,
            availableTimespan: null,
            timespanVariant: null,
          });
        }
        return newItems;
      });
      startRef.current = timeTick;
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
  }, [date, setItems, startRef]);
};

// Update timeline with event data
const useUpdateTimeline = (
  startRef: React.MutableRefObject<number>,
  eventsData: types.CameraEvent[],
  availableTimespansData: types.HlsAvailableTimespan[],
  setItems: React.Dispatch<React.SetStateAction<TimelineItem[]>>,
) => {
  useEffect(() => {
    if (eventsData.length === 0 && availableTimespansData.length === 0) {
      return;
    }

    setItems((prevItems) => {
      const newItems = [...prevItems];

      // Loop over available HLS files
      availableTimespansData.forEach((timespan) => {
        const indexStart = Math.round(
          (startRef.current - (timespan.end || dayjs().unix())) / SCALE,
        );
        const indexEnd = Math.round(
          (startRef.current - timespan.start) / SCALE,
        );
        if (indexStart === indexEnd) {
          newItems[indexStart] = {
            ...newItems[indexStart],
            availableTimespan: timespan,
            timespanVariant: "round",
          };
          return;
        }
        newItems[indexStart] = {
          ...newItems[indexStart],
          availableTimespan: timespan,
          timespanVariant: "first",
        };
        newItems[indexEnd] = {
          ...newItems[indexEnd],
          availableTimespan: timespan,
          timespanVariant: "last",
        };
        for (let i = indexStart + 1; i < indexEnd; i++) {
          newItems[i] = {
            ...newItems[i],
            availableTimespan: timespan,
            timespanVariant: "middle",
          };
        }
      });

      // Loop over events where type is motion or recording
      eventsData
        .filter(
          (cameraEvent): cameraEvent is types.CameraTimedEvents =>
            cameraEvent.type === "motion" || cameraEvent.type === "recording",
        )
        .forEach((cameraEvent) => {
          const indexStart = Math.round(
            (startRef.current - (cameraEvent.end_timestamp || dayjs().unix())) /
              SCALE,
          );
          const indexEnd = Math.round(
            (startRef.current - cameraEvent.start_timestamp) / SCALE,
          );
          if (indexStart === indexEnd) {
            newItems[indexStart] = {
              ...newItems[indexStart],
              timedEvent: cameraEvent,
            };
            return;
          }
          newItems[indexStart] = {
            ...newItems[indexStart],
            timedEvent: cameraEvent,
          };
          newItems[indexEnd] = {
            ...newItems[indexEnd],
            timedEvent: cameraEvent,
          };
          for (let i = indexStart + 1; i < indexEnd; i++) {
            newItems[i] = {
              ...newItems[i],
              timedEvent: cameraEvent,
            };
          }
        });
      // Loop over events where type is object
      eventsData
        .filter(
          (cameraEvent): cameraEvent is types.CameraObjectEvent =>
            cameraEvent.type === "object",
        )
        .forEach((cameraEvent) => {
          const indexStart = Math.round(
            (startRef.current - cameraEvent.timestamp) / SCALE,
          );
          newItems[indexStart] = {
            ...newItems[indexStart],
            snapshotEvent: cameraEvent,
          };
        });
      return newItems;
    });

    /// Run only when eventsData or availableTimespansData changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsData, availableTimespansData]);
};

const itemEqual = (
  prevItem: Readonly<ItemProps>,
  nextItem: Readonly<ItemProps>,
) =>
  prevItem.item.time === nextItem.item.time &&
  prevItem.item.timespanVariant === nextItem.item.timespanVariant &&
  prevItem.item.timedEvent?.start_timestamp ===
    nextItem.item.timedEvent?.start_timestamp &&
  prevItem.item.timedEvent?.end_timestamp ===
    nextItem.item.timedEvent?.end_timestamp &&
  prevItem.item.snapshotEvent?.timestamp ===
    nextItem.item.snapshotEvent?.timestamp;

type ItemProps = {
  startRef: React.MutableRefObject<number>;
  virtualItem: VirtualItem;
  item: TimelineItem;
};
const Item = memo(
  ({ startRef, virtualItem, item }: ItemProps): JSX.Element => (
    <>
      <TimeTick key={`tick-${item.time}`} time={item.time} />
      {activityLine(startRef, item, virtualItem.index)}
      {objectEvent(item)}
    </>
  ),
  itemEqual,
);

type RowProps = {
  startRef: React.MutableRefObject<number>;
  virtualItem: VirtualItem;
  item: TimelineItem;
};
const Row = memo(({ startRef, virtualItem, item }: RowProps): JSX.Element => {
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
          // eslint-disable-next-line no-nested-ternary
          item.snapshotEvent && hover ? 999 : item.snapshotEvent ? 998 : 1,
      }}
    >
      <Item startRef={startRef} virtualItem={virtualItem} item={item} />
    </div>
  );
});

type VirtualListProps = {
  parentRef: React.MutableRefObject<HTMLDivElement | null>;
  items: TimelineItem[];
  startRef: React.MutableRefObject<number>;
};
const VirtualList = memo(
  ({ parentRef, items, startRef }: VirtualListProps): JSX.Element => {
    const rowVirtualizer = useVirtualizer({
      count: items.length,
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
        {rowVirtualizer.getVirtualItems().map((virtualItem) => (
          <Row
            key={`item-${items[virtualItem.index].time}`}
            startRef={startRef}
            virtualItem={virtualItem}
            item={items[virtualItem.index]}
          />
        ))}
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
    const firstRenderRef = useRef(true);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const startRef = useRef<number>(calculateStart(date));
    const endRef = useRef<number>(calculateEnd(date));

    const [items, setItems] = useState<TimelineItem[]>([]);
    const eventsQuery = useEvents({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
    });
    const eventsData = eventsQuery.data?.events || [];
    const availableTimespansQuery = useHlsAvailableTimespans({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
    });
    const availableTimespansData =
      availableTimespansQuery.data?.timespans || [];

    // Generate initial timeline with no event data
    useInitialTimeline(startRef, endRef.current, setItems);
    // Add timeticks every SCALE seconds
    useAddTicks(date, startRef, setItems);
    // Update timeline with event data
    useUpdateTimeline(startRef, eventsData, availableTimespansData, setItems);

    if (eventsQuery.isLoading && firstRenderRef.current) {
      return <Loading text="Loading Timeline" fullScreen={false} />;
    }
    firstRenderRef.current = false;
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
        <VirtualList parentRef={parentRef} items={items} startRef={startRef} />
      </div>
    );
  },
);
