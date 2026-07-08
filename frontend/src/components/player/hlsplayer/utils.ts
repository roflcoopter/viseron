import Hls, { type HlsConfig } from "hls.js";
import React from "react";

import { getToken } from "lib/tokens";
import * as types from "lib/types";

export enum HlsPlaybackMode {
  Synced = "synced",
  Vod = "vod",
  Live = "live",
}

const HLS_LIVE_SYNC_SEGMENT_COUNT = 3;
const HLS_LIVE_MAX_LATENCY_SEGMENT_COUNT = 6;
const HLS_DISABLED_LIVE_MAX_LATENCY = Infinity;

const BASE_HLS_CONFIG = {
  autoStartLoad: false,
  maxBufferLength: 30, // 30 seconds of forward buffer
  backBufferLength: 15, // 15 seconds of back buffer
  liveDurationInfinity: false, // Has to be false to seek backwards
} satisfies Partial<HlsConfig>;

export const HLS_CONFIG_BY_PLAYBACK_MODE = {
  // Synced playback is app-controlled wall-clock playback used by the Events grid.
  // hls.js must not independently seek to the live edge in this mode.
  [HlsPlaybackMode.Synced]: {
    ...BASE_HLS_CONFIG,
    liveSyncDurationCount: HLS_LIVE_SYNC_SEGMENT_COUNT,
    liveMaxLatencyDurationCount: HLS_DISABLED_LIVE_MAX_LATENCY,
  },
  [HlsPlaybackMode.Vod]: {
    ...BASE_HLS_CONFIG,
    liveSyncDurationCount: HLS_LIVE_SYNC_SEGMENT_COUNT,
    liveMaxLatencyDurationCount: HLS_DISABLED_LIVE_MAX_LATENCY,
  },
  [HlsPlaybackMode.Live]: {
    ...BASE_HLS_CONFIG,
    liveSyncDurationCount: HLS_LIVE_SYNC_SEGMENT_COUNT,
    liveMaxLatencyDurationCount: HLS_LIVE_MAX_LATENCY_SEGMENT_COUNT,
  },
} satisfies Record<HlsPlaybackMode, Partial<HlsConfig>>;

// Creates an HLS.js instance with standard configuration and authentication setup.
export function createHlsInstance(
  auth: types.AuthEnabledResponse,
  hlsClientIdRef: React.MutableRefObject<string>,
  playbackMode: HlsPlaybackMode,
): Hls {
  return new Hls({
    ...HLS_CONFIG_BY_PLAYBACK_MODE[playbackMode],
    async xhrSetup(xhr, _url) {
      xhr.withCredentials = true;
      if (auth.enabled) {
        const token = await getToken();
        if (token) {
          xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }
      }
      xhr.setRequestHeader("Hls-Client-Id", hlsClientIdRef.current);
    },
  });
}

export function startLoadAtCurrentTime(hls: Hls): void {
  const currentTime = hls.media?.currentTime;
  if (Number.isFinite(currentTime)) {
    hls.startLoad(currentTime);
    return;
  }
  hls.startLoad();
}

export function seekMediaAndStartLoad(
  hls: Hls,
  media: HTMLMediaElement,
  mediaTime: number,
): void {
  if (!Number.isFinite(mediaTime)) {
    return;
  }
  media.currentTime = mediaTime;
  hls.startLoad(mediaTime);
}

// Ignorable HLS error details that don't require user notification.
// - FRAG_GAP: Natural since recordings are not necessarily continuous
// - BUFFER_STALLED_ERROR: Happens when too close to live edge, automatically stabilizes
// - BUFFER_SEEK_OVER_HOLE: Happens when seeking over a gap in the recording
const IGNORABLE_ERROR_DETAILS = new Set([
  Hls.ErrorDetails.FRAG_GAP,
  Hls.ErrorDetails.BUFFER_STALLED_ERROR,
  Hls.ErrorDetails.BUFFER_SEEK_OVER_HOLE,
]);

export interface HlsErrorHandlerOptions {
  hlsRef: React.MutableRefObject<Hls | null>;
  setHlsRefsError: (
    hlsRef: React.MutableRefObject<Hls | null>,
    error: string | null,
  ) => void;
  delayedInitializationTimeoutRef: React.MutableRefObject<
    NodeJS.Timeout | undefined
  >;
  delayedRecoveryTimeoutRef: React.MutableRefObject<NodeJS.Timeout | undefined>;
  onReinitialize: () => void;
}

// Sets up standardized error handling for an HLS.js instance.
// Handles both recoverable and fatal errors with appropriate retry strategies.
export function setupHlsErrorHandling(
  hls: Hls,
  options: HlsErrorHandlerOptions,
): void {
  const {
    hlsRef,
    setHlsRefsError,
    delayedInitializationTimeoutRef,
    delayedRecoveryTimeoutRef,
    onReinitialize,
  } = options;

  // Reset error state when a fragment is loaded successfully
  hls.on(Hls.Events.FRAG_LOADED, () => {
    setHlsRefsError(hlsRef, null);
  });

  // Delayed initialization retry for fatal errors
  const delayedInitialization = () => {
    if (delayedInitializationTimeoutRef.current) {
      return;
    }

    delayedInitializationTimeoutRef.current = setTimeout(() => {
      onReinitialize();
      delayedInitializationTimeoutRef.current = undefined;
    }, 5000);
  };

  // Delayed recovery for media errors
  const delayedRecovery = () => {
    if (delayedRecoveryTimeoutRef.current) {
      return;
    }

    delayedRecoveryTimeoutRef.current = setTimeout(() => {
      hlsRef.current?.recoverMediaError();
      delayedRecoveryTimeoutRef.current = undefined;
    }, 5000);
  };

  // Main error handler
  hls.on(Hls.Events.ERROR, (_event, data) => {
    // Check if this is an ignorable error
    if (!IGNORABLE_ERROR_DETAILS.has(data.details)) {
      console.log("HLSJS Error:", data);
      setHlsRefsError(hlsRef, data.error.message.slice(0, 200));
    }

    if (data.fatal) {
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR:
          if (data.details === Hls.ErrorDetails.MANIFEST_LOAD_ERROR) {
            delayedInitialization();
          }
          if (hlsRef.current) {
            startLoadAtCurrentTime(hlsRef.current);
          }
          break;

        case Hls.ErrorTypes.MEDIA_ERROR:
          delayedRecovery();
          break;

        default:
          delayedInitialization();
          break;
      }
    }
  });
}

// Cleans up an HLS instance and associated timeouts.
export function cleanupHlsInstance(
  hlsRef: React.MutableRefObject<Hls | null>,
  removeHlsRef: (ref: React.MutableRefObject<Hls | null>) => void,
  delayedInitializationTimeoutRef: React.MutableRefObject<
    NodeJS.Timeout | undefined
  >,
  delayedRecoveryTimeoutRef?: React.MutableRefObject<
    NodeJS.Timeout | undefined
  >,
): void {
  if (hlsRef.current) {
    hlsRef.current.destroy();
    removeHlsRef(hlsRef);
    hlsRef.current = null;
  }
  if (delayedInitializationTimeoutRef.current) {
    clearTimeout(delayedInitializationTimeoutRef.current);
  }
  if (delayedRecoveryTimeoutRef?.current) {
    clearTimeout(delayedRecoveryTimeoutRef.current);
  }
}
