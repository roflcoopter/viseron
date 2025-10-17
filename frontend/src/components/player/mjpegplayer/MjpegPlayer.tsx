import { useTheme } from "@mui/material/styles";
import React, { useCallback, useEffect, useRef, useState } from "react";
import screenfull from "screenfull";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/player/CustomControls.js";
import { isTouchDevice } from "lib/helpers.js";
import * as types from "lib/types";

const useMjpegControlsVisibility = (
  containerRef: React.RefObject<HTMLDivElement | null>,
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
    if (!isFullscreen) {
      if (screenfull.isEnabled) {
        screenfull.request(containerRef.current);
      }
    } else {
      screenfull.exit();
    }
  }, [isFullscreen, containerRef]);

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
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

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
  } = useMjpegControlsVisibility(containerRef);

  const error = useMjpegErrorHandling(imgRef, src);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        ...style,
      }}
      onMouseEnter={isTouchDevice() ? undefined : handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
    >
      <CustomControls
        isVisible={controlsVisible || isHovering || isMenuOpen}
        isFullscreen={isFullscreen}
        onFullscreenToggle={handleFullscreenToggle}
        extraButtons={extraButtons}
      />
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
        }}
        draggable={false}
      />
      <CameraNameOverlay
        camera_identifier={camera.identifier}
        extraStatusText={error || "MJPEG Stream"}
      />
    </div>
  );
}
