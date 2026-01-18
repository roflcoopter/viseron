import { Suspense, lazy } from "react";

import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

const HlsVodPlayer = lazy(
  () => import("components/player/hlsplayer/HlsVodPlayer"),
);

export function getVideoElement(
  camera: types.Camera | types.FailedCamera,
  recording: types.Recording | null | undefined,
) {
  if (!objHasValues(recording) || !recording) {
    return (
      <VideoPlayerPlaceholder
        aspectRatio={camera.mainstream.width / camera.mainstream.height}
      />
    );
  }

  return (
    <Suspense
      fallback={
        <VideoPlayerPlaceholder
          aspectRatio={camera.mainstream.width / camera.mainstream.height}
        />
      }
    >
      <HlsVodPlayer
        key={camera.identifier}
        camera={camera}
        recording={recording}
        loop
        poster={`${recording.thumbnail_path}`}
      />
    </Suspense>
  );
}
