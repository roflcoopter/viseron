import * as types from "lib/types";

// No idea how to type this...
export function sortObj(obj: any) {
  return Object.keys(obj).sort().reduce((result: any, key: any) => {
    result[key] = obj[key];
    return result;
  }, {});
}

export function objIsEmpty(obj: any) {
  return Object.keys(obj).length === 0;
}

export function getRecordingVideoJSOptions(recording: types.Recording) {
  return {
    autoplay: false,
    playsinline: true,
    controls: true,
    loop: true,
    poster: process.env.REACT_APP_PROXY_HOST
      ? `http://${process.env.REACT_APP_PROXY_HOST}${recording.thumbnail_path}`
      : `${recording.thumbnail_path}`,
    preload: "none",
    responsive: true,
    fluid: true,
    playbackRates: [0.5, 1, 2, 5, 10],
    sources: [
      {
        src: process.env.REACT_APP_PROXY_HOST
          ? `http://${process.env.REACT_APP_PROXY_HOST}${recording.path}`
          : `${recording.path}`,
        type: "video/mp4",
      },
    ],
  };
}

export function toTitleCase(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase()
}
