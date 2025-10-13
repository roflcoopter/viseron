import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { memo, useMemo } from "react";

import { SnapshotIcon } from "components/events/SnapshotEvent";
import {
  extractUniqueLabels,
  extractUniqueTypes,
  getEventTime,
  getSrc,
  useEventStore,
  useSelectEvent,
} from "components/events/utils";
import { useFirstRender } from "hooks/UseFirstRender";
import {
  BLANK_IMAGE,
  getCameraNameFromQueryCache,
  getTimeFromDate,
} from "lib/helpers";
import * as types from "lib/types";

type EventTableItemIconsProps = {
  sortedEvents: types.CameraEvent[];
};

const EventTableItemIcons = ({ sortedEvents }: EventTableItemIconsProps) => {
  const uniqueEvents = extractUniqueTypes(sortedEvents);
  const cameraName = getCameraNameFromQueryCache(
    sortedEvents[0].camera_identifier,
  );

  return (
    <div>
      <Typography fontSize=".75rem" fontWeight="bold" align="center">
        {cameraName}
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

type EventTableItemProps = {
  events: types.CameraEvent[];
  isScrolling: boolean;
  virtualRowIndex: number;
  measureElement: (element: HTMLElement | null) => void;
  setElementHeight: React.Dispatch<React.SetStateAction<number | null>>;
};
export const EventTableItem = memo(
  ({
    events,
    isScrolling,
    virtualRowIndex,
    measureElement,
    setElementHeight,
  }: EventTableItemProps) => {
    const theme = useTheme();
    const firstRender = useFirstRender();

    const { selectedEvent } = useEventStore();

    // Show the oldest event first in the list, API returns latest first
    const sortedEvents = useMemo(
      () =>
        events
          .slice()
          .sort((a, b) => a.created_at_timestamp - b.created_at_timestamp),
      [events],
    );
    const handleEventClick = useSelectEvent();

    const src = useMemo(
      () =>
        isScrolling && firstRender ? BLANK_IMAGE : getSrc(sortedEvents[0]),
      [isScrolling, firstRender, sortedEvents],
    );

    const selected = !!selectedEvent && selectedEvent.id === sortedEvents[0].id;

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
        <CardActionArea onClick={() => handleEventClick(sortedEvents[0])}>
          <Grid
            container
            direction="row"
            justifyContent="flex-end"
            alignItems="center"
          >
            <Grid size={8}>
              <EventTableItemIcons sortedEvents={sortedEvents} />
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
