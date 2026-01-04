import { VideoOff } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import { useTheme } from "@mui/material/styles";
import React, { useCallback, useEffect, useRef, useState } from "react";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/player/CustomControls.js";
import { usePlayerSettingsStore } from "components/player/UsePlayerSettingsStore";
import { ZoomPanOverlay } from "components/player/ZoomPanOverlay";
import { useZoomPan } from "components/player/hooks/useZoomPan";
import { VideoRTC } from "components/player/liveplayer/video-rtc.js";
import "components/player/liveplayer/video-stream.js";
import { useCameraManualRecording } from "lib/api/camera";
import { isTouchDevice } from "lib/helpers.js";
import * as types from "lib/types";

const useVideoControlsVisibility = (
  playerRef: React.RefObject<VideoRTC | null>,
  camera: types.Camera | types.FailedCamera,
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void,
) => {
  const [controlsVisible, setControlsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPictureInPicture, setIsPictureInPicture] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const manualRecording = useCameraManualRecording();

  // Get mute state from store
  const isMuted = usePlayerSettingsStore(
    (state) => state.muteMap[camera.identifier] ?? false,
  );
  const setMute = usePlayerSettingsStore((state) => state.setMute);

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
        setMute(camera.identifier, true);
      } else {
        setMute(camera.identifier, false);
      }
      showControlsTemporarily();
    },
    [playerRef, camera, setMute, showControlsTemporarily],
  );

  const handleMuteToggle = useCallback(() => {
    const videoElement = playerRef.current;
    if (videoElement && videoElement.video) {
      videoElement.video.muted = !isMuted;
    }
    setMute(camera.identifier, !isMuted);
    showControlsTemporarily();
  }, [playerRef, camera, isMuted, setMute, showControlsTemporarily]);

  const handleFullscreenToggle = useCallback(() => {
    const newFullscreenState = !isFullscreen;
    setIsFullscreen(newFullscreenState);
    onPlayerFullscreenChange?.(newFullscreenState);
  }, [isFullscreen, onPlayerFullscreenChange]);

  const handlePictureInPictureToggle = useCallback(async () => {
    try {
      const videoElement = playerRef.current?.video;
      if (!videoElement) return;

      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsPictureInPicture(false);
      } else {
        await videoElement.requestPictureInPicture();
        setIsPictureInPicture(true);

        // Ensure video is playing before requesting PiP
        if (videoElement.paused) {
          await videoElement.play();
        }
      }
    } catch (error) {
      console.error("Error toggling Picture in Picture:", error);
      setIsPictureInPicture(false);
    }
  }, [playerRef]);

  const isPictureInPictureSupported = useCallback(
    () =>
      "pictureInPictureEnabled" in document && document.pictureInPictureEnabled,
    [],
  );

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

  const handleManualRecording = useCallback(() => {
    if (camera.failed || manualRecording.isPending) {
      return;
    }
    if (camera.is_recording) {
      manualRecording.mutate({ camera, action: "stop" });
    } else {
      manualRecording.mutate({ camera, action: "start" });
    }
  }, [manualRecording, camera]);

  useEffect(() => {
    const videoElement = playerRef.current;
    if (!videoElement || !videoElement.video) return () => {};

    // Sync mute state with video element on mount
    videoElement.video.muted = isMuted;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    // Handle PiP state changes
    const handleEnterPiP = () => setIsPictureInPicture(true);
    const handleLeavePiP = () => setIsPictureInPicture(false);

    videoElement.video.addEventListener("play", handlePlay);
    videoElement.video.addEventListener("pause", handlePause);
    videoElement.video.addEventListener(
      "enterpictureinpicture",
      handleEnterPiP,
    );
    videoElement.video.addEventListener(
      "leavepictureinpicture",
      handleLeavePiP,
    );

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      videoElement.video!.removeEventListener("play", handlePlay);
      videoElement.video!.removeEventListener("pause", handlePause);
      videoElement.video!.removeEventListener(
        "enterpictureinpicture",
        handleEnterPiP,
      );
      videoElement.video!.removeEventListener(
        "leavepictureinpicture",
        handleLeavePiP,
      );
    };
  }, [playerRef, isMuted]);

  return {
    handlePlayPause,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handlePictureInPictureToggle,
    isPictureInPictureSupported: isPictureInPictureSupported(),
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleManualRecording,
    manualRecordingLoading: manualRecording.isPending,
    controlsVisible,
    isHovering,
    isPlaying,
    isMuted,
    isFullscreen,
    isPictureInPicture,
  };
};

const usePlayerStatus = (playerRef: React.RefObject<VideoRTC | null>) => {
  const [status, setStatus] = useState<string>("");
  const [hasError, setHasError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const handleStatus = (e: Event) => {
      const customEvent = e as CustomEvent;
      const statusValue = customEvent.detail?.value || "";

      // Ignore "Loading" status text - we show spinner instead
      if (statusValue.toLowerCase() === "loading") {
        return;
      }

      setStatus(statusValue);

      // Check if status indicates an error
      const isError =
        statusValue.toLowerCase().includes("error") ||
        statusValue.toLowerCase().includes("failed") ||
        statusValue.toLowerCase().includes("disconnect");
      setHasError(isError);

      // Check if status indicates loading is complete
      if (
        statusValue.toLowerCase().includes("connected") ||
        statusValue.toLowerCase().includes("playing") ||
        isError
      ) {
        setIsLoading(false);
      }
    };
    const videoElement = playerRef.current;
    videoElement?.addEventListener("status", handleStatus);

    // Also listen for error events directly on the video element
    const handleError = () => {
      setHasError(true);
      setStatus("Connection failed");
      setIsLoading(false);
    };

    const handleLoadStart = () => setIsLoading(true);
    const handleCanPlay = () => setIsLoading(false);
    const handleLoadedData = () => setIsLoading(false);

    if (videoElement?.video) {
      videoElement.video.addEventListener("error", handleError);
      videoElement.video.addEventListener("loadstart", handleLoadStart);
      videoElement.video.addEventListener("canplay", handleCanPlay);
      videoElement.video.addEventListener("loadeddata", handleLoadedData);
    }

    return () => {
      videoElement?.removeEventListener("status", handleStatus);
      if (videoElement?.video) {
        videoElement.video.removeEventListener("error", handleError);
        videoElement.video.removeEventListener("loadstart", handleLoadStart);
        videoElement.video.removeEventListener("canplay", handleCanPlay);
        videoElement.video.removeEventListener("loadeddata", handleLoadedData);
      }
    };
  }, [playerRef]);

  return { status, hasError, isLoading };
};

interface LivePlayerProps extends React.HTMLAttributes<HTMLElement> {
  camera: types.Camera | types.FailedCamera;
  src: string;
  style?: React.CSSProperties;
  playerRef?: React.RefObject<VideoRTC | null>;
  extraButtons?: React.ReactNode;
  isMenuOpen?: boolean;
  flipView?: boolean;
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void;
}

export function LivePlayer({
  camera,
  src,
  style,
  playerRef,
  extraButtons,
  isMenuOpen = false,
  flipView = false,
  onPlayerFullscreenChange,
}: LivePlayerProps) {
  const _elementRef = useRef<VideoRTC>(null);
  const elementRef = playerRef || _elementRef;
  const containerRef = useRef<HTMLDivElement>(null);
  const theme = useTheme();

  const {
    status: playerStatus,
    hasError,
    isLoading,
  } = usePlayerStatus(elementRef);

  const {
    handlePlayPause,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handlePictureInPictureToggle,
    isPictureInPictureSupported,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleManualRecording,
    manualRecordingLoading,
    controlsVisible,
    isPlaying,
    isHovering,
    isMuted,
    isFullscreen,
    isPictureInPicture,
  } = useVideoControlsVisibility(elementRef, camera, onPlayerFullscreenChange);

  // Disable zoom/pan when loading, camera is disconnected and still loading or has error
  const isZoomPanDisabled: boolean = Boolean(
    isLoading ||
      (!camera.failed && !(camera as types.Camera).connected) ||
      hasError,
  );

  const {
    transformStyle,
    handleMouseDown,
    resetTransform,
    scale,
    translateX,
    translateY,
    cursor,
  } = useZoomPan(containerRef, {
    minScale: 1.0,
    maxScale: 5,
    zoomSpeed: 0.2,
    disabled: isZoomPanDisabled,
  });

  useEffect(() => {
    if (elementRef.current) {
      elementRef.current.src = src;
      elementRef.current.controls = false; // Always hide native controls
    }
  }, [elementRef, src]);

  return (
    <div
      ref={containerRef}
      style={{
        position: isFullscreen ? "fixed" : "relative",
        top: isFullscreen ? 0 : "auto",
        left: isFullscreen ? 0 : "auto",
        width: isFullscreen ? "100vw" : "100%",
        height: isFullscreen ? "100vh" : "100%",
        zIndex: isFullscreen ? 8000 : "auto",
        backgroundColor: isFullscreen
          ? theme.palette.background.default
          : "transparent",
        overflow: "hidden",
        cursor: isZoomPanDisabled ? "default" : cursor,
      }}
      onMouseEnter={isTouchDevice() ? undefined : handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
      onMouseDown={isZoomPanDisabled ? undefined : handleMouseDown}
      onDoubleClick={isZoomPanDisabled ? undefined : resetTransform}
      role="button"
      tabIndex={0}
      aria-label={
        isZoomPanDisabled
          ? "Video player"
          : "Video player - scroll to zoom, drag to pan, double-click to reset"
      }
      onKeyDown={
        isZoomPanDisabled
          ? undefined
          : (e) => {
              if (e.key === "Enter" || e.key === " ") {
                resetTransform();
              }
            }
      }
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
        onPictureInPictureToggle={handlePictureInPictureToggle}
        isPictureInPictureSupported={isPictureInPictureSupported}
        onManualRecording={camera.failed ? undefined : handleManualRecording}
        isRecording={camera.failed ? undefined : camera.is_recording}
        manualRecordingLoading={manualRecordingLoading}
        extraButtons={extraButtons}
      />
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
          ...(!isZoomPanDisabled ? transformStyle : {}),
        }}
      >
        {/* Show placeholder when camera is disconnected (but NOT when in PiP mode) */}
        {!camera.failed &&
          !(camera as types.Camera).connected &&
          !isPictureInPicture && (
            <Box
              sx={{
                width: "100%",
                height: "100%",
                backgroundColor: theme.palette.background.default,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 200,
                gap: 2,
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
                {playerStatus ||
                  (!(camera as types.Camera).connected
                    ? "Camera Disconnected"
                    : "No Video Signal")}
              </Box>
            </Box>
          )}

        {/* Always render video-stream element, but hide it visually when camera is disconnected */}
        <video-stream
          ref={elementRef}
          style={{
            ...style,
            userSelect: "none",
            pointerEvents: "none",
            transform: flipView ? "rotate(180deg)" : "none",
            transition: "transform 0.3s ease-in-out",
            // Hide video element when camera is disconnected (but keep it in DOM)
            display:
              !camera.failed && !(camera as types.Camera).connected
                ? "none"
                : "block",
          }}
        />

        {/* Show PiP overlay when in Picture-in-Picture mode */}
        {isPictureInPicture && (
          <Box
            sx={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: theme.palette.background.default,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
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
              Playing in Picture-in-Picture
            </Box>
          </Box>
        )}

        {/* Show loading indicator */}
        {isLoading &&
          !isPictureInPicture &&
          (camera.failed || (camera as types.Camera).connected) && (
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
      </div>
      <CameraNameOverlay
        camera_identifier={camera.identifier}
        extraStatusText={
          isPictureInPicture ? "Picture-in-Picture Mode" : playerStatus
        }
      />
      <ZoomPanOverlay
        scale={scale}
        translateX={translateX}
        translateY={translateY}
        isVisible={
          !isZoomPanDisabled && (controlsVisible || isHovering || isMenuOpen)
        }
      />
    </div>
  );
}
