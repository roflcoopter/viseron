import * as React from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";
import "videojs-overlay";
import "videojs-overlay/dist/videojs-overlay.css";

import * as types from "lib/types";

import "./VideoPlayer.css";

interface VideoPlayerPropsInferface {
  recording: types.Recording;
  options: videojs.PlayerOptions;
}

type OverlayBase = {
  align?:
    | "top-left"
    | "top"
    | "top-right"
    | "right"
    | "bottom-right"
    | "bottom"
    | "bottom-left"
    | "left";
  class?: string;
  content?: string;
};

type VideoJsOverlayOptions = OverlayBase & {
  showBackground?: boolean;
  attachToControlBar?: boolean;

  overlays: OverlayBase &
    {
      start?: string | number;
      end?: string | number;
    }[];
};

type VideoJsPlayerOverlay = videojs.Player & {
  overlay: (overlays: VideoJsOverlayOptions) => void;
};

const VideoPlayer: React.FC<VideoPlayerPropsInferface> = ({
  recording,
  options,
}) => {
  const videoNode = React.useRef<HTMLVideoElement>(null);
  const player = React.useRef<videojs.Player>();

  React.useEffect(() => {
    if (!player.current) {
      player.current = videojs(videoNode.current!, options, () => {
        (player.current as VideoJsPlayerOverlay).overlay({
          class: "videojs-overlay-custom",
          overlays: [
            {
              content: recording.filename.split(".")[0],
              start: "loadstart",
              end: "play",
            },
            {
              content: recording.filename.split(".")[0],
              start: "pause",
              end: "play",
            },
          ],
        });
      });
    }
    return () => {
      if (player.current) {
        player.current.dispose();
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div data-vjs-player>
      <video ref={videoNode} className="video-js vjs-big-play-centered" />
    </div>
  );
};

export default VideoPlayer;
