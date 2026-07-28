import type Hls from "hls.js";

import {
  HLS_CONFIG_BY_PLAYBACK_MODE,
  HlsPlaybackMode,
  seekHlsByOffset,
  seekHlsToLiveEdge,
  seekMediaAndStartLoad,
  startLoadAtBeginning,
  startLoadAtCurrentTime,
} from "components/player/hlsplayer/utils";

describe("HLS playback mode config", () => {
  it("does not allow hls.js to chase the live edge in synced playback", () => {
    expect(
      HLS_CONFIG_BY_PLAYBACK_MODE[HlsPlaybackMode.Synced]
        .liveMaxLatencyDurationCount,
    ).toBe(Infinity);
  });

  it("keeps live edge chasing enabled for plain live playback", () => {
    expect(
      Number.isFinite(
        HLS_CONFIG_BY_PLAYBACK_MODE[HlsPlaybackMode.Live]
          .liveMaxLatencyDurationCount,
      ),
    ).toBe(true);
  });

  it("uses explicit config for every playback mode", () => {
    expect(Object.keys(HLS_CONFIG_BY_PLAYBACK_MODE)).toEqual(
      Object.values(HlsPlaybackMode),
    );
  });
});

describe("seekMediaAndStartLoad", () => {
  it("seeks the media element and starts loading at the same media time", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 0 } as HTMLMediaElement;
    const hls = { startLoad } as unknown as Hls;

    seekMediaAndStartLoad(hls, media, 42.25);

    expect(media.currentTime).toBe(42.25);
    expect(startLoad).toHaveBeenCalledWith(42.25);
  });

  it("ignores non-finite seek targets", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 0 } as HTMLMediaElement;
    const hls = { startLoad } as unknown as Hls;

    seekMediaAndStartLoad(hls, media, Infinity);

    expect(media.currentTime).toBe(0);
    expect(startLoad).not.toHaveBeenCalled();
  });

  it("bounds negative seek targets at the beginning", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 10, duration: 100 } as HTMLMediaElement;
    const hls = { startLoad } as unknown as Hls;

    seekMediaAndStartLoad(hls, media, -5);

    expect(media.currentTime).toBe(0);
    expect(startLoad).toHaveBeenCalledWith(0);
  });

  it("bounds seek targets to finite media duration", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 10, duration: 100 } as HTMLMediaElement;
    const hls = { startLoad } as unknown as Hls;

    seekMediaAndStartLoad(hls, media, 125);

    expect(media.currentTime).toBe(100);
    expect(startLoad).toHaveBeenCalledWith(100);
  });

  it("bounds seek targets to the current seekable range", () => {
    const startLoad = vi.fn();
    const media = {
      currentTime: 55,
      duration: 100,
      seekable: {
        length: 1,
        start: () => 50,
        end: () => 80,
      },
    } as unknown as HTMLMediaElement;
    const hls = { startLoad } as unknown as Hls;

    seekMediaAndStartLoad(hls, media, 40);

    expect(media.currentTime).toBe(50);
    expect(startLoad).toHaveBeenCalledWith(50);
  });
});

describe("startLoadAtCurrentTime", () => {
  it("resumes loading from the current media time when available", () => {
    const startLoad = vi.fn();
    const hls = {
      media: { currentTime: 12.5 },
      startLoad,
    } as unknown as Hls;

    startLoadAtCurrentTime(hls);

    expect(startLoad).toHaveBeenCalledWith(12.5);
  });

  it("falls back to hls.js default start position when current time is unavailable", () => {
    const startLoad = vi.fn();
    const hls = {
      media: null,
      startLoad,
    } as unknown as Hls;

    startLoadAtCurrentTime(hls);

    expect(startLoad).toHaveBeenCalledWith();
  });
});

describe("startLoadAtBeginning", () => {
  it("starts loading from media time zero", () => {
    const startLoad = vi.fn();
    const hls = { startLoad } as unknown as Hls;

    startLoadAtBeginning(hls);

    expect(startLoad).toHaveBeenCalledWith(0);
  });
});

describe("seekHlsByOffset", () => {
  it("seeks relative to the hls media current time", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 30, duration: 100 } as HTMLMediaElement;
    const hls = { media, startLoad } as unknown as Hls;

    seekHlsByOffset(hls, 10);

    expect(media.currentTime).toBe(40);
    expect(startLoad).toHaveBeenCalledWith(40);
  });

  it("does nothing without attached media", () => {
    const startLoad = vi.fn();
    const hls = { media: null, startLoad } as unknown as Hls;

    seekHlsByOffset(hls, 10);

    expect(startLoad).not.toHaveBeenCalled();
  });
});

describe("seekHlsToLiveEdge", () => {
  it("seeks to the configured delay behind media duration", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 0, duration: 100 } as HTMLMediaElement;
    const hls = { media, startLoad } as unknown as Hls;

    seekHlsToLiveEdge(hls, 15);

    expect(media.currentTime).toBe(85);
    expect(startLoad).toHaveBeenCalledWith(85);
  });

  it("does nothing when media duration is not finite", () => {
    const startLoad = vi.fn();
    const media = { currentTime: 0, duration: Infinity } as HTMLMediaElement;
    const hls = { media, startLoad } as unknown as Hls;

    seekHlsToLiveEdge(hls, 15);

    expect(media.currentTime).toBe(0);
    expect(startLoad).not.toHaveBeenCalled();
  });
});
