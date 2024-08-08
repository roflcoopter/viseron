import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Tooltip, { TooltipProps, tooltipClasses } from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { styled, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
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
import { toTitleCase } from "lib/helpers";
import * as types from "lib/types";

const CustomWidthTooltip = styled(({ className, ...props }: TooltipProps) => (
  <Tooltip {...props} classes={{ popper: className }} />
))(() => ({
  [`& .${tooltipClasses.tooltip}`]: {
    overflowX: "hidden",
    overflowY: "scroll",
    maxHeight: "50vh",
    maxWidth: "100vw",
  },
}));

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

const ToolTipContent = ({ events }: { events: types.CameraEvent[] }) => {
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));
  const width = matches ? (events.length > 1 ? "50vw" : "25vw") : "90vw";
  return (
    <Grid
      container
      direction="row"
      spacing={1}
      sx={{ flexGrow: 1, width }}
      columns={2}
    >
      {events.reverse().map((event, index) => (
        <Grid
          item
          key={`${index}-${getEventTimestamp(event)}`}
          xs={events.length > 1 ? 1 : 2}
        >
          <Card>
            <CardMedia
              sx={{
                borderRadius: theme.shape.borderRadius,
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
  const theme = useTheme();
  const Icon = getIcon(events[0]);
  return (
    <CustomWidthTooltip title={<ToolTipContent events={events} />} arrow>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "5px",
          cursor: "pointer",
          "&:hover": {
            backgroundColor:
              theme.palette.mode === "dark"
                ? theme.palette.primary[900]
                : theme.palette.primary[200],
            borderRadius: "5px",
          },
        }}
      >
        <Icon
          color="primary"
          style={{
            height: EVENT_ICON_HEIGHT,
            width: EVENT_ICON_HEIGHT,
          }}
        />
      </Box>
    </CustomWidthTooltip>
  );
};

const SnapshotIcons = ({ events }: { events: types.CameraEvent[] }) => {
  const uniqueEvents = extractUniqueTypes(events);
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
      sx={{
        width: "35%",
        margin: "auto",
        marginLeft: "10px",
        marginRight: "10px",
        overflow: "hidden",
        borderRadius: "5px",
        border: `1px solid ${
          theme.palette.mode === "dark"
            ? theme.palette.primary[900]
            : theme.palette.primary[200]
        }`,
        transform: `translateY(calc(-50% + ${TICK_HEIGHT / 2}px))`,
        boxShadow: "0px 0px 5px 0px rgba(0,0,0,0.75)",
      }}
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
