import Card from "@mui/material/Card";
import CardMedia from "@mui/material/CardMedia";
import { useEffect, useRef } from "react";
import videojs from "video.js";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import * as types from "lib/types";

const _videoJsOptions: videojs.PlayerOptions = {
  autoplay: true,
  playsinline: true,
  controls: true,
  loop: true,
  preload: undefined,
  responsive: true,
  fluid: false,
  aspectRatio: "16:9",
  fill: true,
  playbackRates: [0.5, 1, 2, 5, 10],
  liveui: true,
  liveTracker: {
    trackingThreshold: 0,
  },
  html5: {
    vhs: {
      experimentalLLHLS: true,
    },
  },
};

type EventPlayerProps = {
  recording: types.Recording;
};
const EventPlayer = ({ recording }: EventPlayerProps) => {
  const videoNode = useRef<HTMLVideoElement>(null);
  const player = useRef<videojs.Player>();

  useEffect(() => {
    if (!player.current) {
      player.current = videojs(
        videoNode.current!,
        {
          ..._videoJsOptions,
          sources: [{ src: recording.hls_url, type: "application/x-mpegURL" }],
        },
        () => {}
      );
    }
    return () => {
      if (player.current) {
        player.current.dispose();
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (player.current) {
      player.current.reset();
      player.current.src([
        {
          src: recording.hls_url,
          type: "application/x-mpegURL",
        },
      ]);
      player.current.load();
    }
  }, [recording]);

  return (
    <div data-vjs-player>
      <video ref={videoNode} className="video-js vjs-big-play-centered" />
    </div>
  );
};

type PlayerCardProps = {
  camera: types.Camera | null;
  recording: types.Recording | null;
};

export const PlayerCard = ({ camera, recording }: PlayerCardProps) => (
  <Card
    variant="outlined"
    sx={{
      marginBottom: "10px",
      position: "relative",
    }}
  >
    {camera && <CameraNameOverlay camera={camera} />}
    <CardMedia>
      {recording ? (
        <EventPlayer recording={recording} />
      ) : (
        <VideoPlayerPlaceholder
          aspectRatio={camera ? camera.width / camera.height : undefined}
          text={camera ? "Select an event" : "Select a camera"}
        />
      )}
    </CardMedia>
  </Card>
);
