import { act } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HlsPlayer } from "components/player/hlsplayer/HlsPlayer";
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

    // Stores the once-handlers so tests can invoke them manually.
    handlers: Record<string, (...callbackArgs: any[]) => void> = {};

    on = vi.fn();

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

const latestHls = () => hlsInstances[hlsInstances.length - 1];

beforeEach(() => {
  hlsInstances.length = 0;
});

describe("HlsPlayer handler registration", () => {
  it("registers MANIFEST_PARSED and LEVEL_LOADED before loadSource", () => {
    renderWithContext(<HlsPlayer camera={mockCamera} />);

    const hls = latestHls();
    expect(hls).toBeDefined();
    expect(hls.once).toHaveBeenCalledWith(
      "hlsManifestParsed",
      expect.any(Function),
    );
    expect(hls.once).toHaveBeenCalledWith(
      "hlsLevelLoaded",
      expect.any(Function),
    );

    // Both once-handlers must be registered before the source starts loading,
    // otherwise an early MANIFEST_PARSED would never trigger startLoad.
    const lastOnceOrder = Math.max(...hls.once.mock.invocationCallOrder);
    const loadSourceOrder = hls.loadSource.mock.invocationCallOrder[0];
    expect(lastOnceOrder).toBeLessThan(loadSourceOrder);
  });

  it("starts loading when MANIFEST_PARSED fires after registration", () => {
    renderWithContext(<HlsPlayer camera={mockCamera} />);

    const hls = latestHls();
    // Simulate the manifest being parsed and assert the load is kicked off.
    act(() => {
      hls.handlers.hlsManifestParsed();
    });

    expect(hls.startLoad).toHaveBeenCalledWith(0);
  });
});
