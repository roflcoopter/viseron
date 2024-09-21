import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid2";
import Typography from "@mui/material/Typography";
import dayjs, { Dayjs } from "dayjs";
import { memo, useEffect } from "react";
import { forceCheck } from "react-lazyload";
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
import { objIsEmpty, throttle } from "lib/helpers";
import * as types from "lib/types";

// Group events that are within 2 minutes of each other
const groupEventsByTime = (
  snapshotEvents: types.CameraEvent[],
): types.CameraEvent[][] => {
  if (snapshotEvents.length === 0) {
    return [];
  }

  const groups: types.CameraEvent[][] = [];
  let currentGroup: types.CameraEvent[] = [];
  let groupStartTime = getEventTimestamp(snapshotEvents[0]);
  let groupCameraIdentifier = snapshotEvents[0].camera_identifier;

  for (const event of snapshotEvents) {
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
  }

  // Add the last group if it has any items
  if (currentGroup.length > 0) {
    groups.push(currentGroup);
  }

  return groups;
};

const useOnScroll = (parentRef: React.RefObject<HTMLDivElement>) => {
  useEffect(() => {
    const container = parentRef.current;
    if (!container) return () => {};

    const throttleForceCheck = throttle(() => {
      forceCheck();
    }, 100);
    container.addEventListener("scroll", throttleForceCheck);

    return () => {
      container.removeEventListener("scroll", throttleForceCheck);
    };
  });
};

type EventTableProps = {
  parentRef: React.RefObject<HTMLDivElement>;
  cameras: types.CamerasOrFailedCameras;
  date: Dayjs | null;
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent) => void;
  setRequestedTimestamp: (timestamp: number | null) => void;
};

export const EventTable = memo(
  ({
    parentRef,
    cameras,
    date,
    selectedEvent,
    setSelectedEvent,
    setRequestedTimestamp,
  }: EventTableProps) => {
    const formattedDate = dayjs(date).format("YYYY-MM-DD");
    const { selectedCameras } = useCameraStore();
    const eventsQueries = useEventsMultiple({
      camera_identifiers: selectedCameras,
      date: formattedDate,
      configOptions: { enabled: !!date },
    });

    const availableTimespans = useTimespans(date);

    useOnScroll(parentRef);
    const { filters } = useFilterStore();

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

    const filteredEvents = eventsQueries.data.filter(
      (event) => filters[event.type].checked,
    );
    const groupedEvents = groupEventsByTime(filteredEvents);
    return (
      <Box>
        <Grid container direction="row" columns={1}>
          {groupedEvents.map((events) => {
            const oldestEvent = events[events.length - 1];
            return (
              <Grid
                key={`event-${oldestEvent.type}-${oldestEvent.id}`}
                size={{
                  xs: 12,
                  sm: 12,
                  md: 12,
                  lg: 12,
                  xl: 12,
                }}
              >
                <EventTableItem
                  cameras={cameras}
                  events={events}
                  setSelectedEvent={setSelectedEvent}
                  selected={
                    !!selectedEvent && selectedEvent.id === oldestEvent.id
                  }
                  setRequestedTimestamp={setRequestedTimestamp}
                  availableTimespans={availableTimespans}
                />
                <Divider sx={{ marginTop: "5px", marginBottom: "5px" }} />
              </Grid>
            );
          })}
        </Grid>
      </Box>
    );
  },
);
