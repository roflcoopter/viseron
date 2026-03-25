import { useCallback, useEffect, useRef, useState } from "react";
import screenfull from "screenfull";

// Extend HTMLVideoElement interface with WebKit-specific fullscreen properties
interface WebkitHTMLVideoElement extends HTMLVideoElement {
  webkitEnterFullscreen?: () => void;
  webkitExitFullscreen?: () => void;
  webkitSupportsFullscreen?: boolean;
  webkitDisplayingFullscreen?: boolean;
}

// Delay before resuming playback after iOS fullscreen exit (WebKit pauses video on exit)
const IOS_RESUME_DELAY_MS = 200;

// Checks if WebKit fullscreen is supported on the given video element.
const isWebkitFullscreenSupported = (
  video: HTMLVideoElement | null,
): video is WebkitHTMLVideoElement => {
  if (!video) return false;
  const webkitVideo = video as WebkitHTMLVideoElement;
  return typeof webkitVideo.webkitEnterFullscreen === "function";
};

// Handle fullscreen changes using the standard Fullscreen API
function useStandardFullscreen(
  isStandardFullscreenSupported: boolean,
  setIsFullscreen: React.Dispatch<React.SetStateAction<boolean>>,
) {
  useEffect(() => {
    if (!isStandardFullscreenSupported) return undefined;

    const handleFullscreenChange = () => {
      setIsFullscreen(screenfull.isFullscreen);
    };

    screenfull.on("change", handleFullscreenChange);
    return () => {
      screenfull.off("change", handleFullscreenChange);
    };
  }, [isStandardFullscreenSupported, setIsFullscreen]);
}

// Handle WebKit fullscreen events (iOS Safari)
function useWebkitFullscreen(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  isStandardFullscreenSupported: boolean,
  setIsFullscreen: React.Dispatch<React.SetStateAction<boolean>>,
) {
  const resumeTimeoutRef = useRef<NodeJS.Timeout>(undefined);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || isStandardFullscreenSupported) return undefined;
    if (!isWebkitFullscreenSupported(video)) return undefined;

    const handleWebkitBeginFullscreen = () => {
      // WebKit does not enter fullscreen mode if video is not playing
      video.play().catch(() => {
        // Ignore play errors
      });
      setIsFullscreen(true);
    };

    const handleWebkitEndFullscreen = () => {
      setIsFullscreen(false);

      // iOS WebKit pauses the video when exiting fullscreen.
      // Resume playback after a short delay to ensure the transition is complete.
      resumeTimeoutRef.current = setTimeout(() => {
        if (video && !video.paused) return; // Already playing
        video.play().catch(() => {
          // Ignore errors
        });
      }, IOS_RESUME_DELAY_MS);
    };

    video.addEventListener(
      "webkitbeginfullscreen",
      handleWebkitBeginFullscreen,
    );
    video.addEventListener("webkitendfullscreen", handleWebkitEndFullscreen);

    return () => {
      if (resumeTimeoutRef.current) {
        clearTimeout(resumeTimeoutRef.current);
      }
      video.removeEventListener(
        "webkitbeginfullscreen",
        handleWebkitBeginFullscreen,
      );
      video.removeEventListener(
        "webkitendfullscreen",
        handleWebkitEndFullscreen,
      );
    };
  }, [videoRef, isStandardFullscreenSupported, setIsFullscreen]);
}

// Hook to manage fullscreen state for video elements.
// Supports both the standard Fullscreen API (desktop/Android) and
// WebKit-specific fullscreen (iOS Safari).
//
// On iOS, only the video element itself can go fullscreen (not containers),
// so custom overlays won't be visible in fullscreen mode.
export function useFullscreen(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  containerRef?: React.RefObject<HTMLElement | null>,
) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Determine fullscreen support
  const isStandardFullscreenSupported = screenfull.isEnabled;
  const isWebkitSupported = isWebkitFullscreenSupported(videoRef.current);
  const isFullscreenSupported =
    isStandardFullscreenSupported || isWebkitSupported;

  // Handle standard fullscreen changes
  useStandardFullscreen(isStandardFullscreenSupported, setIsFullscreen);
  // Handle WebKit fullscreen events (iOS)
  useWebkitFullscreen(videoRef, isStandardFullscreenSupported, setIsFullscreen);

  const toggleFullscreen = useCallback(() => {
    // Standard Fullscreen API (desktop/Android)
    if (isStandardFullscreenSupported) {
      const target = containerRef?.current || videoRef.current;
      if (target) {
        screenfull.toggle(target);
      }
      return;
    }

    // WebKit fullscreen (iOS)
    const video = videoRef.current;
    if (video && isWebkitFullscreenSupported(video)) {
      const webkitVideo = video as WebkitHTMLVideoElement;
      if (webkitVideo.webkitDisplayingFullscreen) {
        webkitVideo.webkitExitFullscreen?.();
      } else {
        webkitVideo.webkitEnterFullscreen?.();
      }
    }
  }, [videoRef, containerRef, isStandardFullscreenSupported]);

  return {
    isFullscreen,
    isFullscreenSupported,
    toggleFullscreen,
  };
}
