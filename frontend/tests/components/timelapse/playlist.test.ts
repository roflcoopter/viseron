import { describe, expect, test } from "vitest";

import {
  buildTimelapsePlaylist,
  frameAt,
  frameIndexAtOrAfter,
  frameTime,
  isBuffered,
} from "components/timelapse/playlist";
import { API_V1_URL } from "lib/api/client";
import * as types from "lib/types";

const STREAM: types.TimelapseStream = {
  fps: 15,
  segment_frames: 2,
  width: 1280,
  height: 720,
};

const makeFrames = (fileKeys: number[]): types.TimelapseFrame[] =>
  fileKeys.map((file_key, i) => ({
    file_key,
    timestamp: 1000 + i * 5,
    path: `/files/${file_key}.jpg`,
  }));

const segmentUrl = (keys: string, startFrame: number) =>
  `${window.location.origin}${API_V1_URL}/timelapse/camera1/segment` +
  `?keys=${keys}&start_frame=${startFrame}&width=1280&height=720`;

describe("buildTimelapsePlaylist", () => {
  test("splits the frames into segments of segment_frames frames", () => {
    expect(
      buildTimelapsePlaylist("camera1", makeFrames([1, 26, 255]), STREAM),
    ).toBe(
      [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:1",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD",
        "#EXTINF:0.133,",
        segmentUrl("1%2C1a", 0),
        "#EXTINF:0.067,",
        segmentUrl("ff", 2),
        "#EXT-X-ENDLIST",
      ].join("\n"),
    );
  });
});

describe("frame and time mapping", () => {
  test("frameAt is the inverse of frameTime", () => {
    const indexes = Array.from({ length: 100 }, (_, i) => i);
    expect(indexes.map((i) => frameAt(frameTime(i, 15), 15))).toEqual(indexes);
  });

  test.each([
    { timestamp: 0, expected: 0 },
    { timestamp: 1003, expected: 1 },
    { timestamp: 1010, expected: 2 },
    { timestamp: 2000, expected: 2 },
  ])(
    "frameIndexAtOrAfter($timestamp) is $expected",
    ({ timestamp, expected }) => {
      expect(frameIndexAtOrAfter(makeFrames([1, 2, 3]), timestamp)).toBe(
        expected,
      );
    },
  );
});

describe("isBuffered", () => {
  const ranges = (buffered: [number, number][]) =>
    ({
      length: buffered.length,
      start: (i: number) => buffered[i][0],
      end: (i: number) => buffered[i][1],
    }) as TimeRanges;

  test.each([
    { time: 1, expected: false },
    { time: 2, expected: true },
    { time: 3.5, expected: true },
    { time: 5, expected: false },
    { time: 6.5, expected: true },
  ])("time $time is buffered: $expected", ({ time, expected }) => {
    expect(
      isBuffered(
        ranges([
          [2, 4],
          [6, 8],
        ]),
        time,
      ),
    ).toBe(expected);
  });

  test("nothing is buffered before loading", () => {
    expect(isBuffered(ranges([]), 0)).toBe(false);
  });
});
