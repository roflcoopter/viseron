import Image from "@jy95/material-ui-image";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import IconButton from "@mui/material/IconButton";
import Popover from "@mui/material/Popover";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import PopupState, { bindHover, bindPopover } from "material-ui-popup-state";
import HoverPopover from "material-ui-popup-state/HoverPopover";
import { memo, useCallback, useRef } from "react";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
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
  useFilterStore,
  useSelectEvent,
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
          <Typography variant="h5" fontSize="1rem">
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
          <Typography variant="h5" fontSize="1rem">
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
          <Typography variant="h5" fontSize="1rem">
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
          <Typography variant="h5" fontSize="1rem">
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
          <Typography variant="h5" fontSize="1rem">
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

function PopoverContent({ events }: { events: types.CameraEvent[] }) {
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));
  const width = matches ? (events.length > 1 ? "50vw" : "25vw") : "90vw";
  const handleEventClick = useSelectEvent();
  const exportEvent = useExportEvent();
  const { filters } = useFilterStore();

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
        .map((event) => (
          <Grid
            key={`${event.id}-${getEventTimestamp(event)}`}
            size={events.length > 1 ? 1 : 2}
          >
            <Card>
              <CardActionArea
                onClick={() => {
                  handleEventClick(event);
                }}
              >
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
                  {filters.groupCameras.checked && (
                    <CameraNameOverlay
                      camera_identifier={event.camera_identifier}
                    />
                  )}
                </CardMedia>
              </CardActionArea>
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
}

function Divider() {
  return (
    <Box
      sx={(theme) => ({
        height: "1px",
        flexGrow: 1,
        backgroundColor: theme.palette.divider,
      })}
    />
  );
}

export function SnapshotIcon({ events }: { events: types.CameraEvent[] }) {
  const Icon = getIcon(events[0]);
  const PopoverComponent = isTouchDevice() ? Popover : HoverPopover;

  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleOnMouseEnter = useCallback(
    (
      e: React.MouseEvent<HTMLElement>,
      onMouseOver: (e: React.MouseEvent<HTMLElement>) => void,
    ) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      const currentTarget = e.currentTarget;
      timeoutRef.current = setTimeout(() => {
        e.currentTarget = currentTarget;
        onMouseOver(e);
      }, 100);
    },
    [timeoutRef],
  );

  const handleMouseLeave = useCallback(
    (e: React.MouseEvent, onMouseLeave: (event: React.MouseEvent) => void) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      onMouseLeave(e);
    },
    [timeoutRef],
  );

  return (
    <PopupState variant="popover">
      {(popupState) => {
        const { onMouseLeave, onMouseOver, ...rest } = bindHover(popupState);

        return (
          <div>
            <Box
              // eslint-disable-next-line react/jsx-props-no-spreading
              {...rest}
              onMouseOver={(e) => handleOnMouseEnter(e, onMouseOver)}
              onMouseLeave={(e) => handleMouseLeave(e, onMouseLeave)}
              sx={(theme) => ({
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "5px",
                cursor: "pointer",
                borderRadius: 1, // theme.shape.borderRadius * 1
                "&:hover": {
                  backgroundColor: theme.palette.primary[200],

                  ...theme.applyStyles("dark", {
                    backgroundColor: theme.palette.primary[900],
                  }),
                },
                ...(popupState.isOpen && {
                  backgroundColor: theme.palette.primary[200],

                  ...theme.applyStyles("dark", {
                    backgroundColor: theme.palette.primary[900],
                  }),
                }),
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
              // eslint-disable-next-line react/jsx-props-no-spreading
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
        );
      }}
    </PopupState>
  );
}

function SnapshotIcons({ events }: { events: types.CameraEvent[] }) {
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
}

function Snapshot({ snapshotPath }: { snapshotPath: string }) {
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
        lineHeight: 0,
      })}
    >
      <img
        src={snapshotPath}
        alt="Event snapshot"
        color={theme.palette.background.default}
        style={{
          display: "block",
          aspectRatio: "1/1",
          width: "100%",
          height: "100%",
          objectFit: "contain",
          background: theme.palette.background.default,
        }}
      />
    </Box>
  );
}

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
