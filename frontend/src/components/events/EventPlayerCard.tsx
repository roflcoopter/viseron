import Card from "@mui/material/Card";
import CardMedia from "@mui/material/CardMedia";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import Hls from "hls.js";
import { useEffect, useRef } from "react";
import videojs from "video.js";
import Player from "video.js/dist/types/player";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { TimelinePlayer } from "components/events/timeline/TimelinePlayer";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import { useAuthContext } from "context/AuthContext";
import { getAuthHeader } from "lib/tokens";
import * as types from "lib/types";

dayjs.extend(utc);

const _videoJsOptions = {
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

const useInitializePlayer = (
  videoNode: React.RefObject<HTMLVideoElement>,
  player: React.MutableRefObject<Player | undefined>,
  source: string,
) => {
  const { auth } = useAuthContext();

  useEffect(() => {
    if (!player.current) {
      const separator = source.includes("?") ? "&" : "?";
      player.current = videojs(
        videoNode.current!,
        {
          ..._videoJsOptions,
          sources: [
            {
              src:
                source + (auth ? `${separator}token=${getAuthHeader()}` : ""),
              type: "application/x-mpegURL",
            },
          ],
        },
        () => {},
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
};

const useSourceChange = (
  player: React.MutableRefObject<Player | undefined>,
  source: string,
) => {
  const { auth } = useAuthContext();

  useEffect(() => {
    if (player.current) {
      const separator = source.includes("?") ? "&" : "?";
      player.current.reset();
      player.current.src([
        {
          src: source + (auth ? `${separator}token=${getAuthHeader()}` : ""),
          type: "application/x-mpegURL",
        },
      ]);
      player.current.load();
    }
  }, [auth, player, source]);
};

type EventPlayerProps = {
  source: string;
};

const EventPlayer = ({ source }: EventPlayerProps) => {
  const videoNode = useRef<HTMLVideoElement>(null);
  const player = useRef<Player>();

  useInitializePlayer(videoNode, player, source);
  useSourceChange(player, source);

  return (
    <div data-vjs-player>
      <video ref={videoNode} className="video-js vjs-big-play-centered" />
    </div>
  );
};

type PlayerCardProps = {
  camera: types.Camera | null;
  eventSource: string | null;
  requestedTimestamp: number | null;
  selectedTab: "events" | "timeline";
  hlsRef: React.MutableRefObject<Hls | null>;
};

export const PlayerCard = ({
  camera,
  eventSource,
  requestedTimestamp,
  selectedTab,
  hlsRef,
}: PlayerCardProps) => {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <Card
      ref={ref}
      variant="outlined"
      sx={{
        marginBottom: "10px",
        position: "relative",
      }}
    >
      {camera && <CameraNameOverlay camera={camera} />}
      <CardMedia>
        {eventSource && selectedTab === "events" ? (
          <EventPlayer source={eventSource} />
        ) : camera && requestedTimestamp && selectedTab === "timeline" ? (
          <TimelinePlayer
            containerRef={ref}
            hlsRef={hlsRef}
            camera={camera}
            requestedTimestamp={requestedTimestamp}
          />
        ) : (
          <VideoPlayerPlaceholder
            aspectRatio={camera ? camera.width / camera.height : undefined}
            text={camera ? "Select an event" : "Select a camera"}
          />
        )}
      </CardMedia>
    </Card>
  );
};
