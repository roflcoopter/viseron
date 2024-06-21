import Image from "@jy95/material-ui-image";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import PersonIcon from "@mui/icons-material/DirectionsWalk";
import FaceIcon from "@mui/icons-material/Face";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import PetsIcon from "@mui/icons-material/Pets";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Tooltip, { TooltipProps, tooltipClasses } from "@mui/material/Tooltip";
import { styled, useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { memo } from "react";

import {
  EVENT_ICON_HEIGHT,
  TICK_HEIGHT,
  convertToPercentage,
  extractUniqueLabels,
  extractUniqueTypes,
} from "components/events/utils";
import LicensePlateRecgnitionIcon from "components/icons/LicensePlateRecognition";
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

const labelToIcon = (label: string) => {
  switch (label) {
    case "person":
      return PersonIcon;

    case "car":
    case "truck":
    case "vehicle":
      return DirectionsCarIcon;

    case "dog":
    case "cat":
    case "animal":
      return PetsIcon;

    default:
      return ImageSearchIcon;
  }
};

const getIcon = (snapshotEvent: types.CameraSnapshotEvent) => {
  switch (snapshotEvent.type) {
    case "object":
      return labelToIcon(snapshotEvent.label);
    case "face_recognition":
      return FaceIcon;
    case "license_plate_recognition":
      return LicensePlateRecgnitionIcon;
    default:
      return ImageSearchIcon;
  }
};

const getText = (snapshotEvent: types.CameraSnapshotEvent) => {
  const date = new Date(snapshotEvent.time);
  switch (snapshotEvent.type) {
    case "object":
      return (
        <Box>
          <Box>Object Detection</Box>
          <Box>{`Label: ${snapshotEvent.label}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(
            snapshotEvent.confidence,
          )}%`}</Box>
          <Box>{`Timestamp: ${date.toLocaleString()}`}</Box>
        </Box>
      );

    case "face_recognition":
      return (
        <Box>
          <Box>Face Recognition</Box>
          <Box>{`Name: ${toTitleCase(snapshotEvent.data.name)}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(
            snapshotEvent.data.confidence,
          )}%`}</Box>
          <Box>{`Timestamp: ${date.toLocaleString()}`}</Box>
        </Box>
      );

    case "license_plate_recognition":
      return (
        <Box>
          <Box>License Plate Recognition</Box>
          <Box>{`Plate: ${snapshotEvent.data.plate}`}</Box>
          <Box>{`Confidence: ${convertToPercentage(
            snapshotEvent.data.confidence,
          )}%`}</Box>
          <Box>{`Known: ${snapshotEvent.data.known}`}</Box>
          <Box>{`Timestamp: ${date.toLocaleString()}`}</Box>
        </Box>
      );

    default:
      return null;
  }
};

const ToolTipContent = ({
  snapshotEvents,
}: {
  snapshotEvents: types.CameraSnapshotEvents;
}) => {
  const theme = useTheme();
  const matches = useMediaQuery(theme.breakpoints.up("sm"));
  const width = matches
    ? snapshotEvents.length > 1
      ? "50vw"
      : "25vw"
    : "90vw";
  return (
    <Grid
      container
      direction="row"
      spacing={1}
      sx={{ flexGrow: 1, width }}
      columns={2}
    >
      {snapshotEvents.reverse().map((snapshotEvent, index) => (
        <Grid
          item
          key={`${index}-${snapshotEvent.timestamp}`}
          xs={snapshotEvents.length > 1 ? 1 : 2}
        >
          <Card>
            <CardMedia
              sx={{
                borderRadius: theme.shape.borderRadius,
                overflow: "hidden",
              }}
            >
              <Image
                src={snapshotEvent.snapshot_path}
                color={theme.palette.background.default}
                animationDuration={0}
                imageStyle={{
                  objectFit: "contain",
                }}
              />
            </CardMedia>
            <CardContent>{getText(snapshotEvent)}</CardContent>
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

export const SnapshotIcon = ({
  snapshotEvents,
}: {
  snapshotEvents: types.CameraSnapshotEvents;
}) => {
  const theme = useTheme();
  const Icon = getIcon(snapshotEvents[0]);
  return (
    <CustomWidthTooltip
      title={<ToolTipContent snapshotEvents={snapshotEvents} />}
      arrow
    >
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
          style={{
            color:
              theme.palette.mode === "dark"
                ? theme.palette.primary[600]
                : theme.palette.primary[300],
            height: EVENT_ICON_HEIGHT,
            width: EVENT_ICON_HEIGHT,
          }}
        />
      </Box>
    </CustomWidthTooltip>
  );
};

const SnapshotIcons = ({
  snapshotEvents,
}: {
  snapshotEvents: types.CameraSnapshotEvents;
}) => {
  const uniqueEvents = extractUniqueTypes(snapshotEvents);
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
              <SnapshotIcon snapshotEvents={uniqueLabels[label]} />
            </Box>
          ));
        }
        return (
          <Box key={`icon-${key}`}>
            <SnapshotIcon snapshotEvents={uniqueEvents[key]} />
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
  snapshotEvents: types.CameraSnapshotEvents;
};
export const SnapshotEvent = memo(({ snapshotEvents }: SnapshotEventProps) => (
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
    <SnapshotIcons snapshotEvents={snapshotEvents} />
    <Divider />
    <Snapshot snapshotPath={snapshotEvents[0].snapshot_path} />
  </Box>
));
