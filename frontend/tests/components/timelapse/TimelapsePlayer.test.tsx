import { act, fireEvent, screen } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  TimelapsePlayer,
  findGaps,
} from "components/timelapse/TimelapsePlayer";
import * as types from "lib/types";

const { hlsInstances } = vi.hoisted(() => ({
  hlsInstances: [] as any[],
}));

vi.mock("hls.js", () => {
  class MockHls {
    handlers: Record<string, (...callbackArgs: any[]) => void> = {};

    on = vi.fn((event: string, callback: (...callbackArgs: any[]) => void) => {
      this.handlers[event] = callback;
    });

    attachMedia = vi.fn();

    loadSource = vi.fn();

    startLoad = vi.fn();

    recoverMediaError = vi.fn();

    destroy = vi.fn();

    constructor() {
      hlsInstances.push(this);
    }

    static isSupported = () => true;

    static Events = {
      MANIFEST_PARSED: "hlsManifestParsed",
      FRAG_LOADED: "hlsFragLoaded",
      ERROR: "hlsError",
    };

    // Read at import time by components/player/hlsplayer/utils
    static ErrorDetails = {
      FRAG_GAP: "fragGap",
      BUFFER_STALLED_ERROR: "bufferStalledError",
      BUFFER_SEEK_OVER_HOLE: "bufferSeekOverHole",
      MANIFEST_LOAD_ERROR: "manifestLoadError",
    };

    static ErrorTypes = {
      NETWORK_ERROR: "networkError",
      MEDIA_ERROR: "mediaError",
    };
  }

  return { default: MockHls };
});

const STREAM: types.TimelapseStream = {
  fps: 15,
  segment_frames: 60,
  width: 320,
  height: 240,
};

const makeFrames = (timestamps: number[]): types.TimelapseFrame[] =>
  timestamps.map((timestamp, i) => ({
    file_key: i,
    timestamp,
    path: `/files/frame${i}.jpg`,
  }));

const FRAMES = makeFrames([1000, 1005, 1010, 1015, 1020]);

let blobs: Blob[];

const latestHls = () => hlsInstances[hlsInstances.length - 1];

const video = () =>
  screen
    .getByTestId("timelapse-player")
    .querySelector("video") as HTMLVideoElement;

const position = () => screen.getByText(/^\d+ \/ \d+$/).textContent;

const still = () => screen.queryByTestId("timelapse-still") as HTMLImageElement;

const frameTime = (index: number) => (index + 0.5) / 15;

const seekTo = (index: number) =>
  fireEvent.change(screen.getByRole("slider"), { target: { value: index } });

const fireMedia = (event: string) => {
  act(() => {
    video().dispatchEvent(new Event(event));
  });
};

const player = (frames: types.TimelapseFrame[]) => (
  <TimelapsePlayer
    camera_identifier="camera1"
    frames={frames}
    step={null}
    stream={STREAM}
  />
);

const renderPlayer = () => renderWithContext(player(FRAMES));

describe("TimelapsePlayer", () => {
  beforeEach(() => {
    hlsInstances.length = 0;
    blobs = [];
    URL.createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return `blob:${blobs.length}`;
    });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(
      function play(this: HTMLMediaElement) {
        this.dispatchEvent(new Event("play"));
        return Promise.resolve();
      },
    );
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(
      function pause(this: HTMLMediaElement) {
        this.dispatchEvent(new Event("pause"));
      },
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("loads the playlist and shows the first frame without fetching segments", async () => {
    renderPlayer();
    const hls = latestHls();

    expect(hls.loadSource).toHaveBeenCalledWith("blob:1");
    expect(await blobs[0].text()).toContain("/timelapse/camera1/segment?");
    act(() => hls.handlers.hlsManifestParsed());
    expect(hls.startLoad).not.toHaveBeenCalled();
    expect(still().src).toContain("/files/frame0.jpg");
  });

  test.each([
    {
      name: "playing",
      start: () => fireEvent.click(screen.getByLabelText("Play")),
      startPosition: frameTime(0),
    },
    {
      name: "seeking",
      start: () => seekTo(4),
      startPosition: frameTime(4),
    },
  ])("$name starts loading segments once", ({ start, startPosition }) => {
    renderPlayer();
    const hls = latestHls();
    act(() => hls.handlers.hlsManifestParsed());

    start();
    seekTo(3);

    expect(hls.startLoad).toHaveBeenCalledOnce();
    expect(hls.startLoad).toHaveBeenCalledWith(startPosition);
  });

  test("playing before the manifest is parsed loads once it is", () => {
    renderPlayer();
    const hls = latestHls();

    fireEvent.click(screen.getByLabelText("Play"));
    expect(hls.startLoad).not.toHaveBeenCalled();
    act(() => hls.handlers.hlsManifestParsed());

    expect(hls.startLoad).toHaveBeenCalledExactlyOnceWith(frameTime(0));
  });

  test("shows the frame at the playback position", () => {
    renderPlayer();
    fireMedia("seeked");

    video().currentTime = 0.2;
    fireMedia("timeupdate");

    expect(position()).toBe("4 / 5");
    expect(still()).not.toBeInTheDocument();
  });

  test("ignores the playback position until the video has seeked", () => {
    renderPlayer();

    video().currentTime = 0.2;
    fireMedia("timeupdate");

    expect(position()).toBe("1 / 5");
    expect(still()).toBeInTheDocument();
  });

  test("playback speed sets the rate relative to the stream", () => {
    renderPlayer();

    expect(video().playbackRate).toBe(2);
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByRole("option", { name: "24 fps" }));

    expect(video().playbackRate).toBe(1.6);
  });

  test("scrubbing seeks and pauses", () => {
    renderPlayer();
    fireEvent.click(screen.getByLabelText("Play"));

    fireEvent.change(screen.getByRole("slider"), { target: { value: 3 } });

    expect(position()).toBe("4 / 5");
    expect(screen.getByLabelText("Play")).toBeInTheDocument();
  });

  describe("dragging the slider", () => {
    const setBuffered = (ranges: [number, number][]) => {
      Object.defineProperty(video(), "buffered", {
        configurable: true,
        value: {
          length: ranges.length,
          start: (i: number) => ranges[i][0],
          end: (i: number) => ranges[i][1],
        },
      });
    };

    const startDrag = () => {
      const slider = document.querySelector(".MuiSlider-root") as HTMLElement;
      vi.spyOn(slider, "getBoundingClientRect").mockReturnValue(
        new DOMRect(0, 0, 100, 10),
      );
      fireEvent.mouseDown(slider, { button: 0, clientX: 50 });
    };

    beforeEach(() => {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    test("seeks buffered frames immediately", () => {
      renderPlayer();
      act(() => latestHls().handlers.hlsManifestParsed());
      fireEvent.click(screen.getByLabelText("Play"));
      fireMedia("playing");
      setBuffered([[0, 1]]);

      startDrag();
      expect(position()).toBe("3 / 5");
      expect(video().currentTime).toBeCloseTo(frameTime(2));
      expect(screen.getByLabelText("Play")).toBeInTheDocument();

      fireEvent.mouseMove(document, { buttons: 1, clientX: 75 });
      expect(video().currentTime).toBeCloseTo(frameTime(3));
      fireMedia("seeked");
      expect(position()).toBe("4 / 5");
      expect(still()).not.toBeInTheDocument();
    });

    test("does not fetch a still per frame", () => {
      renderPlayer();
      const hls = latestHls();
      act(() => hls.handlers.hlsManifestParsed());

      startDrag();
      fireEvent.mouseMove(document, { buttons: 1, clientX: 75 });

      expect(position()).toBe("4 / 5");
      expect(still().src).toContain("/files/frame0.jpg");
      expect(hls.startLoad).not.toHaveBeenCalled();
    });

    test("seeks unbuffered frames once the thumb rests", () => {
      renderPlayer();
      const hls = latestHls();
      act(() => hls.handlers.hlsManifestParsed());

      startDrag();
      act(() => vi.advanceTimersByTime(100));
      fireEvent.mouseMove(document, { buttons: 1, clientX: 75 });
      act(() => vi.advanceTimersByTime(100));
      expect(hls.startLoad).not.toHaveBeenCalled();

      act(() => vi.advanceTimersByTime(200));
      expect(hls.startLoad).toHaveBeenCalledExactlyOnceWith(frameTime(3));
      expect(video().currentTime).toBeCloseTo(frameTime(3));

      fireMedia("seeked");
      expect(still()).not.toBeInTheDocument();
      expect(position()).toBe("4 / 5");
    });

    test("seeks unbuffered frames on release", () => {
      renderPlayer();
      const hls = latestHls();
      act(() => hls.handlers.hlsManifestParsed());

      startDrag();
      fireEvent.mouseMove(document, { buttons: 1, clientX: 75 });
      fireEvent.mouseUp(document, { clientX: 75 });

      expect(hls.startLoad).toHaveBeenCalledExactlyOnceWith(frameTime(3));
      expect(video().currentTime).toBeCloseTo(frameTime(3));
      act(() => vi.runAllTimers());
      expect(hls.startLoad).toHaveBeenCalledOnce();
    });

    test("keeps the thumb in place while the video lags behind", () => {
      renderPlayer();
      act(() => latestHls().handlers.hlsManifestParsed());
      fireEvent.click(screen.getByLabelText("Play"));
      fireMedia("playing");

      startDrag();
      fireMedia("timeupdate");

      expect(position()).toBe("3 / 5");
    });
  });

  test("shows a spinner while the video is waiting for data", () => {
    renderPlayer();
    expect(screen.queryByLabelText("Buffering")).not.toBeInTheDocument();

    fireMedia("waiting");
    expect(screen.getByLabelText("Buffering")).toBeInTheDocument();

    fireMedia("playing");
    expect(screen.queryByLabelText("Buffering")).not.toBeInTheDocument();
  });

  test("picks up new frames of a live range once paused", async () => {
    const { rerender } = renderPlayer();
    fireEvent.click(screen.getByLabelText("Play"));
    const hls = latestHls();

    rerender(player(makeFrames([1000, 1005, 1010, 1015, 1020, 1025])));
    expect(hlsInstances).toHaveLength(1);
    expect(position()).toBe("1 / 5");

    fireEvent.click(screen.getByLabelText("Pause"));

    expect(hls.destroy).toHaveBeenCalled();
    expect(latestHls().loadSource).toHaveBeenCalledWith("blob:2");
    expect(position()).toBe("1 / 6");
  });

  test("keeps the position when a live range refreshes while paused", () => {
    const { rerender } = renderPlayer();
    act(() => latestHls().handlers.hlsManifestParsed());
    seekTo(2);
    fireMedia("seeked");
    expect(position()).toBe("3 / 5");

    // Thinned to a coarser step, the old frame 3 at 1010 is now frame 2
    rerender(player(makeFrames([1000, 1010, 1020, 1030])));
    const hls = latestHls();
    expect(hlsInstances).toHaveLength(2);
    expect(position()).toBe("2 / 4");

    // Attaching a new source rewinds the video
    video().currentTime = 0;
    fireMedia("emptied");
    fireMedia("timeupdate");
    act(() => hls.handlers.hlsManifestParsed());
    expect(position()).toBe("2 / 4");
    expect(still().src).toContain("/files/frame1.jpg");
    expect(hls.startLoad).not.toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText("Play"));
    expect(position()).toBe("2 / 4");
    expect(hls.startLoad).toHaveBeenCalledExactlyOnceWith(frameTime(1));
  });

  test("shows fatal playback errors until a fragment loads", () => {
    renderPlayer();

    act(() =>
      latestHls().handlers.hlsError(null, {
        fatal: true,
        type: "networkError",
        error: new Error("Segment failed"),
      }),
    );
    expect(screen.getByText("Segment failed")).toBeInTheDocument();

    act(() => latestHls().handlers.hlsFragLoaded());
    expect(screen.queryByText("Segment failed")).not.toBeInTheDocument();
  });

  test.each([
    {
      type: "networkError",
      restart: "play",
      method: "startLoad",
      calls: [[frameTime(0)], [frameTime(0)]],
    },
    {
      type: "networkError",
      restart: "seek",
      method: "startLoad",
      calls: [[frameTime(0)], [frameTime(1)]],
    },
    {
      type: "mediaError",
      restart: "play",
      method: "recoverMediaError",
      calls: [[]],
    },
  ])(
    "$restart after a fatal $type clears the error and restarts loading",
    ({ type, restart, method, calls }) => {
      renderPlayer();
      const hls = latestHls();
      act(() => hls.handlers.hlsManifestParsed());
      fireEvent.click(screen.getByLabelText("Play"));
      act(() =>
        hls.handlers.hlsError(null, {
          fatal: true,
          type,
          error: new Error("Segment failed"),
        }),
      );
      fireEvent.click(screen.getByLabelText("Pause"));

      if (restart === "play") {
        fireEvent.click(screen.getByLabelText("Play"));
      } else {
        seekTo(1);
      }

      expect(screen.queryByText("Segment failed")).not.toBeInTheDocument();
      expect(hls[method].mock.calls).toEqual(calls);
    },
  );
});

describe("findGaps", () => {
  test.each([
    {
      name: "no gaps",
      timestamps: [0, 5, 10, 15],
      step: null,
      expected: [],
    },
    {
      name: "a gap longer than a minute",
      timestamps: [0, 5, 10, 200, 205],
      step: null,
      expected: [3],
    },
    {
      name: "gaps relative to the downsampling step",
      timestamps: [0, 100, 200, 800, 900],
      step: 100,
      expected: [3],
    },
  ])("finds $name", ({ timestamps, step, expected }) => {
    expect(findGaps(makeFrames(timestamps), step)).toEqual(expected);
  });

  test("keeps only the 100 longest gaps in frame order", () => {
    // The gap before frame i is 99 + i seconds
    const timestamps = [0];
    for (let i = 1; i <= 102; i++) {
      timestamps.push(timestamps[i - 1] + 99 + i);
    }

    const gaps = findGaps(makeFrames(timestamps), 10);

    expect(gaps).toEqual(Array.from({ length: 100 }, (_, i) => i + 3));
  });
});
