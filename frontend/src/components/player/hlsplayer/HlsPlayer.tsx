import { VideoOff } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import { useTheme } from "@mui/material/styles";
import Hls, { LevelLoadedData } from "hls.js";
import React, {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { v4 as uuidv4 } from "uuid";
import { useShallow } from "zustand/react/shallow";

import {
  findFragmentByTimestamp,
  getSeekTarget,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";
import { useAuthContext } from "context/AuthContext";
import { ViseronContext } from "context/ViseronContext";
import { useFirstRender } from "hooks/UseFirstRender";
import { BASE_PATH } from "lib/api/client";
import { BLANK_IMAGE } from "lib/helpers";
import {
  getDateStringFromDayjs,
  getDayjsFromUnixTimestamp,
} from "lib/helpers/dates";
import { getToken } from "lib/tokens";
import * as types from "lib/types";

const loadSource = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  playingDate: number,
  camera: types.Camera | types.FailedCamera,
) => {
  if (!hlsRef.current) {
    return;
  }
  // Subtract 1 hour from playingDate.
  // This is to allow clicking on the timeline and then seek backwards a bit to get some
  // context before the requested timestamp
  const startTimestamp = playingDate - 3600;

  const source =
    `${BASE_PATH}/api/v1/hls/${camera.identifier}/index.m3u8` +
    `?start_timestamp=${startTimestamp}` +
    `&date=${getDateStringFromDayjs(getDayjsFromUnixTimestamp(playingDate))}`;
  hlsClientIdRef.current = uuidv4();
  hlsRef.current.loadSource(source);
};

const onLevelLoaded = (
  data: LevelLoadedData,
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  playingDateRef: React.MutableRefObject<number>,
) => {
  const playingDateMillis = playingDateRef.current * 1000;
  const fragments = data.details.fragments;
  if (!hlsRef.current || !videoRef.current) {
    return;
  }

  if (fragments.length > 0) {
    initialProgramDateTime.current = fragments[0].programDateTime!;
  }

  // Seek to the requested timestamp
  const fragment = findFragmentByTimestamp(fragments, playingDateMillis);
  if (fragment) {
    const seekTarget = getSeekTarget(fragment, playingDateMillis);
    videoRef.current.currentTime = seekTarget;
    videoRef.current.play().catch(() => {
      // Ignore play errors
    });
  } else {
    videoRef.current.pause();
  }
};

const onManifestParsed = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
) => {
  if (!hlsRef.current || !videoRef.current) {
    return;
  }

  videoRef.current.muted = true;
  hlsRef.current.startLoad(0);
};

const onMediaAttached = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  playingDateRef: React.MutableRefObject<number>,
) => {
  hlsRef.current!.once(Hls.Events.MANIFEST_PARSED, () => {
    onManifestParsed(hlsRef, videoRef);
  });

  hlsRef.current!.once(
    Hls.Events.LEVEL_LOADED,
    (event: any, data: LevelLoadedData) => {
      onLevelLoaded(
        data,
        hlsRef,
        videoRef,
        initialProgramDateTime,
        playingDateRef,
      );
    },
  );
};

const initializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  auth: types.AuthEnabledResponse,
  camera: types.Camera | types.FailedCamera,
  playingDateRef: React.MutableRefObject<number>,
  setHlsRefsError: (
    hlsRef: React.MutableRefObject<Hls | null>,
    error: string | null,
  ) => void,
  delayedInitializationTimeoutRef: React.MutableRefObject<
    NodeJS.Timeout | undefined
  >,
  delayedRecoveryTimeoutRef: React.MutableRefObject<NodeJS.Timeout | undefined>,
) => {
  // Destroy the previous hls instance if it exists
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }

  // Create a new hls instance
  hlsRef.current = new Hls({
    autoStartLoad: false,
    maxBufferLength: 30, // 30 seconds of forward buffer
    backBufferLength: 15, // 15 seconds of back buffer
    liveSyncDurationCount: 1, // Start from the second last segment
    maxStarvationDelay: 99999999, // Prevents auto seeking back on starvation
    liveDurationInfinity: false, // Has to be false to seek backwards
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

  if (videoRef.current) {
    hlsRef.current.attachMedia(videoRef.current);
  }

  // Load the source and start the hls instance
  loadSource(hlsRef, hlsClientIdRef, playingDateRef.current, camera);

  // Handle MEDIA_ATTACHED event
  hlsRef.current.on(Hls.Events.MEDIA_ATTACHED, () => {
    onMediaAttached(hlsRef, videoRef, initialProgramDateTime, playingDateRef);
  });

  // Reset error state when a fragment is loaded
  hlsRef.current.on(Hls.Events.FRAG_LOADED, () => {
    setHlsRefsError(hlsRef, null);
  });

  // Make sure initialization is retried on error after a delay
  const delayedInitialization = () => {
    if (delayedInitializationTimeoutRef.current) {
      return;
    }

    delayedInitializationTimeoutRef.current = setTimeout(() => {
      initializePlayer(
        hlsRef,
        hlsClientIdRef,
        videoRef,
        initialProgramDateTime,
        auth,
        camera,
        playingDateRef,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
      delayedInitializationTimeoutRef.current = undefined;
    }, 5000);
  };

  const delayedRecovery = () => {
    if (delayedRecoveryTimeoutRef.current) {
      return;
    }

    delayedRecoveryTimeoutRef.current = setTimeout(() => {
      hlsRef.current!.recoverMediaError();
    }, 5000);
  };

  // Handle errors
  hlsRef.current.on(Hls.Events.ERROR, (_event, data) => {
    // Ignore some HLS errors:
    // - FRAG_GAP: Natural since recordings are not necessarily continuous
    // - BUFFER_STALLED_ERROR: Happens when too close to live edge, automatically stabilizezes itself
    switch (data.details) {
      case Hls.ErrorDetails.FRAG_GAP:
      case Hls.ErrorDetails.BUFFER_STALLED_ERROR:
        break;
      default:
        setHlsRefsError(hlsRef, data.error.message.slice(0, 200));
        break;
    }

    if (data.fatal) {
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR:
          if (data.details === Hls.ErrorDetails.MANIFEST_LOAD_ERROR) {
            delayedInitialization();
          }
          hlsRef.current!.startLoad();
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
};

const useInitializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  camera: types.Camera | types.FailedCamera,
) => {
  const { auth } = useAuthContext();
  const { connected } = useContext(ViseronContext);
  const { addHlsRef, removeHlsRef, setHlsRefsError } = useHlsStore(
    useShallow((state) => ({
      addHlsRef: state.addHlsRef,
      removeHlsRef: state.removeHlsRef,
      setHlsRefsError: state.setHlsRefsError,
    })),
  );
  const { playingDateRef } = useReferencePlayerStore(
    useShallow((state) => ({
      playingDateRef: state.playingDateRef,
    })),
  );
  const delayedInitializationTimeoutRef = useRef<NodeJS.Timeout>(undefined);
  const delayedRecoveryTimeoutRef = useRef<NodeJS.Timeout>(undefined);

  const reInitPlayer = useCallback(() => {
    if (Hls.isSupported()) {
      initializePlayer(
        hlsRef,
        hlsClientIdRef,
        videoRef,
        initialProgramDateTime,
        auth,
        camera,
        playingDateRef,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    }
  }, [
    auth,
    camera,
    hlsClientIdRef,
    hlsRef,
    initialProgramDateTime,
    playingDateRef,
    setHlsRefsError,
    videoRef,
    delayedInitializationTimeoutRef,
    delayedRecoveryTimeoutRef,
  ]);

  useEffect(() => {
    if (Hls.isSupported()) {
      addHlsRef(hlsRef);
      initializePlayer(
        hlsRef,
        hlsClientIdRef,
        videoRef,
        initialProgramDateTime,
        auth,
        camera,
        playingDateRef,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    }
    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        removeHlsRef(hlsRef);
        hlsRef.current = null;
      }
      if (delayedInitializationTimeoutRef.current) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        clearTimeout(delayedInitializationTimeoutRef.current);
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Pause the player when the connection is lost
  useEffect(() => {
    if (!connected && hlsRef.current) {
      hlsRef.current.stopLoad();
    } else if (connected && hlsRef.current) {
      hlsRef.current.startLoad();
    }
  }, [connected, hlsRef]);

  return {
    reInitPlayer,
  };
};

// Seek to the requestedTimestamp if it is within the seekable range
const useSeekToTimestamp = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  camera: types.Camera | types.FailedCamera,
  reInitPlayer: () => void,
) => {
  // Avoid running on first render to not call loadSource twice
  const firstRender = useFirstRender();
  const { requestedTimestamp } = useReferencePlayerStore(
    useShallow((state) => ({
      requestedTimestamp: state.requestedTimestamp,
    })),
  );

  useEffect(() => {
    if (
      !hlsRef.current ||
      !videoRef.current ||
      !hlsRef.current.media ||
      firstRender
    ) {
      return;
    }

    const requestedTimestampMillis = requestedTimestamp * 1000;
    // Set seek target timestamp
    const currentLevel = hlsRef.current.levels[hlsRef.current.currentLevel];
    if (!currentLevel || !currentLevel.details) {
      return;
    }

    const fragments = currentLevel.details.fragments;
    if (!fragments || fragments.length === 0) {
      return;
    }
    const fragment = findFragmentByTimestamp(
      fragments,
      requestedTimestampMillis,
    );

    if (fragment) {
      const seekTarget = getSeekTarget(fragment, requestedTimestampMillis);
      videoRef.current.currentTime = seekTarget;
      videoRef.current.play().catch(() => {
        // Ignore play errors
      });
    } else {
      // If the fragment is not found, reinitialize the player to load the correct source
      reInitPlayer();
    }
  }, [
    camera,
    firstRender,
    hlsClientIdRef,
    hlsRef,
    initialProgramDateTime,
    reInitPlayer,
    requestedTimestamp,
    videoRef,
  ]);
};

interface HlsPlayerProps {
  camera: types.Camera | types.FailedCamera;
}

export function HlsPlayer({ camera }: HlsPlayerProps) {
  const theme = useTheme();
  const hlsRef = useRef<Hls | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsClientIdRef = useRef<string>(uuidv4());
  const initialProgramDateTime = useRef<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const { hlsRefError } = useHlsStore(
    useShallow((state) => ({
      hlsRefError: state.hlsRefsError.get(hlsRef),
    })),
  );

  const { reInitPlayer } = useInitializePlayer(
    hlsRef,
    hlsClientIdRef,
    videoRef,
    initialProgramDateTime,
    camera,
  );
  useSeekToTimestamp(
    hlsRef,
    hlsClientIdRef,
    videoRef,
    initialProgramDateTime,
    camera,
    reInitPlayer,
  );

  // Handle loading state
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return () => {};

    const handleLoadStart = () => setIsLoading(true);
    const handleCanPlay = () => setIsLoading(false);
    const handleLoadedData = () => setIsLoading(false);
    const handleError = () => setIsLoading(false);

    video.addEventListener("loadstart", handleLoadStart);
    video.addEventListener("canplay", handleCanPlay);
    video.addEventListener("loadeddata", handleLoadedData);
    video.addEventListener("error", handleError);

    return () => {
      video.removeEventListener("loadstart", handleLoadStart);
      video.removeEventListener("canplay", handleCanPlay);
      video.removeEventListener("loadeddata", handleLoadedData);
      video.removeEventListener("error", handleError);
    };
  }, []);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        display: "flex",
      }}
    >
      {/* Always render video-element */}
      <video
        ref={videoRef}
        poster={BLANK_IMAGE}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          backgroundColor: theme.palette.background.default,
        }}
        controls={false}
        playsInline
        muted
      />

      {/* Show loading indicator and when camera is connected */}
      {isLoading && (
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(0, 0, 0, 0.3)",
            zIndex: 1,
            pointerEvents: "none",
          }}
        >
          <CircularProgress enableTrackSlot />
        </Box>
      )}

      {/* Show error overlay */}
      {!!(hlsRef.current && hlsRefError) && (
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: "100%",
            height: "100%",
            backgroundColor: (t) =>
              t.palette.mode === "dark"
                ? "rgba(0, 0, 0, 0.8)"
                : "rgba(235, 235, 235, 0.8)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: 200,
            gap: 2,
            zIndex: 2,
          }}
        >
          <VideoOff
            size={48}
            style={{
              color: theme.palette.text.secondary,
              opacity: 0.5,
            }}
          />
          <Box
            sx={{
              color: theme.palette.text.secondary,
              textAlign: "center",
              fontSize: "0.875rem",
              opacity: 0.7,
              maxWidth: "80%",
              wordBreak: "break-word",
            }}
          >
            {hlsRefError}
          </Box>
        </Box>
      )}
    </div>
  );
}
