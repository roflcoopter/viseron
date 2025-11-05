import { 
  TrashCan,
  DocumentVideo,
} from "@carbon/icons-react";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import CardMedia from "@mui/material/CardMedia";
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
import { getTimeFromDate, getVideoElement, objHasValues } from "lib/helpers";
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
    const startDate = new Date(recording.start_time);
    text = `Latest recording: ${startDate.toLocaleDateString()} - ${getTimeFromDate(
      new Date(recording.start_time),
    )}`;
  }

  if (cameraQuery.isPending || !cameraQuery.data) {
    return null;
  }

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
        <Typography variant="h5" align="center">
          {cameraQuery.data.name}
        </Typography>
        <Typography align="center">{text}</Typography>
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
          {getVideoElement(cameraQuery.data, recording, auth.enabled)}
        </LazyLoad>
      </CardMedia>
      <CardActions>
        <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
          <Tooltip title="View Recordings">
            <span>
              <IconButton
                component={Link}
                to={`/recordings/${camera_identifier}`}
                disabled={!objHasValues(recording)}
              >
                <DocumentVideo size={20}/>
              </IconButton>
            </span>
          </Tooltip>
          {!user || user.role === "admin" || user.role === "write" ? (
            <Tooltip title="Delete Recordings">
              <MutationIconButton
                mutation={deleteRecording}
                disabled={!objHasValues(recording)}
                onClick={() => {
                  deleteRecording.mutate({
                    identifier: camera_identifier,
                    failed,
                  });
                }}
              >
                <TrashCan size={20}/>
              </MutationIconButton>
            </Tooltip>
          ) : null}
        </Stack>
      </CardActions>
    </Card>
  );
}
