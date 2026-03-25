import Hls from "hls.js";
import React from "react";

import { getToken } from "lib/tokens";
import * as types from "lib/types";

// Default HLS configuration options shared between live and VOD players.
export const DEFAULT_HLS_CONFIG = {
  autoStartLoad: false,
  maxBufferLength: 30, // 30 seconds of forward buffer
  backBufferLength: 15, // 15 seconds of back buffer
  liveSyncDurationCount: 1, // Start from the second last segment
  maxStarvationDelay: 99999999, // Prevents auto seeking back on starvation
  liveDurationInfinity: false, // Has to be false to seek backwards
};

// Creates an HLS.js instance with standard configuration and authentication setup.
export function createHlsInstance(
  auth: types.AuthEnabledResponse,
  hlsClientIdRef: React.MutableRefObject<string>,
): Hls {
  return new Hls({
    ...DEFAULT_HLS_CONFIG,
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
          hlsRef.current?.startLoad();
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
