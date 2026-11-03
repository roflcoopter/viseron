import { ImageCopy } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { Link } from "react-router-dom";

import { formatDuration, formatTimestamp } from "components/timelapse/utils";
import * as types from "lib/types";

type TimelapseCameraCardProps = {
  camera: types.Camera;
  summary: types.TimelapseCameraSummary | undefined;
};

export function TimelapseCameraCard({
  camera,
  summary,
}: TimelapseCameraCardProps) {
  // The latest frame can be pruned right after the summary is fetched
  const [failedPath, setFailedPath] = useState<string | null>(null);
  const latestFrame = summary?.latest_frame;
  const count = summary?.count ?? 0;
  const aspectRatio = camera.mainstream.width / camera.mainstream.height;

  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardActionArea
        component={Link}
        to={`/timelapse/${camera.identifier}`}
        sx={{ height: "100%" }}
      >
        <CardContent>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
          >
            <Typography variant="h6">{camera.name}</Typography>
            <Chip
              label={`${count} ${count === 1 ? "frame" : "frames"}`}
              size="small"
              variant="outlined"
              color="info"
            />
          </Stack>
        </CardContent>
        {latestFrame && failedPath !== latestFrame.path ? (
          <Box
            component="img"
            src={latestFrame.path}
            alt={`Latest timelapse frame of ${camera.name}`}
            onError={() => setFailedPath(latestFrame.path)}
            sx={{ display: "block", width: "100%", aspectRatio }}
          />
        ) : (
          <Box
            sx={{
              width: "100%",
              aspectRatio,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: "background.default",
            }}
          >
            <ImageCopy size={48} style={{ opacity: 0.5 }} />
          </Box>
        )}
        <CardContent>
          {summary?.first_timestamp && summary.last_timestamp ? (
            <Typography variant="body2" color="text.secondary">
              {formatTimestamp(summary.first_timestamp, false)} –{" "}
              {formatTimestamp(summary.last_timestamp, false)} (
              {formatDuration(summary.last_timestamp - summary.first_timestamp)}
              )
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No frames yet
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
