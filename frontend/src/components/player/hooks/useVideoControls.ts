import { useCallback, useEffect, useRef, useState } from "react";

const CONTROLS_HIDE_DELAY = 3000;

export interface UseVideoControlsOptions {
  onFullscreenChange?: (isFullscreen: boolean) => void;
  initialFullscreen?: boolean;
}

export interface UseVideoControlsReturn {
  // Visibility state
  controlsVisible: boolean;
  isHovering: boolean;
  isFullscreen: boolean;

  // Visibility handlers
  showControlsTemporarily: () => void;
  handleMouseEnter: () => void;
  handleMouseMove: () => void;
  handleMouseLeave: () => void;
  handleTouchStart: () => void;

  // Fullscreen handlers
  setIsFullscreen: React.Dispatch<React.SetStateAction<boolean>>;
  handleFullscreenToggle: () => void;
}

// Hook for managing common logic for video controls. used across the different
// video player implementations.
export function useVideoControls(
  options: UseVideoControlsOptions = {},
): UseVideoControlsReturn {
  const { onFullscreenChange, initialFullscreen = false } = options;

  const [controlsVisible, setControlsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(initialFullscreen);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showControlsTemporarily = useCallback(() => {
    setControlsVisible(true);
    setIsHovering(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setControlsVisible(false);
      setIsHovering(false);
    }, CONTROLS_HIDE_DELAY);
  }, []);

  // NOTE: mouseenter/mousemove are also synthesized by browsers after a touch
  // tap, but no mouseleave ever follows on touch-only devices.
  const handleMouseEnter = useCallback(() => {
    showControlsTemporarily();
  }, [showControlsTemporarily]);
  const handleMouseMove = useCallback(() => {
    showControlsTemporarily();
  }, [showControlsTemporarily]);

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
      setIsHovering(false);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    } else {
      showControlsTemporarily();
    }
  }, [controlsVisible, showControlsTemporarily]);

  const handleFullscreenToggle = useCallback(() => {
    const newFullscreenState = !isFullscreen;
    setIsFullscreen(newFullscreenState);
    onFullscreenChange?.(newFullscreenState);
  }, [isFullscreen, onFullscreenChange]);

  // Cleanup timeout on unmount
  useEffect(
    () => () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    },
    [],
  );

  return {
    // Visibility state
    controlsVisible,
    isHovering,
    isFullscreen,

    // Visibility handlers
    showControlsTemporarily,
    handleMouseEnter,
    handleMouseMove,
    handleMouseLeave,
    handleTouchStart,

    // Fullscreen handlers
    setIsFullscreen,
    handleFullscreenToggle,
  };
}
