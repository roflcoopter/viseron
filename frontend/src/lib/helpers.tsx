import { Suspense, lazy } from "react";

import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import * as types from "lib/types";

const VideoPlayer = lazy(() => import("components/videoplayer/VideoPlayer"));

export function sortObj(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.keys(obj)
    .sort()
    .reduce((result: Record<string, unknown>, key: string) => {
      result[key] = obj[key];
      return result;
    }, {});
}

export function objIsEmpty(obj: any) {
  if (obj === null || obj === undefined) {
    return true;
  }
  return Object.keys(obj).length === 0;
}

export function objHasValues<T = Record<never, never>>(obj: unknown): obj is T {
  return typeof obj === "object" && obj !== null && Object.keys(obj).length > 0;
}

export function getRecordingVideoJSOptions(recording: types.Recording) {
  return {
    autoplay: false,
    playsinline: true,
    controls: true,
    loop: true,
    poster: `${recording.thumbnail_path}`,
    preload: undefined,
    responsive: true,
    fluid: true,
    playbackRates: [0.5, 1, 2, 5, 10],
    sources: [
      {
        src: `${recording.path}`,
        type: "video/mp4",
      },
    ],
  };
}

export function getVideoElement(
  camera: types.Camera | types.FailedCamera,
  recording: types.Recording | null | undefined
) {
  if (!objHasValues(recording) || !recording) {
    return <VideoPlayerPlaceholder camera={camera} />;
  }

  const videoJsOptions = getRecordingVideoJSOptions(recording);
  return (
    <Suspense fallback={<VideoPlayerPlaceholder camera={camera} />}>
      <VideoPlayer options={videoJsOptions} />
    </Suspense>
  );
}

export function toTitleCase(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// eslint-disable-next-line no-promise-executor-return
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function getTimeFromDate(date: Date) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
