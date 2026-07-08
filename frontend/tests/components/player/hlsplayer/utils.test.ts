import type Hls from "hls.js";

import {
  HLS_CONFIG_BY_PLAYBACK_MODE,
  HlsPlaybackMode,
  seekMediaAndStartLoad,
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
