import { VirtualItem, useVirtualizer } from "@tanstack/react-virtual";
import dayjs from "dayjs";
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
import { dateToTimestamp } from "lib/helpers";
import * as types from "lib/types";

export const TICK_HEIGHT = 8;
export const SCALE = 60;
export const EXTRA_TICKS = 10;

const round = (num: number) => Math.ceil(num / SCALE) * SCALE;

const activityLine = (
  startRef: React.MutableRefObject<number>,
  item: TimelineItem,
  index: number,
) => {
  const { time, timedEvent } = item;

  if (timedEvent === null) {
    return (
      <ActivityLine
        key={`line-${time}`}
        active={false}
        cameraEvent={null}
        variant={null}
      />
    );
  }

  const indexStart = Math.round(
    (startRef.current - (timedEvent.end_timestamp || dayjs().unix())) / SCALE,
  );
  const indexEnd = Math.round(
    (startRef.current - timedEvent.start_timestamp) / SCALE,
  );

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
    />
  );
};

const objectEvent = (item: TimelineItem, index: number) => {
  const { time, snapshotEvent } = item;
  if (snapshotEvent === null) {
    return null;
  }
  return (
    <ObjectEvent
      key={`object-${time}`}
      objectEvent={snapshotEvent}
      eventIndex={index}
    />
  );
};

type ItemProps = {
  startRef: React.MutableRefObject<number>;
  virtualItem: VirtualItem;
  item: TimelineItem;
};
const Item = memo(
  ({ startRef, virtualItem, item }: ItemProps): JSX.Element => (
    <div
      key={item.time}
      style={{
        display: "flex",
        justifyContent: "start",
        position: "absolute",
        top: 0,
        left: 0,
        height: `${virtualItem.size}px`,
        width: "100%",
        transform: `translateY(${virtualItem.start}px)`,
        zIndex: item.snapshotEvent ? 999 : 1,
      }}
    >
      <TimeTick key={`tick-${item.time}`} time={item.time} />
      {activityLine(startRef, item, virtualItem.index)}
      {objectEvent(item, virtualItem.index)}
    </div>
  ),
);

type TimelineItem = {
  startRef: React.MutableRefObject<number>;
  time: number;
  timedEvent: null | types.CameraMotionEvent | types.CameraRecordingEvent;
  snapshotEvent: null | types.CameraObjectEvent;
};

// Generate initial timeline with no event data
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
        startRef,
        time: timeTick,
        timedEvent: null,
        snapshotEvent: null,
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
  startRef: React.MutableRefObject<number>,
  setItems: React.Dispatch<React.SetStateAction<TimelineItem[]>>,
) => {
  const timeout = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const addTicks = (ticksToAdd: number) => {
      setItems((prevItems) => {
        const newItems = [...prevItems];
        let timeTick = startRef.current;
        for (let i = 0; i < ticksToAdd; i++) {
          timeTick += SCALE;
          newItems.unshift({
            startRef,
            time: timeTick,
            timedEvent: null,
            snapshotEvent: null,
          });
        }

        startRef.current = timeTick;
        return newItems;
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
  }, [setItems, startRef]);
};

// Update timeline with event data
const useUpdateTimeline = (
  startRef: React.MutableRefObject<number>,
  eventsData: types.CameraEvent[],
  setItems: React.Dispatch<React.SetStateAction<TimelineItem[]>>,
) => {
  useEffect(() => {
    if (eventsData.length === 0) {
      return;
    }

    setItems((prevItems) => {
      const newItems = [...prevItems];
      // Loop over events where type is motion
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

    /// Run only when eventsData changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventsData]);
};

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
          <Item
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
  setSource: (source: string | null) => void;
};
export const TimelineTable = memo(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ({ parentRef, camera, setSource }: TimelineTableProps) => {
    const firstRenderRef = useRef(true);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const startRef = useRef<number>(
      round(dateToTimestamp(new Date()) + SCALE * EXTRA_TICKS),
    );
    const endRef = useRef<number>(
      dateToTimestamp(new Date(new Date().setHours(0, 0, 0, 0))),
    );
    const [items, setItems] = useState<TimelineItem[]>([]);
    const eventsQuery = useEvents({
      camera_identifier: camera.identifier,
      time_from: endRef.current,
      time_to: startRef.current,
      configOptions: {
        notifyOnChangeProps: ["data"],
      },
    });
    const eventsData = eventsQuery.data?.events || [];

    // Generate initial timeline with no event data
    useInitialTimeline(startRef, endRef.current, setItems);
    // Add timeticks every SCALE seconds
    useAddTicks(startRef, setItems);
    // Update timeline with event data
    useUpdateTimeline(startRef, eventsData, setItems);

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
