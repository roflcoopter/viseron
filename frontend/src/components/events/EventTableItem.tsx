import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardMedia from "@mui/material/CardMedia";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import LazyLoad from "react-lazyload";

import { SnapshotIcon } from "components/events/SnapshotEvent";
import {
  extractUniqueLabels,
  extractUniqueTypes,
  getSrc,
} from "components/events/utils";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { getTimeFromDate } from "lib/helpers";
import * as types from "lib/types";

const getText = (snapshotEvents: types.CameraSnapshotEvents) => {
  const uniqueEvents = extractUniqueTypes(snapshotEvents);
  return (
    <Box>
      <Typography variant="body2" align="center">{`${getTimeFromDate(
        new Date(snapshotEvents[0].time),
      )}`}</Typography>
      <Grid container justifyContent="center" alignItems="center">
        {Object.keys(uniqueEvents).map((key) => {
          // For object detection we want to group by label
          if (key === "object") {
            const uniqueLabels = extractUniqueLabels(
              uniqueEvents[key] as Array<types.CameraObjectEvent>,
            );
            return Object.keys(uniqueLabels).map((label) => (
              <Grid item key={`icon-${key}-${label}`}>
                <SnapshotIcon snapshotEvents={uniqueLabels[label]} />
              </Grid>
            ));
          }
          return (
            <Grid item key={`icon-${key}`}>
              <SnapshotIcon snapshotEvents={uniqueEvents[key]} />
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
};

const isTimespanAvailable = (
  timestamp: number,
  availableTimespans: types.HlsAvailableTimespans,
) => {
  for (const timespan of availableTimespans.timespans) {
    if (timestamp >= timespan.start && timestamp <= timespan.end) {
      return true;
    }
  }
  return false;
};

type EventTableItemProps = {
  camera: types.Camera | types.FailedCamera;
  snapshotEvents: types.CameraSnapshotEvents;
  setSelectedEvent: (event: types.CameraEvent) => void;
  selected: boolean;
  setRequestedTimestamp: (timestamp: number | null) => void;
  availableTimespans: types.HlsAvailableTimespans;
};
export const EventTableItem = ({
  camera,
  snapshotEvents,
  setSelectedEvent,
  selected,
  setRequestedTimestamp,
  availableTimespans,
}: EventTableItemProps) => {
  const theme = useTheme();
  return (
    <Card
      variant="outlined"
      square
      sx={{
        border: selected
          ? `2px solid ${theme.palette.primary[400]}`
          : "2px solid transparent",
        borderRadius: "5px",
        boxShadow: "none",
      }}
    >
      <CardActionArea
        onClick={() => {
          if (
            isTimespanAvailable(
              Math.round(snapshotEvents[0].timestamp),
              availableTimespans,
            )
          ) {
            setSelectedEvent(snapshotEvents[0]);
            setRequestedTimestamp(Math.round(snapshotEvents[0].timestamp));
            return;
          }

          setSelectedEvent(snapshotEvents[0]);
          setRequestedTimestamp(null);
        }}
      >
        <Grid
          container
          direction="row"
          justifyContent="flex-end"
          alignItems="center"
        >
          <Grid item xs={6}>
            {getText(snapshotEvents)}
          </Grid>
          <Grid item xs={6}>
            <CardMedia
              sx={{
                borderRadius: "5px",
                overflow: "hidden",
              }}
            >
              <LazyLoad
                overflow
                offset={100}
                placeholder={
                  <VideoPlayerPlaceholder
                    aspectRatio={camera.width / camera.height}
                  />
                }
              >
                <Image
                  src={getSrc(snapshotEvents[0])}
                  aspectRatio={camera.width / camera.height}
                  color={theme.palette.background.default}
                  animationDuration={1000}
                />
              </LazyLoad>
            </CardMedia>
          </Grid>
        </Grid>
      </CardActionArea>
    </Card>
  );
};
