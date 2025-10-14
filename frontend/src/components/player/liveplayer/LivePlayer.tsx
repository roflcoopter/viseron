import React, { useCallback, useEffect, useRef, useState } from "react";
import screenfull from "screenfull";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/player/CustomControls.js";
import { VideoRTC } from "components/player/liveplayer/video-rtc.js";
import "components/player/liveplayer/video-stream.js";
import { isTouchDevice } from "lib/helpers.js";
import * as types from "lib/types";

const useVideoControlsVisibility = (
  playerRef: React.RefObject<VideoRTC | null>,
) => {
  const [controlsVisible, setControlsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showControlsTemporarily = useCallback(() => {
    setControlsVisible(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setControlsVisible(false);
    }, 3000); // Hide controls after 3 seconds
  }, []);

  const togglePlayPause = useCallback(() => {
    const videoElement = playerRef.current;
    if (videoElement && videoElement.video) {
      if (videoElement.video.paused) {
        videoElement.video.play();
      } else {
        videoElement.video.pause();
      }
    }
  }, [playerRef]);

  const handlePlayPause = useCallback(() => {
    togglePlayPause();
    showControlsTemporarily();
  }, [showControlsTemporarily, togglePlayPause]);

  const handleVolumeChange = useCallback(
    (event: Event, newVolume: number | number[]) => {
      const videoElement = playerRef.current;
      if (videoElement && videoElement.video) {
        videoElement.video.muted = false;
        videoElement.video.volume = (newVolume as number) / 100;
      }
      if ((newVolume as number) === 0) {
        setIsMuted(true);
      } else {
        setIsMuted(false);
      }
      showControlsTemporarily();
    },
    [playerRef, setIsMuted, showControlsTemporarily],
  );

  const handleMuteToggle = useCallback(() => {
    const videoElement = playerRef.current;
    if (videoElement && videoElement.video) {
      videoElement.video.muted = !isMuted;
    }
    setIsMuted(!isMuted);
    showControlsTemporarily();
  }, [playerRef, isMuted, showControlsTemporarily]);

  const handleFullscreenToggle = useCallback(() => {
    const elem = playerRef.current?.video;
    if (!elem) return;
    if (!isFullscreen) {
      if (screenfull.isEnabled) {
        screenfull.request(elem);
      }
    } else {
      screenfull.exit();
    }
  }, [playerRef, isFullscreen]);

  const handleMouseEnter = useCallback(() => {
    setIsHovering(true);
    setControlsVisible(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    setControlsVisible(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  }, []);

  const handleTouchStart = useCallback(() => {
    if (controlsVisible) {
      setControlsVisible(false);
    } else {
      showControlsTemporarily();
    }
  }, [controlsVisible, showControlsTemporarily]);

  useEffect(() => {
    const videoElement = playerRef.current;
    if (!videoElement || !videoElement.video) return () => {};
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    videoElement.video.addEventListener("play", handlePlay);
    videoElement.video.addEventListener("pause", handlePause);
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      videoElement.video!.removeEventListener("play", handlePlay);
      videoElement.video!.removeEventListener("pause", handlePause);
    };
  }, [playerRef]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(
        !!document.fullscreenElement &&
          document.fullscreenElement === playerRef.current,
      );
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [playerRef]);

  return {
    handlePlayPause,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isMuted,
    isFullscreen,
  };
};

const usePlayerStatus = (playerRef: React.RefObject<VideoRTC | null>) => {
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    const handleStatus = (e: Event) => {
      const customEvent = e as CustomEvent;
      setStatus(customEvent.detail?.value || "");
    };
    const videoElement = playerRef.current;
    videoElement?.addEventListener("status", handleStatus);
    return () => {
      videoElement?.removeEventListener("status", handleStatus);
    };
  }, [playerRef]);
  return status;
};

interface LivePlayerProps extends React.HTMLAttributes<HTMLElement> {
  camera: types.Camera | types.FailedCamera;
  controls?: boolean;
  src: string;
  style?: React.CSSProperties;
  playerRef?: React.RefObject<VideoRTC | null>;
  extraButtons?: React.ReactNode;
  isMenuOpen?: boolean;
}

export function LivePlayer({
  camera,
  controls,
  src,
  style,
  playerRef,
  extraButtons,
  isMenuOpen = false,
}: LivePlayerProps) {
  const _elementRef = useRef<VideoRTC>(null);
  const elementRef = playerRef || _elementRef;
  const containerRef = useRef<HTMLDivElement>(null);

  const playerStatus = usePlayerStatus(elementRef);

  const {
    handlePlayPause,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isPlaying,
    isHovering,
    isMuted,
    isFullscreen,
  } = useVideoControlsVisibility(elementRef);

  useEffect(() => {
    if (elementRef.current) {
      elementRef.current.src = src;
      elementRef.current.controls = controls === undefined ? true : controls;
    }
  }, [elementRef, src, controls]);

  return (
    <div
      ref={containerRef}
      style={{ position: "relative", width: "100%", height: "100%" }}
      onMouseEnter={isTouchDevice() ? undefined : handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
    >
      <CustomControls
        onPlayPause={handlePlayPause}
        onVolumeChange={handleVolumeChange}
        onMuteToggle={handleMuteToggle}
        isVisible={controlsVisible || isHovering || isMenuOpen}
        isPlaying={isPlaying}
        isMuted={isMuted}
        isFullscreen={isFullscreen}
        onFullscreenToggle={handleFullscreenToggle}
        extraButtons={extraButtons}
      />
      <video-stream ref={elementRef} style={style} controls={controlsVisible} />
      <CameraNameOverlay
        camera_identifier={camera.identifier}
        extraStatusText={playerStatus}
      />
    </div>
  );
}
