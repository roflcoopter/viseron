import { Suspense, lazy } from "react";

import VideoPlayerPlaceholder from "components/videoplayer/VideoPlayerPlaceholder";
import * as types from "lib/types";

import { getAuthHeader } from "./tokens";

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

export function getRecordingVideoJSOptions(
  recording: types.Recording,
  auth_token?: string,
) {
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
    liveui: true,
    liveTracker: {
      trackingThreshold: 0,
    },
    html5: {
      vhs: {
        experimentalLLHLS: true,
      },
    },
    sources: [
      {
        src: recording.hls_url + (auth_token ? `?token=${auth_token}` : ""),
        type: "application/x-mpegURL",
      },
    ],
  };
}

export function getVideoElement(
  camera: types.Camera | types.FailedCamera,
  recording: types.Recording | null | undefined,
  auth: boolean,
) {
  if (!objHasValues(recording) || !recording) {
    return (
      <VideoPlayerPlaceholder aspectRatio={camera.width / camera.height} />
    );
  }

  let authHeader: string | null = null;
  if (auth) {
    authHeader = getAuthHeader();
  }
  const videoJsOptions = getRecordingVideoJSOptions(
    recording,
    authHeader || undefined,
  );
  return (
    <Suspense
      fallback={
        <VideoPlayerPlaceholder aspectRatio={camera.width / camera.height} />
      }
    >
      <VideoPlayer options={videoJsOptions} />
    </Suspense>
  );
}

export function toTitleCase(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// eslint-disable-next-line no-promise-executor-return
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function getTimeFromDate(date: Date, seconds = true) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds && { second: "2-digit" }),
  });
}

export const dateToTimestamp = (date: Date) =>
  Math.floor(date.getTime() / 1000);

export const timestampToDate = (timestamp: number) =>
  new Date(timestamp * 1000);

export function removeURLParameter(url: string, parameter: string) {
  const [base, queryString] = url.split("?");
  if (!queryString) {
    return url;
  }
  const params = queryString
    .split("&")
    .filter((param) => !param.startsWith(`${parameter}=`));
  return params.length ? `${base}?${params.join("&")}` : base;
}

export function insertURLParameter(key: string, value: string | number) {
  // remove any param for the same key
  const currentURL = removeURLParameter(window.location.href, key);

  // figure out if we need to add the param with a ? or a &
  let queryStart;
  if (currentURL.indexOf("?") !== -1) {
    queryStart = "&";
  } else {
    queryStart = "?";
  }

  const newurl = `${currentURL + queryStart + key}=${value}`;
  window.history.pushState({ path: newurl }, "", newurl);
}
