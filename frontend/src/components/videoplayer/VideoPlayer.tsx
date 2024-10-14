import { FC, useEffect, useRef } from "react";
import videojs from "video.js";
import Player from "video.js/dist/types/player";
import "video.js/dist/video-js.css";

import "./VideoPlayer.css";

interface VideoPlayerPropsInferface {
  options: Record<string, any>;
  onReady?: (player: Player) => void;
}

const VideoJS: FC<VideoPlayerPropsInferface> = (props) => {
  const videoRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<Player | null>(null);
  const { options, onReady } = props;

  useEffect(() => {
    // Make sure Video.js player is only initialized once
    if (!playerRef.current) {
      // The Video.js player needs to be _inside_ the component el for React 18 Strict Mode.
      const videoElement = document.createElement("video-js");

      videoElement.classList.add("vjs-big-play-centered");
      videoRef.current!.appendChild(videoElement);

      // eslint-disable-next-line no-multi-assign
      const player = (playerRef.current = videojs(videoElement, options, () => {
        player.autoplay(options.autoplay);
        player.src(options.sources);
        player.poster(options.poster!);
        player.load();
      }));
    } else {
      const player = playerRef.current;

      player.autoplay(options.autoplay);
      player.src(options.sources);
      player.poster(options.poster!);
      player.load();
    }
  }, [onReady, options, videoRef]);

  // Dispose the Video.js player when the functional component unmounts
  useEffect(() => {
    const player = playerRef.current;

    return () => {
      if (player && !player.isDisposed()) {
        player.dispose();
        playerRef.current = null;
      }
    };
  }, [playerRef]);

  return (
    <div data-vjs-player data-testid="video-player">
      <div ref={videoRef} />
    </div>
  );
};

const VideoPlayer: FC<VideoPlayerPropsInferface> = ({ options }) => {
  const onReady = (player: Player) => {
    player.autoplay(options.autoplay);
    player.src(options.sources);
    player.poster(options.poster!);
    player.load();
  };

  return <VideoJS options={options} onReady={onReady} />;
};

export default VideoPlayer;
