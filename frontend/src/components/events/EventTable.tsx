import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import dayjs, { Dayjs } from "dayjs";
import { memo, useEffect } from "react";
import { forceCheck } from "react-lazyload";
import ServerDown from "svg/undraw/server_down.svg?react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { EventTableItem } from "components/events/EventTableItem";
import { getEventTimestamp } from "components/events/utils";
import { Loading } from "components/loading/Loading";
import { useEvents } from "lib/api/events";
import { useHlsAvailableTimespans } from "lib/api/hls";
import { objIsEmpty, throttle } from "lib/helpers";
import * as types from "lib/types";

// Group events that are within 2 minutes of each other
const groupEventsByTime = (
  snapshotEvents: types.CameraEvent[],
): types.CameraEvent[][] => {
  if (snapshotEvents.length === 0) {
    return [];
  }

  const _snapshotEvents = snapshotEvents.slice().reverse();

  const groups: types.CameraEvent[][] = [];
  let currentGroup: types.CameraEvent[] = [];
  let startOfGroup = getEventTimestamp(_snapshotEvents[0]);

  for (let i = 0; i < _snapshotEvents.length; i++) {
    if (currentGroup.length === 0) {
      currentGroup.push(_snapshotEvents[i]);
    } else {
      const currentTime = getEventTimestamp(_snapshotEvents[i]);

      if (currentTime - startOfGroup < 120) {
        currentGroup.push(_snapshotEvents[i]);
      } else {
        startOfGroup = getEventTimestamp(_snapshotEvents[i]);
        groups.unshift(currentGroup);
        currentGroup = [_snapshotEvents[i]];
      }
    }
  }

  // Add the last group if it has any items
  if (currentGroup.length > 0) {
    groups.unshift(currentGroup);
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
  camera: types.Camera | types.FailedCamera;
  date: Dayjs | null;
  selectedEvent: types.CameraEvent | null;
  setSelectedEvent: (event: types.CameraEvent) => void;
  setRequestedTimestamp: (timestamp: number | null) => void;
};

export const EventTable = memo(
  ({
    parentRef,
    camera,
    date,
    selectedEvent,
    setSelectedEvent,
    setRequestedTimestamp,
  }: EventTableProps) => {
    const formattedDate = dayjs(date).format("YYYY-MM-DD");
    const eventsQuery = useEvents({
      camera_identifier: camera.identifier,
      date: formattedDate,
      utc_offset_minutes: dayjs().utcOffset(),
      configOptions: { enabled: !!date },
    });

    const availableTimespansQuery = useHlsAvailableTimespans({
      camera_identifier: camera.identifier,
      date: formattedDate,
      configOptions: { enabled: !!date },
    });

    useOnScroll(parentRef);

    if (eventsQuery.isError || availableTimespansQuery.isError) {
      return (
        <ErrorMessage
          text={"Error loading Events"}
          subtext={
            eventsQuery.error?.message || availableTimespansQuery.error?.message
          }
          image={
            <ServerDown width={150} height={150} role="img" aria-label="Void" />
          }
        />
      );
    }

    if (eventsQuery.isLoading || availableTimespansQuery.isLoading) {
      return <Loading text="Loading Events" fullScreen={false} />;
    }

    if (!eventsQuery.data || objIsEmpty(eventsQuery.data)) {
      return (
        <Typography align="center" padding={2}>
          No Events found for {formattedDate}
        </Typography>
      );
    }

    const groupedEvents = groupEventsByTime(eventsQuery.data.events);
    return (
      <Box>
        <Grid container direction="row" columns={1}>
          {groupedEvents.map((events) => (
            <Grid
              item
              xs={12}
              sm={12}
              md={12}
              lg={12}
              xl={12}
              key={`event-${events[0].type}-${events[0].id}`}
            >
              <EventTableItem
                camera={camera}
                events={events}
                setSelectedEvent={setSelectedEvent}
                selected={!!selectedEvent && selectedEvent.id === events[0].id}
                setRequestedTimestamp={setRequestedTimestamp}
                availableTimespans={availableTimespansQuery.data}
              />
              <Divider sx={{ marginTop: "5px", marginBottom: "5px" }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  },
);
