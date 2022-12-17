import { CardActionArea } from "@mui/material";
import Card from "@mui/material/Card";
import LazyLoad from "react-lazyload";

import VideoPlayer from "components/videoplayer/VideoPlayer";
import * as types from "lib/types";

interface RecordingCardInterface {
  recording: types.Recording;
}

export default function RecordingCard({ recording }: RecordingCardInterface) {
  const videoJsOptions = {
    autoplay: false,
    playsinline: true,
    controls: true,
    loop: true,
    poster: process.env.REACT_APP_PROXY_HOST
      ? `http://${process.env.REACT_APP_PROXY_HOST}${recording.thumbnail_path}`
      : `${recording.thumbnail_path}`,
    preload: "none",
    responsive: true,
    fluid: true,
    playbackRates: [0.5, 1, 2, 5, 10],
    sources: [
      {
        src: process.env.REACT_APP_PROXY_HOST
          ? `http://${process.env.REACT_APP_PROXY_HOST}${recording.path}`
          : `${recording.path}`,
        type: "video/mp4",
      },
    ],
  };

  return (
    <LazyLoad height={200}>
      <Card variant="outlined">
        <CardActionArea>
          <VideoPlayer recording={recording} options={videoJsOptions} />
        </CardActionArea>
      </Card>
    </LazyLoad>
  );
}
