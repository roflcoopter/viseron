import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import Hls, { LevelLoadedData } from "hls.js";
import React, { useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

import {
  SCALE,
  calculateHeight,
  findFragmentByTimestamp,
} from "components/events/utils";
import { useAuthContext } from "context/AuthContext";
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
  }
  videoRef.current.play();
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
    liveSyncDurationCount: 1,
    liveDurationInfinity: true,
    async xhrSetup(xhr, _url) {
      xhr.withCredentials = true;
      if (auth.enabled) {
        const token = await getToken();
        if (token) {
          xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }
        xhr.setRequestHeader("Hls-Client-Id", hlsClientIdRef.current);
      }
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

  useEffect(() => {
    if (Hls.isSupported()) {
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
  useEffect(() => {
    if (!hlsRef.current || !videoRef.current || !hlsRef.current.media) {
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

    if (!seeked) {
      loadSource(hlsRef, hlsClientIdRef, requestedTimestamp, camera);
    }
    videoRef.current.play();
  }, [
    camera,
    hlsClientIdRef,
    hlsRef,
    initialProgramDateTime,
    requestedTimestamp,
    videoRef,
  ]);
};

const useResizeObserver = (
  containerRef: React.RefObject<HTMLDivElement>,
  videoRef: React.RefObject<HTMLVideoElement>,
  camera: types.Camera | types.FailedCamera,
) => {
  const resizeObserver = useRef<ResizeObserver>();

  useEffect(() => {
    if (containerRef.current) {
      resizeObserver.current = new ResizeObserver(() => {
        videoRef.current!.style.height = `${calculateHeight(
          camera.width,
          camera.height,
          containerRef.current!.offsetWidth,
        )}px`;
      });
      resizeObserver.current.observe(containerRef.current);
    }
    return () => {
      if (resizeObserver.current) {
        resizeObserver.current.disconnect();
      }
    };
  }, [camera, containerRef, videoRef]);
};
interface TimelinePlayerProps {
  containerRef: React.RefObject<HTMLDivElement>;
  hlsRef: React.MutableRefObject<Hls | null>;
  camera: types.Camera | types.FailedCamera;
  requestedTimestamp: number;
}

export const TimelinePlayer: React.FC<TimelinePlayerProps> = ({
  containerRef,
  hlsRef,
  camera,
  requestedTimestamp,
}) => {
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
  useResizeObserver(containerRef, videoRef, camera);

  return (
    <video
      ref={videoRef}
      style={{
        width: "100%",
        verticalAlign: "top",
        height: containerRef.current
          ? calculateHeight(
              camera.width,
              camera.height,
              containerRef.current.offsetWidth,
            )
          : undefined,
      }}
      controls
      playsInline
    />
  );
};
