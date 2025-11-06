import { useTheme } from "@mui/material/styles";
import { VideoOff } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import React, { useCallback, useEffect, useRef, useState } from "react";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/player/CustomControls.js";
import { useZoomPan } from "components/player/hooks/useZoomPan";
import { ZoomPanOverlay } from "components/player/ZoomPanOverlay";
import { isTouchDevice } from "lib/helpers.js";
import * as types from "lib/types";

const useMjpegControlsVisibility = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void,
) => {
  const [controlsVisible, setControlsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showControlsTemporarily = useCallback(() => {
    setControlsVisible(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => setControlsVisible(false), 3000);
  }, []);

  const handleFullscreenToggle = useCallback(() => {
    if (!containerRef.current) return;
    const newFullscreenState = !isFullscreen;
    setIsFullscreen(newFullscreenState);
    onPlayerFullscreenChange?.(newFullscreenState);
  }, [isFullscreen, containerRef, onPlayerFullscreenChange]);

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

  useEffect(
    () => () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    },
    [],
  );

  return {
    controlsVisible,
    isHovering,
    isFullscreen,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
  };
};

const useMjpegErrorHandling = (
  imgRef: React.RefObject<HTMLImageElement | null>,
  src: string,
) => {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return () => {};
    const handleError = () => setError("Failed to load MJPEG stream.");
    img.addEventListener("error", handleError);
    return () => img.removeEventListener("error", handleError);
  }, [imgRef, src, setError]);

  return error;
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
  onPlayerFullscreenChange,
}: MjpegPlayerProps) {
  const theme = useTheme();
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const {
    controlsVisible,
    isHovering,
    isFullscreen,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
  } = useMjpegControlsVisibility(containerRef, onPlayerFullscreenChange);

  const error = useMjpegErrorHandling(imgRef, src);

  // Disable zoom/pan when camera is disconnected or has error
  const isZoomPanDisabled: boolean = Boolean((!camera.failed && !(camera as types.Camera).connected) || !!error);

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
        backgroundColor: isFullscreen ? theme.palette.background.default : "transparent",
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
      aria-label={isZoomPanDisabled ? "Video player" : "Video player - scroll to zoom, drag to pan, double-click to reset"}
      onKeyDown={isZoomPanDisabled ? undefined : (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          resetTransform();
        }
      }}
    >
      <CustomControls
        isVisible={controlsVisible || isHovering || isMenuOpen}
        isFullscreen={isFullscreen}
        onFullscreenToggle={handleFullscreenToggle}
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
        {(!camera.failed && !(camera as types.Camera).connected) || error ? (
          <Box
            sx={{
              width: "100%",
              height: "100%",
              backgroundColor: theme.palette.background.default,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 200,
              gap: 2,
            }}
          >
            <VideoOff 
              size={48} 
              style={{ 
                color: theme.palette.text.secondary,
                opacity: 0.5 
              }} 
            />
            <Box
              sx={{
                color: theme.palette.text.secondary,
                textAlign: 'center',
                fontSize: '0.875rem',
                opacity: 0.7,
                maxWidth: '80%',
                wordBreak: 'break-word',
              }}
            >
              {error || (!camera.failed && !(camera as types.Camera).connected ? "Camera Disconnected" : "No Video Signal")}
            </Box>
          </Box>
        ) : (
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
              if (drawPostProcessorMask) params.push("draw_post_processor_mask=1");
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
              display: "block",
              userSelect: "none",
              pointerEvents: "none",
            }}
            draggable={false}
          />
        )}
      </div>
      <CameraNameOverlay
        camera_identifier={camera.identifier}
        extraStatusText={error || "MJPEG Stream"}
      />
      <ZoomPanOverlay
        scale={scale}
        translateX={translateX}
        translateY={translateY}
        isVisible={!isZoomPanDisabled && (controlsVisible || isHovering || isMenuOpen)}
      />
    </div>
  );
}
