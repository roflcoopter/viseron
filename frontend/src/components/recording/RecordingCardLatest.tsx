import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import VideoFileIcon from "@mui/icons-material/VideoFile";
import { CardActions, CardMedia } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { AxiosError } from "axios";
import LazyLoad from "react-lazyload";
import { useMutation } from "react-query";
import { Link } from "react-router-dom";

import MutationIconButton from "components/buttons/MutationIconButton";
import VideoPlayer from "components/videoplayer/VideoPlayer";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { deleteRecordingParams } from "lib/api";
import { getRecordingVideoJSOptions, objIsEmpty } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardLatestProps {
  camera: types.Camera;
}

function getLatestRecording(recordings: types.Recordings) {
  if (objIsEmpty(recordings)) {
    return null;
  }

  const latestDate = Object.keys(recordings).sort().reverse()[0];
  const latestRecordings = recordings[latestDate];
  if (objIsEmpty(latestRecordings)) {
    return null;
  }

  return latestRecordings[Object.keys(latestRecordings).sort().reverse()[0]];
}

function getVideoElement(
  camera: types.Camera,
  latestRecording: types.Recording | null
) {
  if (latestRecording === null) {
    return <VideoPlayerPlaceholder camera={camera} />;
  }

  const videoJsOptions = getRecordingVideoJSOptions(latestRecording);
  return <VideoPlayer recording={latestRecording} options={videoJsOptions} />;
}

export default function RecordingCardLatest({
  camera,
}: RecordingCardLatestProps) {
  const recordings = camera.recordings;
  const latestRecording = getLatestRecording(recordings);
  const deleteRecording = useMutation<
    types.APISuccessResponse,
    AxiosError<types.APIErrorResponse>,
    deleteRecordingParams
  >("deleteRecording");

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {camera.name}
          </Typography>
          {latestRecording ? (
            <Typography align="center">{`Latest recording: ${
              latestRecording.date
            } - ${latestRecording.filename.split(".")[0]}`}</Typography>
          ) : (
            <Typography align="center">No recordings found</Typography>
          )}
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(camera, latestRecording)}
          </LazyLoad>
        </CardMedia>
        <CardActions>
          <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
            <Tooltip title="View Recordings">
              <IconButton
                component={Link}
                to={`/recordings/${camera.identifier}`}
                disabled={latestRecording === null}
              >
                <VideoFileIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete Recordings">
              <MutationIconButton<deleteRecordingParams>
                mutation={deleteRecording}
                disabled={latestRecording === null}
                onClick={() => {
                  deleteRecording.mutate({
                    identifier: camera.identifier,
                  });
                }}
              >
                <DeleteForeverIcon />
              </MutationIconButton>
            </Tooltip>
          </Stack>
        </CardActions>
      </Card>
    </LazyLoad>
  );
}
