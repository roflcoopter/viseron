import { CardActionArea, CardActions } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import LazyLoad from "react-lazyload";

import { CardActionButtonLink } from "components/CardActionButton";
import VideoPlayer from "components/videoplayer/VideoPlayer";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
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

function getVideoElement(latestRecording: types.Recording | null) {
  if (latestRecording === null) {
    return <Typography align="center">No recordings found</Typography>;
  }

  const videoJsOptions = getRecordingVideoJSOptions(latestRecording);
  return <VideoPlayer recording={latestRecording} options={videoJsOptions} />;
}

export default function RecordingCardLatest({
  camera,
}: RecordingCardLatestProps) {
  const recordings = camera.recordings;
  const latestRecording = getLatestRecording(recordings);

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {camera.name}
          </Typography>
          {latestRecording && (
            <Typography align="center">{`Latest recording: ${
              latestRecording.date
            } - ${latestRecording.filename.split(".")[0]}`}</Typography>
          )}
        </CardContent>
        <CardActionArea>
          <LazyLoad
            height={200}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(latestRecording)}
          </LazyLoad>
        </CardActionArea>
        <CardActions>
          <CardActionButtonLink
            title="View Recordings"
            target={`/recordings/${camera.identifier}`}
            width="100%"
          />
        </CardActions>
      </Card>
    </LazyLoad>
  );
}
