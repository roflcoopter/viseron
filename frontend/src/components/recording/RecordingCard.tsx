import { CardMedia } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import LazyLoad from "react-lazyload";

import VideoPlayer from "components/videoplayer/VideoPlayer";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { getRecordingVideoJSOptions } from "lib/helpers";
import * as types from "lib/types";

interface RecordingCardInterface {
  camera: types.Camera;
  recording: types.Recording;
}

export default function RecordingCard({
  camera,
  recording,
}: RecordingCardInterface) {
  const videoJsOptions = getRecordingVideoJSOptions(recording);

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardContent>
          <Typography align="center">
            {recording.filename.split(".")[0]}
          </Typography>
        </CardContent>
        <CardMedia>
          <LazyLoad
            height={200}
            offset={500}
            placeholder={<VideoPlayerPlaceholder camera={camera} />}
          >
            <VideoPlayer
              recording={recording}
              options={videoJsOptions}
              overlay={false}
            />
          </LazyLoad>
        </CardMedia>
      </Card>
    </LazyLoad>
  );
}
