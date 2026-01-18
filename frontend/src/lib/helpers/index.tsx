import queryClient from "lib/api/client";
import * as types from "lib/types";

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
