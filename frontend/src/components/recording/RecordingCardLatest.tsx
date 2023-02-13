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
import { deleteRecordingParams, useDeleteRecording } from "lib/api/client";
import { getVideoElement, objHasValues } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardLatestProps {
  camera: types.Camera;
}

export default function RecordingCardLatest({
  camera,
}: RecordingCardLatestProps) {
  const deleteRecording = useDeleteRecording();

  const { status, data: recordings } = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${camera.identifier}?latest`],
  });

  let recording: types.Recording | undefined;
  if (
    objHasValues<types.RecordingsCamera>(recordings) &&
    objHasValues<types.RecordingsCamera>(Object.values(recordings)[0]) &&
    objHasValues<types.RecordingsCamera>(
      Object.values(Object.values(recordings)[0])[0]
    )
  ) {
    const recordingDate = Object.values(recordings)[0];
    recording = Object.values(recordingDate)[0];
  }

  let text = "No recordings found";
  if (status === "error") {
    text = "Error getting latest recording";
  } else if (status === "loading") {
    text = "Loading latest recording";
  } else if (status === "success" && !objHasValues(recording)) {
    text = "No recordings found";
  } else if (status === "success" && objHasValues(recording) && recording) {
    text = `Latest recording: ${recording.date} - ${
      recording.filename.split(".")[0]
    }`;
  }

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {camera.name}
          </Typography>
          <Typography align="center">{text}</Typography>
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(camera, recording)}
          </LazyLoad>
        </CardMedia>
        <CardActions>
          <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
            <Tooltip title="View Recordings">
              <span>
                <IconButton
                  component={Link}
                  to={`/recordings/${camera.identifier}`}
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
                      identifier: camera.identifier,
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
