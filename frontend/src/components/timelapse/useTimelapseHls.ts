import Hls, { HlsConfig } from "hls.js";
import { RefObject, useCallback, useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";

import { createHlsInstance } from "components/player/hlsplayer/utils";
import { useAuthContext } from "context/AuthContext";

// Covers the server's 60 s encode timeout plus time queued behind other encodes
const TIMELAPSE_HLS_CONFIG: Partial<HlsConfig> = {
  fragLoadPolicy: {
    default: {
      maxTimeToFirstByteMs: 120000,
      maxLoadTimeMs: 180000,
      timeoutRetry: { maxNumRetry: 1, retryDelayMs: 0, maxRetryDelayMs: 0 },
      errorRetry: { maxNumRetry: 2, retryDelayMs: 1000, maxRetryDelayMs: 8000 },
    },
  },
};

/**
 * Attach a playlist to the video without fetching segments until load() is
 * called, since every segment the server has not cached costs an encode.
 */
export function useTimelapseHls(
  videoRef: RefObject<HTMLVideoElement | null>,
  playlist: string,
  onMediaReset: () => void,
) {
  const { auth } = useAuthContext();
  const hlsClientIdRef = useRef(uuidv4());
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef<(position: number) => void>(() => {});
  const onMediaResetRef = useRef(onMediaReset);
  onMediaResetRef.current = onMediaReset;

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !Hls.isSupported()) {
      return () => {};
    }
    const url = URL.createObjectURL(
      new Blob([playlist], { type: "application/vnd.apple.mpegurl" }),
    );
    const hls = createHlsInstance(auth, hlsClientIdRef, TIMELAPSE_HLS_CONFIG);
    let parsed = false;
    let started = false;
    let pendingPosition: number | null = null;
    let fatalType: string | null = null;

    const start = (position: number) => {
      // Before the manifest is parsed hls.js would drop the position
      if (!parsed) {
        pendingPosition = position;
        return;
      }
      started = true;
      hls.startLoad(position);
    };

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      parsed = true;
      if (pendingPosition !== null) {
        start(pendingPosition);
      }
    });
    hls.on(Hls.Events.FRAG_LOADED, () => setError(null));
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal) {
        fatalType = data.type;
        setError(data.error.message);
      }
    });

    loadRef.current = (position: number) => {
      const fatal = fatalType;
      if (fatal) {
        fatalType = null;
        setError(null);
      }
      if (fatal === Hls.ErrorTypes.MEDIA_ERROR) {
        onMediaResetRef.current();
        // Reattaches the media and resumes loading from its currentTime
        hls.recoverMediaError();
      } else if (fatal || !started) {
        start(position);
      }
    };

    hls.attachMedia(video);
    hls.loadSource(url);
    return () => {
      loadRef.current = () => {};
      hls.destroy();
      URL.revokeObjectURL(url);
    };
  }, [auth, playlist, videoRef]);

  const load = useCallback((position: number) => loadRef.current(position), []);

  return { error, load };
}
