import { useTheme } from "@mui/material/styles";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import Hls, { LevelLoadedData } from "hls.js";
import React, { useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

import {
  SCALE,
  findFragmentByTimestamp,
  useHlsStore,
} from "components/events/utils";
import { useAuthContext } from "context/AuthContext";
import { useFirstRender } from "hooks/UseFirstRender";
import { BLANK_IMAGE } from "lib/helpers";
import { getToken } from "lib/tokens";
import * as types from "lib/types";

dayjs.extend(utc);

const loadSource = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  requestedTimestamp: number,
  camera: types.Camera | types.FailedCamera,
) => {
  if (!hlsRef.current) {
    return;
  }
  const source = `/api/v1/hls/${camera.identifier}/index.m3u8?start_timestamp=${requestedTimestamp}&daily=true`;
  hlsClientIdRef.current = uuidv4();
  hlsRef.current.loadSource(source);
};

const onLevelLoaded = (
  data: LevelLoadedData,
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestampRef: React.MutableRefObject<number>,
) => {
  const requestedTimestampMillis = requestedTimestampRef.current * 1000;
  const fragments = data.details.fragments;
  if (!hlsRef.current || !videoRef.current) {
    return;
  }

  if (fragments.length > 0) {
    initialProgramDateTime.current = fragments[0].programDateTime!;
  }

  // Seek to the requested timestamp
  const fragment = findFragmentByTimestamp(fragments, requestedTimestampMillis);
  if (fragment) {
    let seekTarget = fragment.start;
    if (requestedTimestampMillis > fragment.programDateTime!) {
      seekTarget =
        fragment.start +
        (requestedTimestampMillis - fragment.programDateTime!) / 1000;
    } else {
      seekTarget = fragment.start;
    }
    videoRef.current.currentTime = seekTarget;
    videoRef.current.play();
  } else {
    videoRef.current.pause();
  }
};

const onManifestParsed = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
) => {
  if (!hlsRef.current || !videoRef.current) {
    return;
  }

  videoRef.current.muted = true;
  hlsRef.current.startLoad();
};

const onMediaAttached = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestampRef: React.MutableRefObject<number>,
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
        requestedTimestampRef,
      );
    },
  );
};

const initializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  auth: types.AuthEnabledResponse,
  camera: types.Camera | types.FailedCamera,
  requestedTimestampRef: React.MutableRefObject<number>,
) => {
  // Destroy the previous hls instance if it exists
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }

  // Create a new hls instance
  hlsRef.current = new Hls({
    maxBufferLength: 30, // 30 seconds of forward buffer
    backBufferLength: 15, // 15 seconds of back buffer
    liveSyncDurationCount: 2, // Start from the second last segment
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
  loadSource(hlsRef, hlsClientIdRef, requestedTimestampRef.current, camera);

  // Handle MEDIA_ATTACHED event
  hlsRef.current.on(Hls.Events.MEDIA_ATTACHED, () => {
    onMediaAttached(
      hlsRef,
      videoRef,
      initialProgramDateTime,
      requestedTimestampRef,
    );
  });

  // Handle errors
  hlsRef.current.on(Hls.Events.ERROR, (_event, data) => {
    if (data.fatal) {
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR:
          hlsRef.current!.startLoad();
          break;
        case Hls.ErrorTypes.MEDIA_ERROR:
          hlsRef.current!.recoverMediaError();
          break;
        default:
          initializePlayer(
            hlsRef,
            hlsClientIdRef,
            videoRef,
            initialProgramDateTime,
            auth,
            camera,
            requestedTimestampRef,
          );
          break;
      }
    }
  });
};

const useInitializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestampRef: React.MutableRefObject<number>,
  camera: types.Camera | types.FailedCamera,
) => {
  const { auth } = useAuthContext();
  const [addHlsRef, removeHlsRef] = useHlsStore((state) => [
    state.addHlsRef,
    state.removeHlsRef,
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
        requestedTimestampRef,
      );
    }
    const hls = hlsRef.current;
    return () => {
      if (hls) {
        hls.destroy();
        removeHlsRef(hlsRef);
        hlsRef.current = null;
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
};

// Seek to the requestedTimestamp if it is within the seekable range
const useSeekToTimestamp = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestamp: number,
  camera: types.Camera | types.FailedCamera,
) => {
  // Avoid running on first render to not call loadSource twice
  const firstRender = useFirstRender();
  useEffect(() => {
    if (
      !hlsRef.current ||
      !videoRef.current ||
      !hlsRef.current.media ||
      firstRender
    ) {
      return;
    }

    // Set seek target timestamp
    let seekTarget = requestedTimestamp;
    if (initialProgramDateTime.current) {
      seekTarget = requestedTimestamp - initialProgramDateTime.current / 1000;
    }

    // Seek to the requested timestamp
    const seekable = hlsRef.current.media.seekable;
    let seeked = false;
    for (let i = 0; i < seekable.length; i++) {
      if (seekTarget >= seekable.start(i) && seekTarget <= seekable.end(i)) {
        videoRef.current.currentTime = seekTarget;
        seeked = true;
        break;
      } else if (
        // Seek to start if target is less than start and within SCALE seconds of start
        seekTarget < seekable.start(i) &&
        seekable.start(i) - seekTarget < SCALE
      ) {
        videoRef.current.currentTime = seekable.start(i);
        seeked = true;
        break;
      } else if (
        // Seek to end if target is greater than end and within SCALE seconds of end
        seekTarget > seekable.end(i) &&
        seekTarget - seekable.end(i) < SCALE
      ) {
        videoRef.current.currentTime = seekable.end(i);
        seeked = true;
        break;
      }
    }

    if (!seeked && seekable.length > 0) {
      loadSource(hlsRef, hlsClientIdRef, requestedTimestamp, camera);
    }
  }, [
    camera,
    firstRender,
    hlsClientIdRef,
    hlsRef,
    initialProgramDateTime,
    requestedTimestamp,
    videoRef,
  ]);
};

interface TimelinePlayerProps {
  camera: types.Camera | types.FailedCamera;
  requestedTimestamp: number;
}

export const TimelinePlayer: React.FC<TimelinePlayerProps> = ({
  camera,
  requestedTimestamp,
}) => {
  const theme = useTheme();
  const hlsRef = useRef<Hls | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsClientIdRef = useRef<string>(uuidv4());
  const initialProgramDateTime = useRef<number | null>(null);
  const requestedTimestampRef = useRef<number>(requestedTimestamp);
  requestedTimestampRef.current = requestedTimestamp;
  useInitializePlayer(
    hlsRef,
    hlsClientIdRef,
    videoRef,
    initialProgramDateTime,
    requestedTimestampRef,
    camera,
  );
  useSeekToTimestamp(
    hlsRef,
    hlsClientIdRef,
    videoRef,
    initialProgramDateTime,
    requestedTimestamp,
    camera,
  );

  return (
    <video
      ref={videoRef}
      poster={BLANK_IMAGE}
      style={{
        width: "100%",
        backgroundColor: theme.palette.background.default,
        height: "100%",
        objectFit: "contain",
      }}
      controls
      playsInline
    />
  );
};
