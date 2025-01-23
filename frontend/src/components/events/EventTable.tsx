import Typography from "@mui/material/Typography";
import { useVirtualizer } from "@tanstack/react-virtual";
import dayjs, { Dayjs } from "dayjs";
import { memo, useLayoutEffect, useMemo, useRef, useState } from "react";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { EventTableItem } from "components/events/EventTableItem";
import {
  getEventTimestamp,
  useCameraStore,
  useFilterStore,
  useTimespans,
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
      if (!filters[event.type].checked) return;

      const currentTime = getEventTimestamp(event);

      if (
        groupStartTime - currentTime < 120 &&
        event.camera_identifier === groupCameraIdentifier
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
  cameras: types.CamerasOrFailedCameras;
  date: Dayjs | null;
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent) => void;
};

export const EventTable = memo(
  ({
    parentRef,
    cameras,
    date,
    selectedEvent,
    setSelectedEvent,
  }: EventTableProps) => {
    const formattedDate = dayjs(date).format("YYYY-MM-DD");

    const [elementHeight, setElementHeight] = useState<number | null>(null);
    const { selectedCameras } = useCameraStore();
    const eventsQueries = useEventsMultiple({
      camera_identifiers: selectedCameras,
      date: formattedDate,
      configOptions: { enabled: !!date },
    });

    // Store as ref to prevent re-render of EventTableItem
    const availableTimespansRef = useRef<types.HlsAvailableTimespan[]>([]);
    const availableTimespans = useTimespans(date);
    availableTimespansRef.current = availableTimespans;

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

    if (eventsQueries.isError) {
      return (
        <ErrorMessage
          text={"Error loading Events"}
          subtext={
            eventsQueries.error?.response?.data.error ||
            eventsQueries.error?.message
          }
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }

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
          const oldestEvent = events[events.length - 1];
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
                cameras={cameras}
                events={events}
                setSelectedEvent={setSelectedEvent}
                selected={
                  !!selectedEvent && selectedEvent.id === oldestEvent.id
                }
                availableTimespansRef={availableTimespansRef}
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
  },
);
