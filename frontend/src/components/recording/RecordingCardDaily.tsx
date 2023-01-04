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

interface RecordingCardDailyProps {
  camera: types.Camera;
  date: string;
}

function getLatestRecordingDate(recordings: types.Recordings, date: string) {
  if (objIsEmpty(recordings)) {
    return null;
  }

  const dailyRecordings = recordings[date];
  if (objIsEmpty(dailyRecordings)) {
    return null;
  }

  return dailyRecordings[Object.keys(dailyRecordings).sort().reverse()[0]];
}

function getVideoElement(
  camera: types.Camera,
  lastRecording: types.Recording | null
) {
  if (lastRecording === null) {
    return <VideoPlayerPlaceholder camera={camera} />;
  }

  const videoJsOptions = getRecordingVideoJSOptions(lastRecording);
  return <VideoPlayer recording={lastRecording} options={videoJsOptions} />;
}

export default function RecordingCardDaily({
  camera,
  date,
}: RecordingCardDailyProps) {
  const recordings = camera.recordings;
  const lastRecording = getLatestRecordingDate(recordings, date);
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
            {date}
          </Typography>
          {lastRecording ? (
            <Typography align="center">{`Last recording: ${
              lastRecording.filename.split(".")[0]
            }`}</Typography>
          ) : (
            <Typography align="center">No recordings found</Typography>
          )}
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            offset={500}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(camera, lastRecording)}
          </LazyLoad>
        </CardMedia>
        <CardActions>
          <Stack direction="row" spacing={1} sx={{ ml: "auto" }}>
            <Tooltip title="View Recordings">
              <IconButton
                component={Link}
                to={`/recordings/${camera.identifier}/${date}`}
                disabled={lastRecording === null}
              >
                <VideoFileIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete Recordings">
              <MutationIconButton<deleteRecordingParams>
                mutation={deleteRecording}
                disabled={lastRecording === null}
                onClick={() => {
                  deleteRecording.mutate({
                    identifier: camera.identifier,
                    date,
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
