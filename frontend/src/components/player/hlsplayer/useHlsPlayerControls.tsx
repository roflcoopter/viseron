import type Hls from "hls.js";
import React, { useCallback, useEffect, useState } from "react";

import {
  HLS_SEEK_STEP_SECONDS,
  seekHlsByOffset,
  seekMediaAndStartLoad,
} from "components/player/hlsplayer/utils";
import { useVideoControls } from "components/player/hooks/useVideoControls";

export const useHlsPlayerControls = (
  videoRef: React.RefObject<HTMLVideoElement | null>,
  hlsRef: React.MutableRefObject<Hls | null>,
) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);

  const {
    controlsVisible,
    isHovering,
    showControlsTemporarily,
    handleMouseEnter,
    handleMouseMove,
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
    const hls = hlsRef.current;
    if (hls) {
      seekHlsByOffset(hls, -HLS_SEEK_STEP_SECONDS);
    }
    showControlsTemporarily();
  }, [hlsRef, showControlsTemporarily]);

  const handleJumpForward = useCallback(() => {
    const hls = hlsRef.current;
    if (hls) {
      seekHlsByOffset(hls, HLS_SEEK_STEP_SECONDS);
    }
    showControlsTemporarily();
  }, [hlsRef, showControlsTemporarily]);

  const handleProgressSeek = useCallback(
    (mediaTime: number) => {
      const hls = hlsRef.current;
      const video = videoRef.current;
      if (hls && video) {
        seekMediaAndStartLoad(hls, video, mediaTime);
      }
    },
    [hlsRef, videoRef],
  );

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
    // setInterval that syncs isPlaying and isMuted state with video element
    const playerStatusInterval = setInterval(() => {
      const video = videoRef.current;
      if (video && !video.paused !== isPlaying) {
        setIsPlaying(!video.paused);
      }
      if (video && video.muted !== isMuted) {
        setIsMuted(video.muted);
      }
    }, 500);
    return () => {
      clearInterval(playerStatusInterval);
    };
  }, [videoRef, isPlaying, isMuted]);

  return {
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleProgressSeek,
    handleVolumeChange,
    handleMuteToggle,
    handleMouseEnter,
    handleMouseMove,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isMuted,
  };
};
