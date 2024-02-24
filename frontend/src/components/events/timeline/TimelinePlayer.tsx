import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import Hls from "hls.js";
import React, { useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

import {
  calculateHeight,
  findFragmentByTimestamp,
} from "components/events/timeline/utils";
import { useAuthContext } from "context/AuthContext";
import { getToken } from "lib/tokens";
import * as types from "lib/types";

dayjs.extend(utc);

const initializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
  intervalRef: React.MutableRefObject<NodeJS.Timeout | null>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  auth: types.AuthEnabledResponse,
  camera: types.Camera,
  requestedTimestamp: number,
) => {
  const requestedTimestampMillis = requestedTimestamp * 1000;
  // Destroy the previous hls instance if it exists
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }

  // Create a new hls instance
  const hlsClientId = uuidv4();
  hlsRef.current = new Hls({
    maxBufferLength: 30, // 30 seconds of forward buffer
    backBufferLength: 15, // 15 seconds of back buffer
    liveSyncDurationCount: 1,
    liveDurationInfinity: true,
    async xhrSetup(xhr, _url) {
      xhr.withCredentials = true;
      if (auth) {
        const token = await getToken();
        if (token) {
          xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }
        xhr.setRequestHeader("Hls-Client-Id", hlsClientId);
      }
    },
  });

  if (videoRef.current) {
    hlsRef.current.attachMedia(videoRef.current);
  }

  // Load the source and start the hls instance
  hlsRef.current.on(Hls.Events.MEDIA_ATTACHED, () => {
    const source = `/api/v1/hls/${
      camera.identifier
    }/index.m3u8?start_timestamp=${requestedTimestamp - 3600}`;
    hlsRef.current!.loadSource(source);
    hlsRef.current!.on(Hls.Events.MANIFEST_PARSED, () => {
      if (!hlsRef.current || !videoRef.current) {
        return;
      }

      videoRef.current.muted = true;
      hlsRef.current.startLoad();

      // Wait for the manifest to be parsed and then seek to the requested timestamp
      intervalRef.current = setInterval(() => {
        if (
          hlsRef.current &&
          hlsRef.current.levels[hlsRef.current.currentLevel]
        ) {
          const fragments =
            hlsRef.current.levels[hlsRef.current.currentLevel].details
              ?.fragments || [];

          if (fragments.length > 0) {
            initialProgramDateTime.current = fragments[0].programDateTime!;
          }

          const fragment = findFragmentByTimestamp(
            hlsRef.current.levels[hlsRef.current.currentLevel].details
              ?.fragments || [],
            requestedTimestampMillis,
          );

          if (fragment && videoRef.current) {
            let seekTarget = fragment.start;
            if (requestedTimestampMillis > fragment.programDateTime!) {
              seekTarget =
                fragment.start +
                (requestedTimestampMillis - fragment.programDateTime!) / 1000;
            }
            videoRef.current.currentTime = seekTarget;
            videoRef.current.play();
          }
          clearInterval(intervalRef.current as NodeJS.Timeout);
        }
      }, 50);
    });
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
            videoRef,
            intervalRef,
            initialProgramDateTime,
            auth,
            camera,
            requestedTimestamp,
          );
          break;
      }
    }
  });
};

const useInitializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestamp: number,
  camera: types.Camera,
) => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const { auth } = useAuthContext();

  useEffect(() => {
    if (Hls.isSupported()) {
      initializePlayer(
        hlsRef,
        videoRef,
        intervalRef,
        initialProgramDateTime,
        auth,
        camera,
        requestedTimestamp,
      );
    }
    const hls = hlsRef.current;
    const interval = intervalRef.current;
    return () => {
      if (hls) {
        hls.destroy();
        hlsRef.current = null;
      }
      if (interval) {
        clearInterval(interval);
      }
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
};

const useSeekToTimestamp = (
  hlsRef: React.MutableRefObject<Hls | null>,
  videoRef: React.RefObject<HTMLVideoElement>,
  initialProgramDateTime: React.MutableRefObject<number | null>,
  requestedTimestamp: number,
) => {
  useEffect(() => {
    // Seek to the requestedTimestamp if it is within the seekable range
    if (hlsRef.current && videoRef.current && initialProgramDateTime.current) {
      const seekTarget =
        requestedTimestamp - initialProgramDateTime.current / 1000;
      if (hlsRef.current.media) {
        const seekable = hlsRef.current.media.seekable;
        for (let i = 0; i < seekable.length; i++) {
          if (
            seekTarget >= seekable.start(i) &&
            seekTarget <= seekable.end(i)
          ) {
            videoRef.current.currentTime = seekTarget;
            videoRef.current.play();
            break;
          } else if (seekTarget < seekable.start(i)) {
            videoRef.current.currentTime = seekable.start(i);
            videoRef.current.play();
            break;
          } else if (seekTarget > seekable.end(i)) {
            videoRef.current.currentTime = seekable.end(i);
            videoRef.current.play();
          }
        }
      }
    }
  }, [hlsRef, initialProgramDateTime, requestedTimestamp, videoRef]);
};

interface TimelinePlayerProps {
  containerRef: React.RefObject<HTMLDivElement>;
  hlsRef: React.MutableRefObject<Hls | null>;
  camera: types.Camera;
  requestedTimestamp: number;
}

export const TimelinePlayer: React.FC<TimelinePlayerProps> = ({
  containerRef,
  hlsRef,
  camera,
  requestedTimestamp,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const initialProgramDateTime = useRef<number | null>(null);
  const resizeObserver = useRef<ResizeObserver>();
  useInitializePlayer(
    hlsRef,
    videoRef,
    initialProgramDateTime,
    requestedTimestamp,
    camera,
  );
  useSeekToTimestamp(
    hlsRef,
    videoRef,
    initialProgramDateTime,
    requestedTimestamp,
  );

  useEffect(() => {
    if (containerRef.current) {
      resizeObserver.current = new ResizeObserver(() => {
        videoRef.current!.style.height = `${calculateHeight(
          camera,
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
  }, [camera, containerRef]);

  return (
    <video
      ref={videoRef}
      style={{
        width: "100%",
        verticalAlign: "top",
        height: containerRef.current
          ? calculateHeight(camera, containerRef.current.offsetWidth)
          : undefined,
      }}
      controls
      playsInline
    />
  );
};
