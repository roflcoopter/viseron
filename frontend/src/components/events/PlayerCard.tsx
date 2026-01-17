import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import { useTheme } from "@mui/material/styles";
import { Suspense, lazy, useCallback, useEffect, useRef } from "react";
import screenfull from "screenfull";
import { useShallow } from "zustand/react/shallow";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { useFilteredCameras } from "components/camera/useCameraStore";
import SyncManager from "components/events/SyncManager";
import {
  LIVE_EDGE_DELAY,
  getSrc,
  useEventStore,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";
import { CustomControls } from "components/player/CustomControls";
import { PlayerGrid } from "components/player/grid/PlayerGrid";
import { useVideoControls } from "components/player/hooks/useVideoControls";
import VideoPlayerPlaceholder from "components/player/videoplayer/VideoPlayerPlaceholder";
import { useCamerasAll } from "lib/api/cameras";
import { isTouchDevice } from "lib/helpers";
import * as types from "lib/types";

const HlsPlayer = lazy(() => import("components/player/hlsplayer/HlsPlayer"));

const usePlayerCardCallbacks = (
  paperRef: React.RefObject<HTMLDivElement | null>,
) => {
  const { hlsRefs, setHlsRefsError } = useHlsStore(
    useShallow((state) => ({
      hlsRefs: state.hlsRefs,
      setHlsRefsError: state.setHlsRefsError,
    })),
  );
  const {
    isPlaying,
    setIsPlaying,
    isLive,
    isMuted,
    setIsMuted,
    playbackSpeed,
    setPlaybackSpeed,
  } = useReferencePlayerStore(
    useShallow((state) => ({
      isPlaying: state.isPlaying,
      setIsPlaying: state.setIsPlaying,
      isLive: state.isLive,
      isMuted: state.isMuted,
      setIsMuted: state.setIsMuted,
      playbackSpeed: state.playbackSpeed,
      setPlaybackSpeed: state.setPlaybackSpeed,
    })),
  );

  const {
    controlsVisible,
    isHovering,
    isFullscreen,
    setIsFullscreen,
    showControlsTemporarily,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
  } = useVideoControls();

  const togglePlayPause = useCallback(() => {
    setIsPlaying(!isPlaying);
    hlsRefs.forEach((player) => {
      if (player) {
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        isPlaying
          ? player.current?.media?.pause()
          : player.current?.media
              ?.play()
              .then(() => {
                setHlsRefsError(player, null);
              })
              .catch(() => {
                // Ignore play errors
              });
      }
    });
  }, [hlsRefs, isPlaying, setHlsRefsError, setIsPlaying]);

  const handlePlayPause = useCallback(() => {
    togglePlayPause();
    showControlsTemporarily();
  }, [showControlsTemporarily, togglePlayPause]);

  const handleJumpBackward = useCallback(() => {
    hlsRefs.forEach((player) => {
      if (player) {
        player.current!.media!.currentTime -= 10;
      }
    });
    showControlsTemporarily();
  }, [hlsRefs, showControlsTemporarily]);

  const handleJumpForward = useCallback(() => {
    hlsRefs.forEach((player) => {
      if (player) {
        player.current!.media!.currentTime += 10;
      }
    });
    showControlsTemporarily();
  }, [hlsRefs, showControlsTemporarily]);

  const handleLiveClick = useCallback(() => {
    hlsRefs.forEach((player) => {
      if (player) {
        const currentTime = player.current!.media!.duration - LIVE_EDGE_DELAY;
        if (!Number.isNaN(currentTime)) {
          player.current!.media!.currentTime =
            player.current!.media!.duration - LIVE_EDGE_DELAY;
        }
      }
    });
    showControlsTemporarily();
  }, [hlsRefs, showControlsTemporarily]);

  const handlePlaybackSpeedChange = useCallback(
    (speed: number) => {
      showControlsTemporarily();
      setPlaybackSpeed(speed);
      hlsRefs.forEach((player) => {
        if (player) {
          player.current!.media!.playbackRate = speed;
        }
      });
    },
    [hlsRefs, setPlaybackSpeed, showControlsTemporarily],
  );

  const handleVolumeChange = useCallback(
    (event: Event, newVolume: number | number[]) => {
      hlsRefs.forEach((player) => {
        if (player) {
          player.current!.media!.muted = false;
          player.current!.media!.volume = (newVolume as number) / 100;
        }
      });
      if ((newVolume as number) === 0) {
        setIsMuted(true);
      } else {
        setIsMuted(false);
      }
      showControlsTemporarily();
    },
    [hlsRefs, setIsMuted, showControlsTemporarily],
  );

  const handleMuteToggle = useCallback(() => {
    hlsRefs.forEach((player) => {
      if (player) {
        player.current!.media!.muted = !isMuted;
      }
    });
    setIsMuted(!isMuted);
    showControlsTemporarily();
  }, [hlsRefs, isMuted, setIsMuted, showControlsTemporarily]);

  const handleFullscreenToggle = useCallback(() => {
    const elem = paperRef.current;
    if (!elem) return;
    if (!isFullscreen) {
      if (screenfull.isEnabled) {
        screenfull.request(elem);
      }
    } else {
      screenfull.exit();
    }
  }, [isFullscreen, paperRef]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [setIsFullscreen]);

  return {
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleLiveClick,
    handlePlaybackSpeedChange,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isLive,
    isMuted,
    isFullscreen,
    playbackSpeed,
  };
};

export function PlayerCard() {
  const theme = useTheme();
  const paperRef: React.MutableRefObject<HTMLDivElement | null> = useRef(null);

  const camerasAll = useCamerasAll();
  const { selectedEvent } = useEventStore();

  const {
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleLiveClick,
    handlePlaybackSpeedChange,
    handleVolumeChange,
    handleMuteToggle,
    handleFullscreenToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isLive,
    isMuted,
    isFullscreen,
    playbackSpeed,
  } = usePlayerCardCallbacks(paperRef);

  const filteredCameras = useFilteredCameras();

  const { requestedTimestamp } = useReferencePlayerStore(
    useShallow((state) => ({
      requestedTimestamp: state.requestedTimestamp,
    })),
  );

  const renderPlayer = useCallback(
    (camera: types.Camera | types.FailedCamera) => (
      <Suspense
        fallback={
          <VideoPlayerPlaceholder
            aspectRatio={camera.mainstream.width / camera.mainstream.height}
          />
        }
      >
        <HlsPlayer key={camera.identifier} camera={camera} />
        <CameraNameOverlay camera_identifier={camera.identifier} />
      </Suspense>
    ),
    [],
  );

  const camera = selectedEvent
    ? camerasAll.combinedData[selectedEvent.camera_identifier]
    : null;
  const src = camera && selectedEvent ? getSrc(selectedEvent) : undefined;

  return (
    <SyncManager>
      <Paper
        ref={paperRef}
        variant="outlined"
        onMouseEnter={isTouchDevice() ? undefined : handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStart}
        sx={{
          position: "relative",
          width: "100%",
          height: "100%",
          boxSizing: "content-box",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <Box sx={{ flexGrow: 1, position: "relative" }}>
          {requestedTimestamp > 0 ? (
            <PlayerGrid
              cameras={filteredCameras}
              containerRef={paperRef}
              renderPlayer={renderPlayer}
              useDoubleColumnMobile
            />
          ) : (
            src &&
            camera && (
              <>
                <Image
                  src={src}
                  aspectRatio={camera.width / camera.height}
                  color={theme.palette.background.default}
                  animationDuration={1000}
                  imageStyle={{
                    objectFit: "contain",
                  }}
                />
                <CameraNameOverlay camera_identifier={camera.identifier} />
              </>
            )
          )}
        </Box>
        <CustomControls
          isPlaying={isPlaying}
          onPlayPause={handlePlayPause}
          onJumpBackward={handleJumpBackward}
          onJumpForward={handleJumpForward}
          isVisible={controlsVisible || isHovering}
          isLive={isLive}
          onLiveClick={handleLiveClick}
          playbackSpeed={playbackSpeed}
          onPlaybackSpeedChange={handlePlaybackSpeedChange}
          onVolumeChange={handleVolumeChange}
          isMuted={isMuted}
          onMuteToggle={handleMuteToggle}
          isFullscreen={isFullscreen}
          onFullscreenToggle={handleFullscreenToggle}
        />
      </Paper>
    </SyncManager>
  );
}
