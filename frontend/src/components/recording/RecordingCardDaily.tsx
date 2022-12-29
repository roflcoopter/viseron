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

function getVideoElement(lastRecording: types.Recording | null) {
  if (lastRecording === null) {
    return <Typography align="center">No recordings found</Typography>;
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
  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h5" align="center">
            {date}
          </Typography>
          {lastRecording && (
            <Typography align="center">{`Last recording: ${
              lastRecording.filename.split(".")[0]
            }`}</Typography>
          )}
        </CardContent>
        <CardActionArea>
          <LazyLoad
            height={200}
            offset={500}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            {getVideoElement(lastRecording)}
          </LazyLoad>
        </CardActionArea>
        <CardActions>
          <CardActionButtonLink
            title="View Recordings"
            target={`/recordings/${camera.identifier}/${date}`}
            width="100%"
          />
        </CardActions>
      </Card>
    </LazyLoad>
  );
}
