import Image from "@jy95/material-ui-image";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import Popover from "@mui/material/Popover";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import PopupState, { bindHover, bindPopover } from "material-ui-popup-state";
import HoverPopover from "material-ui-popup-state/HoverPopover";
import { memo } from "react";

import {
  EVENT_ICON_HEIGHT,
  TICK_HEIGHT,
  convertToPercentage,
  extractUniqueLabels,
  extractUniqueTypes,
  getEventTime,
  getEventTimestamp,
  getIcon,
  getSrc,
} from "components/events/utils";
import { useExportEvent } from "lib/commands";
import { isTouchDevice, toTitleCase } from "lib/helpers";
import * as types from "lib/types";

const getText = (event: types.CameraEvent) => {
  const date = new Date(getEventTime(event));
  switch (event.type) {
    case "object":
      return (
        <Box>
          <Typography variant="h5" fontSize={"1rem"}>
            Object Detection
          </Typography>

          <Box>{`Label: ${event.label}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(event.confidence)}%`}</Box>
          <Box>{`Time: ${date.toLocaleTimeString()}`}</Box>
        </Box>
      );

    case "face_recognition":
      return (
        <Box>
          <Typography variant="h5" fontSize={"1rem"}>
            Face Recognition
          </Typography>
          <Box>{`Name: ${toTitleCase(event.data.name)}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(
            event.data.confidence,
          )}%`}</Box>
          <Box>{`Time: ${date.toLocaleTimeString()}`}</Box>
        </Box>
      );

    case "license_plate_recognition":
      return (
        <Box>
          <Typography variant="h5" fontSize={"1rem"}>
            License Plate Recognition
          </Typography>
          <Box>{`Plate: ${event.data.plate}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(
            event.data.confidence,
          )}%`}</Box>
          <Box>{`Known: ${event.data.known}`}</Box>
          <Box>{`Time: ${date.toLocaleTimeString()}`}</Box>
        </Box>
      );

    case "motion":
      return (
        <Box>
          <Typography variant="h5" fontSize={"1rem"}>
            Motion Detection
          </Typography>
          {event.duration ? (
            <Box>{`Duration: ${Math.round(event.duration)}s`}</Box>
          ) : null}
          <Box>{`Time: ${date.toLocaleTimeString()}`}</Box>
        </Box>
      );

    case "recording":
      return (
        <Box>
          <Typography variant="h5" fontSize={"1rem"}>
            Recording
          </Typography>
          {event.trigger_type ? (
            <Box>{`Triggered by: ${toTitleCase(event.trigger_type)}`}</Box>
          ) : null}
          {event.duration ? (
            <Box>{`Duration: ${Math.round(event.duration)}s`}</Box>
          ) : null}
          <Box>{`Time: ${date.toLocaleTimeString()}`}</Box>
        </Box>
      );

    default:
      return event satisfies never;
  }
};

const getTooltipTitle = (event: types.CameraEvent) => {
  switch (event.type) {
    case "object":
    case "face_recognition":
    case "license_plate_recognition":
    case "motion":
      return "Download Snapshot";

    case "recording":
      return "Download Recording";

    default:
      return event satisfies never;
  }
};

const PopoverContent = ({ events }: { events: types.CameraEvent[] }) => {
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));
  const width = matches ? (events.length > 1 ? "50vw" : "25vw") : "90vw";
  const exportEvent = useExportEvent();

  return (
    <Grid
      container
      direction="row"
      spacing={1}
      sx={{ flexGrow: 1, width }}
      columns={2}
    >
      {events
        .slice()
        .reverse()
        .map((event, index) => (
          <Grid
            key={`${index}-${getEventTimestamp(event)}`}
            size={events.length > 1 ? 1 : 2}
          >
            <Card>
              <CardMedia
                sx={{
                  borderRadius: 1, // theme.shape.borderRadius * 1
                  overflow: "hidden",
                }}
              >
                <Image
                  src={getSrc(event)}
                  color={theme.palette.background.default}
                  animationDuration={0}
                  imageStyle={{
                    objectFit: "contain",
                  }}
                />
              </CardMedia>
              <CardContent>{getText(event)}</CardContent>
              <CardActions>
                <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
                  <Tooltip title={getTooltipTitle(event)}>
                    <IconButton
                      onClick={(e) => {
                        exportEvent(event);
                        e.stopPropagation();
                        e.preventDefault();
                      }}
                    >
                      <FileDownloadIcon />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </CardActions>
            </Card>
          </Grid>
        ))}
    </Grid>
  );
};

const Divider = () => (
  <Box
    sx={(theme) => ({
      height: "1px",
      flexGrow: 1,
      backgroundColor: theme.palette.divider,
    })}
  />
);

export const SnapshotIcon = ({ events }: { events: types.CameraEvent[] }) => {
  const Icon = getIcon(events[0]);
  const PopoverComponent = isTouchDevice() ? Popover : HoverPopover;

  return (
    <PopupState variant="popover">
      {(popupState) => (
        <div>
          <Box
            {...bindHover(popupState)}
            sx={(theme) => ({
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "5px",
              cursor: "pointer",
              "&:hover": {
                borderRadius: 1, // theme.shape.borderRadius * 1
                backgroundColor: theme.palette.primary[200],

                ...theme.applyStyles("dark", {
                  backgroundColor: theme.palette.primary[900],
                }),
              },
            })}
          >
            <Icon
              color="primary"
              style={{
                height: EVENT_ICON_HEIGHT,
                width: EVENT_ICON_HEIGHT,
              }}
            />
          </Box>
          <PopoverComponent
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
            }}
            {...bindPopover(popupState)}
            slotProps={{
              paper: {
                style: {
                  padding: 10,
                  overflowX: "hidden",
                  overflowY: "scroll",
                  maxHeight: "50vh",
                  maxWidth: "100vw",
                },
              },
            }}
            anchorOrigin={{
              vertical: "bottom",
              horizontal: "left",
            }}
            transformOrigin={{
              vertical: "top",
              horizontal: "left",
            }}
          >
            <PopoverContent events={events} />
          </PopoverComponent>
        </div>
      )}
    </PopupState>
  );
};

const SnapshotIcons = ({ events }: { events: types.CameraEvent[] }) => {
  // Show the oldest event first in the list, API returns latest first
  const sortedEvents = events
    .slice()
    .sort((a, b) => a.created_at_timestamp - b.created_at_timestamp);
  const uniqueEvents = extractUniqueTypes(sortedEvents);
  return (
    <Stack direction="row">
      {Object.keys(uniqueEvents).map((key) => {
        // For object detection we want to group by label
        if (key === "object") {
          const uniqueLabels = extractUniqueLabels(
            uniqueEvents[key] as Array<types.CameraObjectEvent>,
          );
          return Object.keys(uniqueLabels).map((label) => (
            <Box key={`icon-${key}-${label}`}>
              <SnapshotIcon events={uniqueLabels[label]} />
            </Box>
          ));
        }
        return (
          <Box key={`icon-${key}`}>
            <SnapshotIcon events={uniqueEvents[key]} />
          </Box>
        );
      })}
    </Stack>
  );
};

const Snapshot = ({ snapshotPath }: { snapshotPath: string }) => {
  const theme = useTheme();
  return (
    <Box
      sx={() => ({
        width: "35%",
        margin: "auto",
        marginLeft: "10px",
        marginRight: "10px",
        overflow: "hidden",
        borderRadius: 1, // theme.shape.borderRadius * 1
        transform: `translateY(calc(-50% + ${TICK_HEIGHT / 2}px))`,
        boxShadow: "0px 0px 5px 0px rgba(0,0,0,0.75)",
        border: `1px solid ${theme.palette.primary[200]}`,
        ...theme.applyStyles("dark", {
          border: `1px solid ${theme.palette.primary[900]}`,
        }),
      })}
    >
      <Image
        src={snapshotPath}
        color={theme.palette.background.default}
        animationDuration={1000}
      />
    </Box>
  );
};

type SnapshotEventProps = {
  events: types.CameraEvent[];
};
export const SnapshotEvent = memo(({ events }: SnapshotEventProps) => (
  <Box
    sx={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      height: TICK_HEIGHT,
      width: "100%",
    }}
  >
    <Divider />
    <SnapshotIcons events={events} />
    <Divider />
    <Snapshot snapshotPath={getSrc(events[0])} />
  </Box>
));
