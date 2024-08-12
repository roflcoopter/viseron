import { render, waitFor } from "@testing-library/react";

import {
  getRecordingVideoJSOptions,
  getVideoElement,
  objHasValues,
  objIsEmpty,
  removeURLParameter,
  sortObj,
  toTitleCase,
} from "lib/helpers";
import * as types from "lib/types";

describe("sortObj", () => {
  it("should sort the object keys in ascending order", () => {
    const obj = { c: 3, a: 1, b: 2 };
    const sortedObj = sortObj(obj);
    expect(Object.keys(sortedObj)).toEqual(["a", "b", "c"]);
  });
});

describe("objIsEmpty", () => {
  it("should return true if the object is empty", () => {
    const obj = {};
    expect(objIsEmpty(obj)).toBe(true);
  });

  it("should return false if the object is not empty", () => {
    const obj = { a: 1 };
    expect(objIsEmpty(obj)).toBe(false);
  });

  it("should return true if the object is null", () => {
    const obj = null;
    expect(objIsEmpty(obj)).toBe(true);
  });

  it("should return true if the object is undefined", () => {
    const obj = undefined;
    expect(objIsEmpty(obj)).toBe(true);
  });
});

describe("objHasValues", () => {
  it("should return true if the object has values", () => {
    const obj = { a: 1 };
    expect(objHasValues(obj)).toBe(true);
  });

  it("should return false if the object is empty", () => {
    const obj = {};
    expect(objHasValues(obj)).toBe(false);
  });

  it("should return false if the object is null", () => {
    const obj = null;
    expect(objHasValues(obj)).toBe(false);
  });

  it("should return false if the object is undefined", () => {
    const obj = undefined;
    expect(objHasValues(obj)).toBe(false);
  });
});

describe("getRecordingVideoJSOptions", () => {
  it("should return the correct videoJS options", () => {
    const recording: types.Recording = {
      thumbnail_path: "thumbnail.jpg",
      hls_url: "video.m3u8",
      id: 0,
      camera_identifier: "",
      start_time: "",
      start_timestamp: 0,
      end_time: "",
      end_timestamp: 0,
      date: "",
      trigger_type: "",
      trigger_id: 0,
    };
    const options = getRecordingVideoJSOptions(recording);
    expect(options).toEqual({
      autoplay: false,
      playsinline: true,
      controls: true,
      loop: true,
      poster: "thumbnail.jpg",
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
          src: "video.m3u8",
          type: "application/x-mpegURL",
        },
      ],
    });
  });
});

describe("getVideoElement", () => {
  it("should render VideoPlayerPlaceholder if recording is null", () => {
    const camera: types.Camera = {
      width: 1920,
      height: 1080,
      identifier: "",
      name: "",
      access_token: "",
      still_image_refresh_interval: 0,
      failed: false,
      is_on: true,
      connected: true,
    };
    const { getByTestId } = render(getVideoElement(camera, null, false));
    expect(getByTestId("video-player-placeholder")).toBeInTheDocument();
  });

  it("should render VideoPlayerPlaceholder if recording is undefined", () => {
    const camera: types.Camera = {
      width: 1920,
      height: 1080,
      identifier: "",
      name: "",
      access_token: "",
      still_image_refresh_interval: 0,
      failed: false,
      is_on: true,
      connected: true,
    };

    const { getByTestId } = render(getVideoElement(camera, undefined, false));
    expect(getByTestId("video-player-placeholder")).toBeInTheDocument();
  });

  it("should render VideoPlayer if recording has values", async () => {
    const camera: types.Camera = {
      width: 1920,
      height: 1080,
      identifier: "",
      name: "",
      access_token: "",
      still_image_refresh_interval: 0,
      failed: false,
      is_on: true,
      connected: true,
    };
    const recording: types.Recording = {
      thumbnail_path: "thumbnail.jpg",
      hls_url: "video.m3u8",
      id: 0,
      camera_identifier: "",
      start_time: "",
      start_timestamp: 0,
      end_time: "",
      end_timestamp: 0,
      date: "",
      trigger_type: "",
      trigger_id: 0,
    };
    const { getByTestId } = render(getVideoElement(camera, recording, false));
    await waitFor(() =>
      expect(getByTestId("video-player")).toBeInTheDocument(),
    );
  });
});

describe("toTitleCase", () => {
  it("should convert the string to title case", () => {
    const str = "hello world";
    expect(toTitleCase(str)).toBe("Hello world");
  });
});

describe("removeURLParameter", () => {
  it("should remove the specified parameter from the URL", () => {
    const url = "https://example.com?param1=value1&param2=value2";
    const parameter = "param1";
    const newURL = removeURLParameter(url, parameter);
    expect(newURL).toBe("https://example.com?param2=value2");
  });

  it("should return the same URL if the parameter does not exist", () => {
    const url = "https://example.com?param1=value1&param2=value2";
    const parameter = "param3";
    const newURL = removeURLParameter(url, parameter);
    expect(newURL).toBe(url);
  });
});
