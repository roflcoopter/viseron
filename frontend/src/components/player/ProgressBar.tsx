import Box from "@mui/material/Box";
import Slider from "@mui/material/Slider";
import Typography from "@mui/material/Typography";
import { RefObject, useCallback, useEffect, useRef, useState } from "react";

// Helper to format time as MM:SS or HH:MM:SS
function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

// Hook that listens to video time updates and duration changes
const useListenTimeUpdate = (
  video: HTMLVideoElement | null,
  isProgressDragging: boolean,
  setCurrentTime: React.Dispatch<React.SetStateAction<number>>,
  setDuration: React.Dispatch<React.SetStateAction<number>>,
) => {
  useEffect(() => {
    if (!video) return () => {};

    const handleTimeUpdate = () => {
      // Only update time from video when not dragging
      if (!isProgressDragging) {
        setCurrentTime(video.currentTime);
      }
    };

    const handleDurationChange = () => {
      if (Number.isFinite(video.duration)) {
        setDuration(video.duration);
      }
    };
    const handleLoadedMetadata = () => {
      if (Number.isFinite(video.duration)) {
        setDuration(video.duration);
      }
    };

    setCurrentTime(video.currentTime);
    if (Number.isFinite(video.duration)) {
      setDuration(video.duration);
    }

    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("durationchange", handleDurationChange);
    video.addEventListener("loadedmetadata", handleLoadedMetadata);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("durationchange", handleDurationChange);
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
    };
  }, [video, isProgressDragging, setCurrentTime, setDuration]);
};

// Hook to handle global mouse/touch up events to always end dragging
const useGlobalDragEnd = (
  isProgressDragging: boolean,
  handleDragEnd: () => void,
) => {
  useEffect(() => {
    if (!isProgressDragging) return () => {};

    const handleGlobalEnd = () => {
      if (isProgressDragging) {
        handleDragEnd();
      }
    };

    document.addEventListener("mouseup", handleGlobalEnd);
    document.addEventListener("touchend", handleGlobalEnd);

    return () => {
      document.removeEventListener("mouseup", handleGlobalEnd);
      document.removeEventListener("touchend", handleGlobalEnd);
    };
  }, [isProgressDragging, handleDragEnd]);
};

interface TimeProps {
  seconds: number;
}

function Time({ seconds }: TimeProps) {
  return (
    <Typography
      variant="caption"
      sx={{
        color: "white",
        textShadow: "0 1px 2px rgba(0,0,0,0.8)",
        minWidth: 40,
        textAlign: "center",
        fontSize: "0.7rem",
      }}
    >
      {formatTime(seconds)}
    </Typography>
  );
}

interface ProgressBarProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  isProgressDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
}

export function ProgressBar({
  videoRef,
  isProgressDragging,
  onDragStart,
  onDragEnd,
}: ProgressBarProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const wasPlayingRef = useRef(false);

  // Subscribe to video element time updates
  useListenTimeUpdate(
    videoRef.current,
    isProgressDragging,
    setCurrentTime,
    setDuration,
  );

  const handleProgressChange = useCallback(
    (_event: Event, newValue: number | number[]) => {
      const video = videoRef.current;
      if (video && duration > 0) {
        const seekTime = newValue as number;
        // Update local state immediately during drag
        setCurrentTime(seekTime);
        video.currentTime = seekTime;
      }
    },
    [videoRef, duration],
  );

  const handleDragStart = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      // Remember if video was playing before pausing
      wasPlayingRef.current = !video.paused;
      if (wasPlayingRef.current) {
        video.pause();
      }
    }
    onDragStart();
  }, [videoRef, onDragStart]);

  const handleDragEnd = useCallback(() => {
    const video = videoRef.current;
    if (video && wasPlayingRef.current) {
      // Resume playing if it was playing before
      video.play().catch(() => {
        // Ignore play errors
      });
      wasPlayingRef.current = false;
    }
    onDragEnd();
  }, [videoRef, onDragEnd]);

  // Global mouse/touch up handler to ensure drag end is always called
  useGlobalDragEnd(isProgressDragging, handleDragEnd);

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        gap: 0.5,
        mx: 1,
        minWidth: 0,
      }}
      onTouchStart={(e) => e.stopPropagation()}
    >
      <Time seconds={currentTime} />
      <Slider
        value={currentTime}
        onChange={handleProgressChange}
        onMouseDown={handleDragStart}
        onMouseUp={handleDragEnd}
        onTouchStart={(e) => {
          e.stopPropagation();
          handleDragStart();
        }}
        onTouchEnd={handleDragEnd}
        sx={{
          flex: 1,
          height: 4,
          "& .MuiSlider-thumb": {
            width: 12,
            height: 12,
            transition: isProgressDragging
              ? "none"
              : "left 0.2s linear, transform 0.2s linear",
          },
          // Make rail (right side if the thumb) less prominent
          "& .MuiSlider-rail": {
            opacity: 0.4,
            backgroundColor: "rgba(255,255,255,0.3)",
          },
          // Make track (left side of the thumb) smaller
          "& .MuiSlider-track": {
            border: "none",
            transition: isProgressDragging ? "none" : "width 0.2s linear",
          },
        }}
        min={0}
        max={duration}
        step={0.01}
      />
      <Time seconds={duration} />
    </Box>
  );
}
