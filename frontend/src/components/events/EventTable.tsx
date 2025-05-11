import Typography from "@mui/material/Typography";
import { useVirtualizer } from "@tanstack/react-virtual";
import dayjs, { Dayjs } from "dayjs";
import { memo, useLayoutEffect, useMemo, useState } from "react";

import { useFilteredCameras } from "components/camera/useCameraStore";
import { EventTableItem } from "components/events/EventTableItem";
import {
  getEventTimestamp,
  useFilterStore,
  useTimespansRef,
} from "components/events/utils";
import { Loading } from "components/loading/Loading";
import { useEventsMultiple } from "lib/api/events";
import { objIsEmpty } from "lib/helpers";
import * as types from "lib/types";

// Group events that are within 2 minutes of each other
const useGroupedEvents = (snapshotEvents: types.CameraEvent[]) => {
  const { filters } = useFilterStore();

  return useMemo(() => {
    if (snapshotEvents.length === 0) {
      return [];
    }

    const groups: types.CameraEvent[][] = [];
    let currentGroup: types.CameraEvent[] = [];
    let groupStartTime = getEventTimestamp(snapshotEvents[0]);
    let groupCameraIdentifier = snapshotEvents[0].camera_identifier;

    snapshotEvents.forEach((event) => {
      // Filter out unwanted event types
      if (!filters.eventTypes[event.type].checked) return;

      const currentTime = getEventTimestamp(event);

      if (
        groupStartTime - currentTime < 120 &&
        (filters.groupCameras.checked ||
          event.camera_identifier === groupCameraIdentifier)
      ) {
        currentGroup.push(event);
      } else {
        if (currentGroup.length > 0) {
          groups.push(currentGroup);
        }
        currentGroup = [event];
        groupStartTime = currentTime;
        groupCameraIdentifier = event.camera_identifier;
      }
    });

    // Add the last group if it has any items
    if (currentGroup.length > 0) {
      groups.push(currentGroup);
    }

    return groups;
  }, [snapshotEvents, filters]);
};

type EventTableProps = {
  parentRef: React.RefObject<HTMLDivElement>;
  date: Dayjs | null;
};

export const EventTable = memo(({ parentRef, date }: EventTableProps) => {
  const formattedDate = dayjs(date).format("YYYY-MM-DD");
  const [elementHeight, setElementHeight] = useState<number | null>(null);
  const filteredCameras = useFilteredCameras();
  const eventsQueries = useEventsMultiple({
    camera_identifiers: Object.keys(filteredCameras),
    date: formattedDate,
    configOptions: { enabled: !!date },
  });

  // Subscribe to timespans so it updates for child components
  useTimespansRef(date);

  const groupedEvents = useGroupedEvents(eventsQueries.data || []);

  const parentElement = parentRef.current;
  const rowVirtualizer = useVirtualizer({
    count: groupedEvents.length,
    getScrollElement: () => parentElement,
    estimateSize: () => elementHeight || 100,
    overscan: 5,
  });

  useLayoutEffect(() => {
    rowVirtualizer.measure();
  }, [rowVirtualizer, elementHeight]);

  if (eventsQueries.isPending) {
    return <Loading text="Loading Events" fullScreen={false} />;
  }

  if (!eventsQueries.data || objIsEmpty(eventsQueries.data)) {
    return (
      <Typography align="center" padding={2}>
        No Events found for {formattedDate}
      </Typography>
    );
  }
  return (
    <div
      style={{
        height: `${rowVirtualizer.getTotalSize()}px`,
        width: "100%",
        position: "relative",
      }}
    >
      {rowVirtualizer.getVirtualItems().map((virtualRow) => {
        const events = groupedEvents[virtualRow.index];
        return (
          <div
            key={virtualRow.key}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <EventTableItem
              events={events}
              isScrolling={rowVirtualizer.isScrolling}
              virtualRowIndex={virtualRow.index}
              measureElement={rowVirtualizer.measureElement}
              setElementHeight={setElementHeight}
            />
          </div>
        );
      })}
    </div>
  );
});
