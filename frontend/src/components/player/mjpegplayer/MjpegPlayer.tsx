import { VideoOff } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import { useTheme } from "@mui/material/styles";
import React, { useEffect, useRef, useState } from "react";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/player/CustomControls.js";
import { ZoomPanOverlay } from "components/player/ZoomPanOverlay";
import { useZoomPan } from "components/player/hooks/useZoomPan";
import { useMjpegPlayerControls } from "components/player/mjpegplayer/useMjpegPlayerControls";
import { isTouchDevice } from "lib/helpers";
import * as types from "lib/types";

const useMjpegErrorHandling = (
  imgRef: React.RefObject<HTMLImageElement | null>,
  src: string,
) => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const prevSrcRef = useRef<string>(src);

  // Reset state when src changes using useMemo/derived state approach
  if (prevSrcRef.current !== src) {
    prevSrcRef.current = src;
    // Reset error and loading state for new src
    if (error !== null) {
      setError(null);
    }
    if (!isLoading) {
      setIsLoading(true);
    }
  }

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return () => {};

    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    const handleError = () => {
      setError("Failed to load MJPEG stream.");
      setIsLoading(false);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const handleLoadStart = () => {
      setIsLoading(true);
      setError(null);
    };

    const handleLoad = () => {
      // For MJPEG streams, we want to show loading briefly even after load
      // to indicate the stream is initializing
      timeoutRef.current = setTimeout(() => {
        setIsLoading(false);
      }, 500); // Show loading for at least 500ms
    };

    img.addEventListener("error", handleError);
    img.addEventListener("loadstart", handleLoadStart);
    img.addEventListener("load", handleLoad);

    // Fallback timeout for streams that don't fire load events properly
    const fallbackTimeout = setTimeout(() => {
      if (img.complete || img.naturalWidth > 0) {
        setIsLoading(false);
      }
    }, 2000); // 2 second fallback

    return () => {
      img.removeEventListener("error", handleError);
      img.removeEventListener("loadstart", handleLoadStart);
      img.removeEventListener("load", handleLoad);

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      clearTimeout(fallbackTimeout);
    };
  }, [imgRef, src]); // Include src in dependencies

  return { error, isLoading };
};

interface MjpegPlayerProps extends React.HTMLAttributes<HTMLElement> {
  camera: types.Camera | types.FailedCamera;
  src: string;
  style?: React.CSSProperties;
  extraButtons?: React.ReactNode;
  drawObjects?: boolean;
  drawMotion?: boolean;
  drawObjectMask?: boolean;
  drawMotionMask?: boolean;
  drawZones?: boolean;
  drawPostProcessorMask?: boolean;
  isMenuOpen?: boolean;
  flipView?: boolean;
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void;
}

export function MjpegPlayer({
  camera,
  src,
  style,
  extraButtons,
  drawObjects = false,
  drawMotion = false,
  drawObjectMask = false,
  drawMotionMask = false,
  drawZones = false,
  drawPostProcessorMask = false,
  isMenuOpen = false,
  flipView = false,
  onPlayerFullscreenChange,
}: MjpegPlayerProps) {
  const theme = useTheme();
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const {
    controlsVisible,
    isHovering,
    isFullscreen,
    isPictureInPicture,
    handleFullscreenToggle,
    handlePictureInPictureToggle,
    isPictureInPictureSupported,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleManualRecording,
    manualRecordingLoading,
  } = useMjpegPlayerControls(containerRef, camera, onPlayerFullscreenChange);

  const { error, isLoading } = useMjpegErrorHandling(imgRef, src);

  // Disable zoom/pan when loading, camera is disconnected and still loading or has error
  const isZoomPanDisabled: boolean = Boolean(
    isLoading ||
      (!camera.failed && !(camera as types.Camera).connected) ||
      !!error,
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
        ...style,
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
        isVisible={controlsVisible || isHovering || isMenuOpen}
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
                {error ||
                  (!(camera as types.Camera).connected
                    ? "Camera Disconnected"
                    : "No Video Signal")}
              </Box>
            </Box>
          )}

        {/* Always render img element, but hide it visually when camera is disconnected */}
        <img
          ref={imgRef}
          src={(() => {
            let url = src;
            const params = [];
            if (drawObjects) params.push("draw_objects=1");
            if (drawMotion) params.push("draw_motion=1");
            if (drawObjectMask) params.push("draw_object_mask=1");
            if (drawMotionMask) params.push("draw_motion_mask=1");
            if (drawZones) params.push("draw_zones=1");
            if (drawPostProcessorMask)
              params.push("draw_post_processor_mask=1");
            if (params.length) {
              url += (url.includes("?") ? "&" : "?") + params.join("&");
            }
            return url;
          })()}
          alt="MJPEG Stream"
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            backgroundColor: theme.palette.background.default,
            userSelect: "none",
            pointerEvents: "none",
            transform: flipView ? "rotate(180deg)" : "none",
            transition: "transform 0.3s ease-in-out",
            // Hide img element when camera is disconnected (but keep it in DOM)
            display:
              !camera.failed && !(camera as types.Camera).connected
                ? "none"
                : "block",
          }}
          draggable={false}
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
        {isLoading && !isPictureInPicture && (
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
          isPictureInPicture
            ? "Picture-in-Picture Mode"
            : error || "MJPEG Stream"
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
