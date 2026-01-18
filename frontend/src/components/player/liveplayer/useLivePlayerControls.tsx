import React, { useCallback, useEffect, useState } from "react";

import { usePlayerSettingsStore } from "components/player/UsePlayerSettingsStore";
import { useVideoControls } from "components/player/hooks/useVideoControls";
import { VideoRTC } from "components/player/liveplayer/video-rtc.js";
import { useCameraManualRecording } from "lib/api/camera";
import * as types from "lib/types";

export const useLivePlayerControls = (
  playerRef: React.RefObject<VideoRTC | null>,
  camera: types.Camera | types.FailedCamera,
  onPlayerFullscreenChange?: (isFullscreen: boolean) => void,
) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPictureInPicture, setIsPictureInPicture] = useState(false);
  const manualRecording = useCameraManualRecording();

  const {
    controlsVisible,
    isHovering,
    isFullscreen,
    showControlsTemporarily,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    handleFullscreenToggle,
  } = useVideoControls({
    onFullscreenChange: onPlayerFullscreenChange,
  });

  // Get mute state from store
  const isMuted = usePlayerSettingsStore(
    (state) => state.muteMap[camera.identifier] ?? false,
  );
  const setMute = usePlayerSettingsStore((state) => state.setMute);

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
