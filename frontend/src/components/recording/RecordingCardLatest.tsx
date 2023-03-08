import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import { CardActions, CardMedia } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import LazyLoad from "react-lazyload";
import { Link } from "react-router-dom";

import MutationIconButton from "components/buttons/MutationIconButton";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { useCamera } from "lib/api/camera";
import { deleteRecordingParams, useDeleteRecording } from "lib/api/client";
import { getVideoElement, objHasValues } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardLatestProps {
  camera_identifier: string;
}

export default function RecordingCardLatest({
  camera_identifier,
}: RecordingCardLatestProps) {
  const deleteRecording = useDeleteRecording();

  const recordingsQuery = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${camera_identifier}?latest`],
  });
  const cameraQuery = useCamera({ camera_identifier });

  let recording: types.Recording | undefined;
  if (
    objHasValues<types.RecordingsCamera>(recordingsQuery.data) &&
    objHasValues<types.RecordingsCamera>(
      Object.values(recordingsQuery.data)[0]
    ) &&
    objHasValues<types.RecordingsCamera>(
      Object.values(Object.values(recordingsQuery.data)[0])[0]
    )
  ) {
    const recordingDate = Object.values(recordingsQuery.data)[0];
    recording = Object.values(recordingDate)[0];
  }

  let text = "No recordings found";
  if (recordingsQuery.status === "error") {
    text = "Error getting latest recording";
  } else if (recordingsQuery.status === "loading") {
    text = "Loading latest recording";
  } else if (recordingsQuery.status === "success" && !objHasValues(recording)) {
    text = "No recordings found";
  } else if (
    recordingsQuery.status === "success" &&
    objHasValues(recording) &&
    recording
  ) {
    text = `Latest recording: ${recording.date} - ${
      recording.filename.split(".")[0]
    }`;
  }

  if (cameraQuery.isLoading || !cameraQuery.data) {
    return null;
  }

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {cameraQuery.data.name}
          </Typography>
          <Typography align="center">{text}</Typography>
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            placeholder={<VideoPlayerPlaceholder camera={cameraQuery.data} />}
          >
            {getVideoElement(cameraQuery.data, recording)}
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
                  <VideoFileIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Delete Recordings">
              <span>
                <MutationIconButton<deleteRecordingParams>
                  mutation={deleteRecording}
                  disabled={!objHasValues(recording)}
                  onClick={() => {
                    deleteRecording.mutate({
                      identifier: camera_identifier,
                    });
                  }}
                >
                  <DeleteForeverIcon />
                </MutationIconButton>
              </span>
            </Tooltip>
          </Stack>
        </CardActions>
      </Card>
    </LazyLoad>
  );
}
