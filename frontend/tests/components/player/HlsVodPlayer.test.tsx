import { act, fireEvent, screen } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HlsVodPlayer } from "components/player/hlsplayer/HlsVodPlayer";
import * as types from "lib/types";

// Collects every mocked Hls instance created during a test so assertions can
// reach into the instance the component is driving.
const { hlsInstances } = vi.hoisted(() => ({
  hlsInstances: [] as any[],
}));

vi.mock("hls.js", () => {
  const Events = {
    MEDIA_ATTACHED: "hlsMediaAttached",
    MANIFEST_PARSED: "hlsManifestParsed",
    LEVEL_LOADED: "hlsLevelLoaded",
    FRAG_LOADED: "hlsFragLoaded",
    ERROR: "hlsError",
  };
  const ErrorDetails = {
    FRAG_GAP: "fragGap",
    BUFFER_STALLED_ERROR: "bufferStalledError",
    BUFFER_SEEK_OVER_HOLE: "bufferSeekOverHole",
    MANIFEST_LOAD_ERROR: "manifestLoadError",
  };
  const ErrorTypes = {
    NETWORK_ERROR: "networkError",
    MEDIA_ERROR: "mediaError",
  };

  class MockHls {
    media: HTMLMediaElement | null = null;

    levels: any[] = [];

    currentLevel = 0;

    // Stores the handlers so tests can invoke them manually.
    handlers: Record<string, (...callbackArgs: any[]) => void> = {};

    on = vi.fn((event: string, callback: (...callbackArgs: any[]) => void) => {
      this.handlers[event] = callback;
    });

    once = vi.fn(
      (event: string, callback: (...callbackArgs: any[]) => void) => {
        this.handlers[event] = callback;
      },
    );

    attachMedia = vi.fn((media: HTMLMediaElement) => {
      this.media = media;
    });

    loadSource = vi.fn();

    startLoad = vi.fn();

    stopLoad = vi.fn();

    destroy = vi.fn();

    recoverMediaError = vi.fn();

    constructor() {
      hlsInstances.push(this);
    }

    static isSupported = () => true;

    static Events = Events;

    static ErrorDetails = ErrorDetails;

    static ErrorTypes = ErrorTypes;
  }

  return { default: MockHls };
});

const mockCamera: types.Camera = {
  width: 1920,
  height: 1080,
  identifier: "camera1",
  name: "Camera 1",
  access_token: "token",
  mainstream: {
    width: 1920,
    height: 1080,
  },
  still_image: {
    refresh_interval: 0,
    available: true,
    width: 1920,
    height: 1080,
  },
  failed: false,
  is_on: true,
  connected: true,
  live_stream_available: true,
  is_recording: false,
};

const mockRecording: types.Recording = {
  id: 1,
  camera_identifier: "camera1",
  start_time: "2026-01-01T00:00:00.000000+00:00",
  start_timestamp: 1767225600,
  end_time: "2026-01-01T00:01:00.000000+00:00",
  end_timestamp: 1767225660,
  trigger_type: "object",
  trigger_id: null,
  thumbnail_path: "/thumbnail.jpg",
  hls_url: "/api/v1/hls/camera1/1/index.m3u8",
};

const latestHls = () => hlsInstances[hlsInstances.length - 1];

const renderAndPlay = () => {
  renderWithContext(
    <HlsVodPlayer camera={mockCamera} recording={mockRecording} />,
  );
  const video = screen
    .getByTestId("hls-vod-player")
    .querySelector("video") as HTMLVideoElement;
  act(() => {
    fireEvent.play(video);
  });
  return latestHls();
};

beforeEach(() => {
  hlsInstances.length = 0;
});

describe("HlsVodPlayer", () => {
  it("loads the recording source when play is pressed", () => {
    const hls = renderAndPlay();

    expect(hls.loadSource).toHaveBeenCalledWith(mockRecording.hls_url);
  });

  it("registers the MANIFEST_PARSED handler before loadSource", () => {
    const hls = renderAndPlay();

    // The shared config uses autoStartLoad: false, so the handler that calls
    // startLoad must be registered before the manifest starts loading.
    const registrationOrder = hls.on.mock.invocationCallOrder.filter(
      (_order: number, index: number) =>
        hls.on.mock.calls[index][0] === "hlsManifestParsed",
    );
    const loadSourceOrder = hls.loadSource.mock.invocationCallOrder[0];
    expect(registrationOrder).toHaveLength(1);
    expect(registrationOrder[0]).toBeLessThan(loadSourceOrder);
  });

  it("starts loading fragments when MANIFEST_PARSED fires", () => {
    const hls = renderAndPlay();

    // Without this the playlist is fetched but no segments are ever requested.
    act(() => {
      hls.handlers.hlsManifestParsed();
    });

    expect(hls.startLoad).toHaveBeenCalledWith(0);
  });
});
