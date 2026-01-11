import dayjs, { Dayjs } from "dayjs";
import { Suspense, lazy } from "react";

import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import queryClient from "lib/api/client";
import { getAuthHeader } from "lib/tokens";
import * as types from "lib/types";

export const DATE_FORMAT = "YYYY-MM-DD";

const VideoPlayer = lazy(
  () => import("components/player/videoplayer/VideoPlayer"),
);

export const BLANK_IMAGE =
  "data:image/svg+xml;charset=utf8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E";

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
  authEnabled: boolean,
) {
  if (!objHasValues(recording) || !recording) {
    return (
      <VideoPlayerPlaceholder
        aspectRatio={camera.mainstream.width / camera.mainstream.height}
      />
    );
  }

  let authHeader: string | null = null;
  if (authEnabled) {
    authHeader = getAuthHeader();
  }
  const videoJsOptions = getRecordingVideoJSOptions(
    recording,
    authHeader || undefined,
  );
  return (
    <Suspense
      fallback={
        <VideoPlayerPlaceholder
          aspectRatio={camera.mainstream.width / camera.mainstream.height}
        />
      }
    >
      <VideoPlayer options={videoJsOptions} />
    </Suspense>
  );
}

export function toTitleCase(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

export function capitalizeEachWord(str: string) {
  return str
    .replace(/-/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

// eslint-disable-next-line no-promise-executor-return
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Get a timezone aware dayjs instance for the current time
export function getDayjs() {
  return dayjs().tz();
}

// Get a timezone aware dayjs instance from a Date object
export function getDayjsFromDate(date: Date) {
  return dayjs(date).tz();
}

// Get a timezone aware dayjs instance from a time string
// eg. "2026-01-10T17:20:09.263303+00:00"
export function getDayjsFromDateTimeString(dateString: string) {
  return dayjs(dateString).tz();
}

// Get a timezone aware dayjs instance from a date string
// eg. "2026-01-10"
export function getDayjsFromDateString(dateString: string) {
  return dayjs.tz(dateString);
}

// Get a timezone aware dayjs instance from a unix timestamp
// Supports both seconds and milliseconds
// Milliseconds are converted to seconds
export function getDayjsFromUnixTimestamp(timestamp: number) {
  if (timestamp.toString().length === 13) {
    timestamp = Math.floor(timestamp / 1000);
  }
  return dayjs.unix(timestamp).tz();
}

// Format a dayjs instance to a time string HH:mm:ss or HH:mm
export function getTimeStringFromDayjs(date: Dayjs, seconds = true) {
  return date.format(seconds ? "HH:mm:ss" : "HH:mm");
}

// Format a dayjs instance to a date string YYYY-MM-DD
export function getDateStringFromDayjs(date: Dayjs) {
  return date.format(DATE_FORMAT);
}

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

export function throttle(func: () => void, timeFrame: number) {
  let lastTime = 0;
  return () => {
    const now = new Date().getTime();
    if (now - lastTime >= timeFrame) {
      func();
      lastTime = now;
    }
  };
}

export function isTouchDevice() {
  return "ontouchstart" in window || navigator.maxTouchPoints > 0;
}

export function getCameraFromQueryCache(
  camera_identifier: string,
): types.Camera | types.FailedCamera | undefined {
  return queryClient.getQueryData(["camera", camera_identifier]);
}

export function getCameraNameFromQueryCache(camera_identifier: string): string {
  const camera = getCameraFromQueryCache(camera_identifier);
  return camera ? camera.name : camera_identifier;
}
