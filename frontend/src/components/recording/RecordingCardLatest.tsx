import { FolderDetails, FolderOff, TrashCan } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import LazyLoad from "react-lazyload";
import { Link } from "react-router-dom";

import MutationIconButton from "components/buttons/MutationIconButton";
import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { useAuthContext } from "context/AuthContext";
import { useCamera } from "lib/api/camera";
import { useDeleteRecording, useRecordings } from "lib/api/recordings";
import {
  getDateStringFromDayjs,
  getDayjsFromDateTimeString,
  getTimeStringFromDayjs,
  getVideoElement,
  objHasValues,
} from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardLatestProps {
  camera_identifier: string;
  failed?: boolean;
}

export default function RecordingCardLatest({
  camera_identifier,
  failed,
}: RecordingCardLatestProps) {
  const theme = useTheme();
  const { auth, user } = useAuthContext();
  const deleteRecording = useDeleteRecording();

  const recordingsQuery = useRecordings({
    camera_identifier,
    latest: true,
    daily: true,
    failed,
  });

  const cameraQuery = useCamera(camera_identifier, failed);

  let recording: types.Recording | undefined;
  if (
    objHasValues<types.RecordingsCamera>(recordingsQuery.data) &&
    objHasValues<types.RecordingsCamera>(
      Object.values(recordingsQuery.data)[0],
    ) &&
    objHasValues<types.RecordingsCamera>(
      Object.values(Object.values(recordingsQuery.data)[0])[0],
    )
  ) {
    const recordingDate = Object.values(recordingsQuery.data)[0];
    recording = Object.values(recordingDate)[0];
  }

  let text = "No recordings found";
  if (recordingsQuery.status === "error") {
    text = "Error getting latest recording";
  } else if (recordingsQuery.status === "pending") {
    text = "Loading latest recording";
  } else if (recordingsQuery.status === "success" && !objHasValues(recording)) {
    text = "No recordings found";
  } else if (
    recordingsQuery.status === "success" &&
    objHasValues(recording) &&
    recording
  ) {
    // We'll handle the formatting in JSX for proper styling
  }

  if (cameraQuery.isPending || !cameraQuery.data) {
    return null;
  }

  const totalDays = recordingsQuery.data
    ? Object.keys(recordingsQuery.data).length
    : 0;

  return (
    <Card
      variant="outlined"
      sx={[
        {
          // Vertically space items evenly to accommodate different aspect ratios
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        },
        cameraQuery.data.failed && {
          border: `2px solid ${
            cameraQuery.data.retrying
              ? theme.palette.warning.main
              : theme.palette.error.main
          }`,
        },
      ]}
    >
      <CardContent>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="h6">{cameraQuery.data.name}</Typography>
          <Tooltip title="Total recording days">
            <Chip
              label={`${totalDays} ${totalDays === 1 ? "Day" : "Days"}`}
              size="small"
              variant="outlined"
              color="info"
            />
          </Tooltip>
        </Stack>
      </CardContent>
      <CardMedia>
        <LazyLoad
          height={200}
          placeholder={
            <VideoPlayerPlaceholder
              aspectRatio={
                cameraQuery.data.mainstream.width /
                cameraQuery.data.mainstream.height
              }
            />
          }
        >
          {objHasValues(recording) ? (
            getVideoElement(cameraQuery.data, recording, auth.enabled)
          ) : (
            <Box
              sx={{
                width: "100%",
                height: 200,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: theme.palette.background.default,
              }}
            >
              <FolderOff
                size={48}
                style={{
                  color: theme.palette.text.secondary,
                  opacity: 0.5,
                }}
              />
            </Box>
          )}
        </LazyLoad>
      </CardMedia>
      <CardActions>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={2}
          sx={{ width: "100%", paddingX: 1 }}
        >
          {objHasValues(recording) ? (
            <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
              Latest recording:{"\n"}
              <span style={{ color: theme.palette.info.main }}>
                {(() => {
                  const startDate = getDayjsFromDateTimeString(
                    recording.start_time,
                  );
                  return `${getDateStringFromDayjs(startDate)} - ${getTimeStringFromDayjs(startDate)}`;
                })()}
              </span>
            </Typography>
          ) : (
            <Typography variant="body2">{text}</Typography>
          )}
          <Stack direction="row" spacing={1}>
            <Tooltip title="View Recordings">
              <span>
                <IconButton
                  component={Link}
                  to={`/recordings/${camera_identifier}`}
                  disabled={!objHasValues(recording)}
                >
                  <FolderDetails size={20} />
                </IconButton>
              </span>
            </Tooltip>
            {!user || user.role === "admin" || user.role === "write" ? (
              <Tooltip title="Delete Recordings">
                <span>
                  <MutationIconButton
                    mutation={deleteRecording}
                    disabled={!objHasValues(recording)}
                    color="error"
                    onClick={() => {
                      deleteRecording.mutate({
                        identifier: camera_identifier,
                        failed,
                      });
                    }}
                  >
                    <TrashCan size={20} />
                  </MutationIconButton>
                </span>
              </Tooltip>
            ) : null}
          </Stack>
        </Stack>
      </CardActions>
    </Card>
  );
}
