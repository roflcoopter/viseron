import VideoPlayer from "components/videoplayer/VideoPlayer";
import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import * as types from "lib/types";

// No idea how to type this...
export function sortObj(obj: any) {
  return Object.keys(obj)
    .sort()
    .reduce((result: any, key: any) => {
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
    preload: "none",
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
  camera: types.Camera,
  recording: types.Recording | null | undefined
) {
  if (!objHasValues(recording) || !recording) {
    return <VideoPlayerPlaceholder camera={camera} />;
  }

  const videoJsOptions = getRecordingVideoJSOptions(recording);
  return <VideoPlayer recording={recording} options={videoJsOptions} />;
}

export function toTitleCase(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// eslint-disable-next-line no-promise-executor-return
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
