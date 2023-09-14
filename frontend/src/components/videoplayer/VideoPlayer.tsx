import { FC, useEffect, useRef, useState } from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";

import "./VideoPlayer.css";

interface VideoPlayerPropsInferface {
  options: videojs.PlayerOptions;
}

const VideoPlayer: FC<VideoPlayerPropsInferface> = ({ options }) => {
  const videoNode = useRef<HTMLVideoElement>(null);
  const player = useRef<videojs.Player>();
  const [source, setSource] = useState<string>(options.sources![0].src);

  useEffect(() => {
    if (!player.current) {
      player.current = videojs(videoNode.current!, options, () => {});
    }
    return () => {
      if (player.current) {
        player.current.dispose();
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (player.current && source !== options.sources![0].src) {
    player.current.src(options.sources!);
    player.current.poster(options.poster!);
    player.current.load();
    setSource(options.sources![0].src);
  }

  return (
    <div data-vjs-player>
      <video ref={videoNode} className="video-js vjs-big-play-centered" />
    </div>
  );
};

export default VideoPlayer;
