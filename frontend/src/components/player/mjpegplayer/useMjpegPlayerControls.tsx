import React, { useCallback, useEffect, useRef, useState } from "react";

import { useVideoControls } from "components/player/hooks/useVideoControls";
import { useCameraManualRecording } from "lib/api/camera";
import * as types from "lib/types";

export const useMjpegPlayerControls = (
  containerRef: React.RefObject<HTMLDivElement | null>,
  camera: types.Camera | types.FailedCamera,
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void,
) => {
  const [isPictureInPicture, setIsPictureInPicture] = useState(false);
  const pipVideoRef = useRef<HTMLVideoElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const manualRecording = useCameraManualRecording();

  const {
    controlsVisible,
    isHovering,
    isFullscreen,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleFullscreenToggle,
  } = useVideoControls({
    onFullscreenChange: onPlayerFullscreenChange,
  });

  const handlePictureInPictureToggle = useCallback(async () => {
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsPictureInPicture(false);
      } else {
        // Find the img element in our container
        const imgElement = containerRef.current?.querySelector("img");
        if (imgElement && imgElement.src) {
          // Create a video element for PiP
          const videoElement = document.createElement("video");
          videoElement.muted = true;
          videoElement.autoplay = true;
          videoElement.loop = true;
          videoElement.style.display = "none";
          videoElement.style.position = "absolute";
          videoElement.style.top = "-9999px";

          // Store reference for cleanup
          pipVideoRef.current = videoElement;

          // Create canvas for converting MJPEG to video stream
          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");

          if (ctx) {
            // Set initial canvas size
            canvas.width = imgElement.naturalWidth || 640;
            canvas.height = imgElement.naturalHeight || 480;

            // Create MediaStream from canvas
            const stream = canvas.captureStream(15); // 15 FPS
            videoElement.srcObject = stream;

            // Add video to DOM
            document.body.appendChild(videoElement);

            // Function to update canvas with current MJPEG frame
            let isAnimating = false;
            const updateCanvas = () => {
              if (
                isAnimating &&
                imgElement.complete &&
                imgElement.naturalWidth > 0
              ) {
                try {
                  // Update canvas size if needed
                  if (
                    canvas.width !== imgElement.naturalWidth ||
                    canvas.height !== imgElement.naturalHeight
                  ) {
                    canvas.width = imgElement.naturalWidth;
                    canvas.height = imgElement.naturalHeight;
                  }

                  // Draw current frame
                  ctx.clearRect(0, 0, canvas.width, canvas.height);
                  ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);

                  // Continue animation
                  animationRef.current = requestAnimationFrame(updateCanvas);
                } catch (error) {
                  console.warn("Error updating PiP canvas:", error);
                }
              }
            };

            // Wait for video to be ready
            await new Promise<void>((resolve, reject) => {
              let isResolved = false;

              // Define cleanup function that will be assigned later
              let cleanup: () => void;

              // Define timeout that will be assigned later
              let timeoutId: NodeJS.Timeout;

              const onError = () => {
                if (!isResolved) {
                  isResolved = true;
                  clearTimeout(timeoutId);
                  cleanup();
                  reject(new Error("Video load failed"));
                }
              };

              const onCanPlay = () => {
                if (!isResolved) {
                  isResolved = true;
                  clearTimeout(timeoutId);
                  cleanup();
                  resolve();
                }
              };

              cleanup = () => {
                videoElement.removeEventListener("canplay", onCanPlay);
                videoElement.removeEventListener("error", onError);
              };

              timeoutId = setTimeout(() => {
                if (!isResolved) {
                  isResolved = true;
                  cleanup();
                  reject(new Error("Video load timeout"));
                }
              }, 5000);

              videoElement.addEventListener("canplay", onCanPlay);
              videoElement.addEventListener("error", onError);

              // Draw initial frame
              if (imgElement.complete) {
                ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
              }

              // Check if already ready
              if (videoElement.readyState >= 3) {
                onCanPlay();
              } else {
                // Start playing the video to trigger canplay event
                videoElement.play().catch(onError);
              }
            });

            // Request Picture in Picture
            await videoElement.requestPictureInPicture();

            // Set state and start animation
            setIsPictureInPicture(true);
            isAnimating = true;
            updateCanvas();

            // Handle PiP events
            const handleLeavePiP = () => {
              isAnimating = false;
              setIsPictureInPicture(false);
              if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
                animationRef.current = null;
              }
              if (
                pipVideoRef.current &&
                document.body.contains(pipVideoRef.current)
              ) {
                document.body.removeChild(pipVideoRef.current);
              }
              pipVideoRef.current = null;
            };

            videoElement.addEventListener(
              "leavepictureinpicture",
              handleLeavePiP,
            );

            // Backup cleanup in case event doesn't fire
            const checkInterval = setInterval(() => {
              if (
                !document.pictureInPictureElement ||
                document.pictureInPictureElement !== videoElement
              ) {
                clearInterval(checkInterval);
                handleLeavePiP();
              }
            }, 1000);
          }
        }
      }
    } catch (error) {
      console.error("Error toggling Picture in Picture:", error);
      setIsPictureInPicture(false);
      // Cleanup on error
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      if (pipVideoRef.current && document.body.contains(pipVideoRef.current)) {
        document.body.removeChild(pipVideoRef.current);
      }
      pipVideoRef.current = null;
    }
  }, [containerRef]);

  const isPictureInPictureSupported = useCallback(
    () =>
      "pictureInPictureEnabled" in document && document.pictureInPictureEnabled,
    [],
  );

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

  useEffect(
    () => () => {
      // Cleanup PiP resources
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (pipVideoRef.current && document.body.contains(pipVideoRef.current)) {
        document.body.removeChild(pipVideoRef.current);
      }
    },
    [],
  );

  return {
    controlsVisible,
    isHovering,
    isFullscreen,
    isPictureInPicture,
    handleFullscreenToggle,
    handlePictureInPictureToggle,
    isPictureInPictureSupported: isPictureInPictureSupported(),
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleManualRecording,
    manualRecordingLoading: manualRecording.isPending,
  };
};
