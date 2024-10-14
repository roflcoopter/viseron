import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid2";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { memo, useCallback, useMemo } from "react";

import { SnapshotIcon } from "components/events/SnapshotEvent";
import {
  extractUniqueLabels,
  extractUniqueTypes,
  getEventTime,
  getEventTimestamp,
  getSrc,
} from "components/events/utils";
import { useFirstRender } from "hooks/UseFirstRender";
import { BLANK_IMAGE, getTimeFromDate } from "lib/helpers";
import * as types from "lib/types";

type EventTableItemIconProps = {
  sortedEvents: types.CameraEvent[];
  cameras: types.CamerasOrFailedCameras;
};

const EventTableItemIcon = ({
  sortedEvents,
  cameras,
}: EventTableItemIconProps) => {
  const uniqueEvents = extractUniqueTypes(sortedEvents);
  return (
    <div>
      <Typography fontSize=".75rem" fontWeight="bold" align="center">
        {`${
          cameras && cameras[sortedEvents[0].camera_identifier]
            ? cameras[sortedEvents[0].camera_identifier].name
            : sortedEvents[0].camera_identifier
        }`}
      </Typography>
      <Typography
        fontSize=".75rem"
        color="text.secondary"
        align="center"
      >{`${getTimeFromDate(
        new Date(getEventTime(sortedEvents[0])),
      )}`}</Typography>
      <Grid container justifyContent="center" alignItems="center">
        {Object.keys(uniqueEvents).map((key) => {
          // For object detection we want to group by label
          if (key === "object") {
            const uniqueLabels = extractUniqueLabels(
              uniqueEvents[key] as Array<types.CameraObjectEvent>,
            );
            return Object.keys(uniqueLabels).map((label) => (
              <Grid key={`icon-${key}-${label}`}>
                <SnapshotIcon events={uniqueLabels[label]} />
              </Grid>
            ));
          }
          return (
            <Grid key={`icon-${key}`}>
              <SnapshotIcon events={uniqueEvents[key]} />
            </Grid>
          );
        })}
      </Grid>
    </div>
  );
};

const isTimespanAvailable = (
  timestamp: number,
  availableTimespans: types.HlsAvailableTimespan[],
) => {
  for (const timespan of availableTimespans) {
    if (timestamp >= timespan.start && timestamp <= timespan.end) {
      return true;
    }
  }
  return false;
};

type EventTableItemProps = {
  cameras: types.CamerasOrFailedCameras;
  events: types.CameraEvent[];
  setSelectedEvent: (event: types.CameraEvent) => void;
  selected: boolean;
  setRequestedTimestamp: (timestamp: number | null) => void;
  availableTimespansRef: React.MutableRefObject<types.HlsAvailableTimespan[]>;
  isScrolling: boolean;
  virtualRowIndex: number;
  measureElement: (element: HTMLElement | null) => void;
  setElementHeight: React.Dispatch<React.SetStateAction<number | null>>;
};
export const EventTableItem = memo(
  ({
    cameras,
    events,
    setSelectedEvent,
    selected,
    setRequestedTimestamp,
    availableTimespansRef,
    isScrolling,
    virtualRowIndex,
    measureElement,
    setElementHeight,
  }: EventTableItemProps) => {
    const theme = useTheme();
    const firstRender = useFirstRender();
    // Show the oldest event first in the list, API returns latest first
    const sortedEvents = useMemo(
      () =>
        events
          .slice()
          .sort((a, b) => a.created_at_timestamp - b.created_at_timestamp),
      [events],
    );

    const handleEventClick = useCallback(() => {
      if (
        isTimespanAvailable(
          Math.round(getEventTimestamp(sortedEvents[0])),
          availableTimespansRef.current,
        )
      ) {
        setSelectedEvent(sortedEvents[0]);
        setRequestedTimestamp(Math.round(getEventTimestamp(sortedEvents[0])));
        return;
      }

      setSelectedEvent(sortedEvents[0]);
      setRequestedTimestamp(null);
    }, [
      sortedEvents,
      availableTimespansRef,
      setSelectedEvent,
      setRequestedTimestamp,
    ]);

    const src = useMemo(
      () =>
        isScrolling && firstRender ? BLANK_IMAGE : getSrc(sortedEvents[0]),
      [isScrolling, firstRender, sortedEvents],
    );

    return (
      <Card
        data-index={virtualRowIndex}
        ref={(node) => {
          measureElement(node);
          if (node) {
            setElementHeight(node.offsetHeight);
          }
        }}
        variant="outlined"
        square
        sx={[
          {
            boxShadow: "none",
          },
          selected
            ? {
                borderRadius: 1, // theme.shape.borderRadius * 1
                border: `2px solid ${theme.palette.primary[400]}`,
                padding: "0px",
              }
            : {
                border: "2px solid transparent",
                borderBottom: `1px solid ${theme.palette.divider}`,
                paddingBottom: "1px",
              },
        ]}
      >
        <CardActionArea onClick={handleEventClick}>
          <Grid
            container
            direction="row"
            justifyContent="flex-end"
            alignItems="center"
          >
            <Grid size={8}>
              <EventTableItemIcon
                sortedEvents={sortedEvents}
                cameras={cameras}
              />
            </Grid>
            <Grid size={4}>
              <CardMedia
                sx={{
                  borderRadius: 1, // theme.shape.borderRadius * 1
                  overflow: "hidden",
                }}
              >
                <img
                  src={src}
                  style={{
                    aspectRatio: "1/1",
                    width: "100%",
                    height: "100%",
                    objectFit: "contain",
                    background: theme.palette.background.default,
                  }}
                />
              </CardMedia>
            </Grid>
          </Grid>
        </CardActionArea>
      </Card>
    );
  },
);
