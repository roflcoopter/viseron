import { useTheme } from "@mui/material/styles";
import Hls from "hls.js";
import React, { useCallback, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { useShallow } from "zustand/react/shallow";

import { useHlsStore } from "components/events/utils";
import { CustomControls } from "components/player/CustomControls";
import { HlsErrorOverlay } from "components/player/hlsplayer/HlsErrorOverlay";
import { useHlsPlayerControls } from "components/player/hlsplayer/useHlsPlayerControls";
import {
  cleanupHlsInstance,
  createHlsInstance,
  setupHlsErrorHandling,
} from "components/player/hlsplayer/utils";
import { useAuthContext } from "context/AuthContext";
import { BLANK_IMAGE, isTouchDevice } from "lib/helpers";
import * as types from "lib/types";

const useLoadSourceOnPlay = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  camera: types.Camera | types.FailedCamera,
  recording: types.Recording | null,
) => {
  useEffect(() => {
    if (!recording) {
      return () => {};
    }
    const video = videoRef.current;
    if (!video) return () => {};

    const handlePlay = () => {
      if (!hlsRef.current) {
        return;
      }
      hlsClientIdRef.current = uuidv4();
      hlsRef.current.loadSource(recording.hls_url);
      // Remove the event listener after loading the source
      video.removeEventListener("play", handlePlay);
    };

    video.addEventListener("play", handlePlay);
    return () => video.removeEventListener("play", handlePlay);
  }, [hlsRef, hlsClientIdRef, videoRef, camera, recording]);
};

const initializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
  auth: types.AuthEnabledResponse,
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

  // Create a new hls instance using shared factory
  hlsRef.current = createHlsInstance(auth, hlsClientIdRef);

  if (videoRef.current) {
    hlsRef.current.attachMedia(videoRef.current);
  }

  // Setup error handling using shared utility
  setupHlsErrorHandling(hlsRef.current, {
    hlsRef,
    setHlsRefsError,
    delayedInitializationTimeoutRef,
    delayedRecoveryTimeoutRef,
    onReinitialize: () => {
      initializePlayer(
        hlsRef,
        hlsClientIdRef,
        videoRef,
        auth,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    },
  });
};

const useInitializePlayer = (
  hlsRef: React.MutableRefObject<Hls | null>,
  hlsClientIdRef: React.MutableRefObject<string>,
  videoRef: React.RefObject<HTMLVideoElement | null>,
) => {
  const { auth } = useAuthContext();
  const { addHlsRef, removeHlsRef, setHlsRefsError } = useHlsStore(
    useShallow((state) => ({
      addHlsRef: state.addHlsRef,
      removeHlsRef: state.removeHlsRef,
      setHlsRefsError: state.setHlsRefsError,
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
        auth,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    }
  }, [hlsRef, hlsClientIdRef, videoRef, auth, setHlsRefsError]);

  useEffect(() => {
    if (Hls.isSupported()) {
      addHlsRef(hlsRef);
      initializePlayer(
        hlsRef,
        hlsClientIdRef,
        videoRef,
        auth,
        setHlsRefsError,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    }
    return () => {
      cleanupHlsInstance(
        hlsRef,
        removeHlsRef,
        delayedInitializationTimeoutRef,
        delayedRecoveryTimeoutRef,
      );
    };
    // Must disable this warning since we dont want to ever run this twice
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return {
    reInitPlayer,
  };
};

interface HlsVodPlayerProps {
  camera: types.Camera | types.FailedCamera;
  recording?: types.Recording | null;
  poster?: string;
  loop?: boolean;
}

export function HlsVodPlayer({
  camera,
  recording = null,
  poster = BLANK_IMAGE,
  loop = false,
}: HlsVodPlayerProps) {
  const theme = useTheme();
  const hlsRef = useRef<Hls | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsClientIdRef = useRef<string>(uuidv4());

  const { hlsRefError } = useHlsStore(
    useShallow((state) => ({
      hlsRefError: state.hlsRefsError.get(hlsRef),
    })),
  );

  const {
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleVolumeChange,
    handleMuteToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isMuted,
  } = useHlsPlayerControls(videoRef);

  useInitializePlayer(hlsRef, hlsClientIdRef, videoRef);
  useLoadSourceOnPlay(hlsRef, hlsClientIdRef, videoRef, camera, recording);

  const aspectRatio = camera.mainstream.width / camera.mainstream.height;

  return (
    <div
      data-testid="hls-vod-player"
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        display: "flex",
        aspectRatio,
      }}
      onMouseEnter={!isTouchDevice() ? handleMouseEnter : undefined}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
    >
      {/* Always render video-element */}
      <video
        ref={videoRef}
        poster={poster}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          backgroundColor: theme.palette.background.default,
        }}
        controls={false}
        loop={loop}
        playsInline
        muted
      />

      <CustomControls
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onJumpBackward={handleJumpBackward}
        onJumpForward={handleJumpForward}
        isVisible={controlsVisible || isHovering}
        onVolumeChange={handleVolumeChange}
        isMuted={isMuted}
        onMuteToggle={handleMuteToggle}
        videoRef={videoRef}
        showProgressBar={!!recording}
      />

      {hlsRef.current && <HlsErrorOverlay error={hlsRefError} />}
    </div>
  );
}

export default HlsVodPlayer;
