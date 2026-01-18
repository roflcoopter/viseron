import React, { useCallback, useEffect, useState } from "react";

import { useVideoControls } from "components/player/hooks/useVideoControls";

export const useHlsPlayerControls = (
  videoRef: React.RefObject<HTMLVideoElement | null>,
) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(
    videoRef.current
      ? videoRef.current.muted || videoRef.current.volume === 0
      : false,
  );

  const {
    controlsVisible,
    isHovering,
    showControlsTemporarily,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
  } = useVideoControls();

  const togglePlayPause = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      if (video.paused) {
        video.play().catch(() => {
          // Ignore play errors
        });
      } else {
        video.pause();
      }
    }
  }, [videoRef]);

  const handlePlayPause = useCallback(() => {
    togglePlayPause();
    showControlsTemporarily();
  }, [showControlsTemporarily, togglePlayPause]);

  const handleJumpBackward = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      video.currentTime -= 10;
    }
    showControlsTemporarily();
  }, [videoRef, showControlsTemporarily]);

  const handleJumpForward = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      video.currentTime += 10;
    }
    showControlsTemporarily();
  }, [videoRef, showControlsTemporarily]);

  const handleVolumeChange = useCallback(
    (_event: Event, newVolume: number | number[]) => {
      const video = videoRef.current;
      if (video) {
        video.muted = false;
        video.volume = (newVolume as number) / 100;
      }
      setIsMuted((newVolume as number) === 0);
      showControlsTemporarily();
    },
    [videoRef, showControlsTemporarily],
  );

  const handleMuteToggle = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      video.muted = !isMuted;
    }
    setIsMuted(!isMuted);
    showControlsTemporarily();
  }, [videoRef, isMuted, showControlsTemporarily]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return () => {};

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleVolumeChangeEvent = () => setIsMuted(video.muted);

    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("volumechange", handleVolumeChangeEvent);

    return () => {
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("volumechange", handleVolumeChangeEvent);
    };
  }, [videoRef]);

  useEffect(() => {
    // setInterval that syncs isPlaying state with video element
    const playerStatusInterval = setInterval(() => {
      const video = videoRef.current;
      if (video && !video.paused !== isPlaying) {
        setIsPlaying(!video.paused);
      }
    }, 500);
    return () => {
      clearInterval(playerStatusInterval);
    };
  }, [videoRef, isPlaying]);

  return {
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
  };
};
