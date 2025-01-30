import Image from "@jy95/material-ui-image";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid2";
import Paper from "@mui/material/Paper";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { useShallow } from "zustand/react/shallow";

import { CameraNameOverlay } from "components/camera/CameraNameOverlay";
import { CustomControls } from "components/events/CustomControls";
import SyncManager from "components/events/SyncManager";
import { TimelinePlayer } from "components/events/timeline/TimelinePlayer";
import {
  LIVE_EDGE_DELAY,
  getSrc,
  playerCardSmMaxHeight,
  useFilteredCameras,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";
import { useResizeObserver } from "hooks/UseResizeObserver";
import { useCamerasAll } from "lib/api/cameras";
import { isTouchDevice } from "lib/helpers";
import * as types from "lib/types";

dayjs.extend(utc);

type GridLayout = {
  columns: number;
  rows: number;
};

// Dont fully understand why we need to subtract 4 from the height
// to keep the players from overflowing the paper
const getContainerHeight = (
  paperRef: React.RefObject<HTMLDivElement>,
  smBreakpoint: boolean,
) =>
  smBreakpoint
    ? paperRef.current?.clientHeight || 0
    : playerCardSmMaxHeight() -
      ((paperRef.current?.offsetHeight || 0) -
        (paperRef.current?.clientHeight || 0)) -
      4;

const calculateCellDimensions = (
  paperRef: React.RefObject<HTMLDivElement>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  const containerWidth = paperRef.current?.clientWidth || 0;
  const containerHeight = getContainerHeight(paperRef, smBreakpoint);
  const cellWidth = containerWidth / gridLayout.columns;
  const cellHeight = containerHeight / gridLayout.rows;
  const cameraAspectRatio = camera.width / camera.height;
  const cellAspectRatio = cellWidth / cellHeight;

  if (cameraAspectRatio > cellAspectRatio) {
    // Video is wider than the cell, fit to width
    const width = cellWidth;
    const height = cellWidth / cameraAspectRatio;
    return { width, height };
  }
  // Video is taller than the cell, fit to height
  const height = Math.floor(cellHeight);
  const width = Math.floor(cellHeight * cameraAspectRatio);
  return { width, height };
};

const calculateLayout = (
  paperRef: React.RefObject<HTMLDivElement>,
  cameras: types.CamerasOrFailedCameras,
  smBreakpoint: boolean,
) => {
  if (!paperRef.current) return { columns: 1, rows: 1 };

  const containerWidth = paperRef.current.clientWidth;
  const containerHeight = getContainerHeight(paperRef, smBreakpoint);
  const camerasLength = Object.keys(cameras).length;

  let bestLayout = { columns: 1, rows: 1 };
  let maxMinDimension = 0;

  for (let columns = 1; columns <= camerasLength; columns++) {
    const rows = Math.ceil(camerasLength / columns);
    const cellWidth = containerWidth / columns;
    const cellHeight = containerHeight / rows;

    // Calculate the minimum dimension (width or height) of any camera in this layout
    let minDimension = Math.min(cellWidth, cellHeight);

    // Adjust for aspect ratio
    Object.values(cameras).forEach((camera) => {
      const aspectRatio = camera.width / camera.height;
      const adjustedWidth = Math.min(cellWidth, cellHeight * aspectRatio);
      const adjustedHeight = Math.min(cellHeight, cellWidth / aspectRatio);
      minDimension = Math.min(minDimension, adjustedWidth, adjustedHeight);
    });

    // If this layout results in larger minimum dimensions, it's our new best layout
    if (minDimension > maxMinDimension) {
      maxMinDimension = minDimension;
      bestLayout = { columns, rows };
    }

    // If adding more columns would make cells smaller than they need to be, stop here
    if (cellWidth < minDimension) {
      break;
    }
  }

  return bestLayout;
};

const useGridLayout = (
  paperRef: React.RefObject<HTMLDivElement>,
  cameras: types.CamerasOrFailedCameras,
  setPlayerItemsSize: () => void,
) => {
  const theme = useTheme();
  const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
  const [gridLayout, setGridLayout] = useState<{
    columns: number;
    rows: number;
  }>({ columns: 1, rows: 1 });

  const handleResize = useCallback(() => {
    const layout = calculateLayout(paperRef, cameras, smBreakpoint);
    if (
      layout.columns !== gridLayout.columns ||
      layout.rows !== gridLayout.rows
    ) {
      setGridLayout(layout);
    }
    setPlayerItemsSize();
  }, [
    cameras,
    gridLayout.columns,
    gridLayout.rows,
    setPlayerItemsSize,
    paperRef,
    smBreakpoint,
  ]);

  // Observe both the paperRef and window resize to update the layout
  useResizeObserver(paperRef, handleResize);
  useEffect(() => {
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [handleResize]);

  return gridLayout;
};

const setPlayerSize = (
  paperRef: React.RefObject<HTMLDivElement>,
  boxRef: React.RefObject<HTMLDivElement>,
  camera: types.Camera | types.FailedCamera,
  gridLayout: GridLayout,
  smBreakpoint: boolean,
) => {
  if (paperRef.current && boxRef.current) {
    const { width, height } = calculateCellDimensions(
      paperRef,
      camera,
      gridLayout,
      smBreakpoint,
    );
    boxRef.current.style.width = `${width}px`;
    boxRef.current.style.height = `${height}px`;
  }
};

const usePlayerCardCallbacks = () => {
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
  const [controlsVisible, setControlsVisible] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showControlsTemporarily = useCallback(() => {
    setControlsVisible(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setControlsVisible(false);
    }, 3000); // Hide controls after 3 seconds
  }, []);

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
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleLiveClick,
    handlePlaybackSpeedChange,
    handleVolumeChange,
    handleMuteToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isLive,
    isMuted,
    playbackSpeed,
  };
};

interface PlayerItemRef {
  setSize: () => void;
}

type PlayerItemProps = {
  camera: types.Camera | types.FailedCamera;
  paperRef: React.RefObject<HTMLDivElement>;
  gridLayout: GridLayout;
};
const PlayerItem = forwardRef<PlayerItemRef, PlayerItemProps>(
  ({ camera, paperRef, gridLayout }, ref) => {
    const theme = useTheme();
    const smBreakpoint = useMediaQuery(theme.breakpoints.up("sm"));
    const boxRef = useRef<HTMLDivElement>(null);

    useImperativeHandle(ref, () => ({
      // PlayerCard will call this function to set the size of the player.
      // Done this way since the player size depends on the size of the parent
      // which is not known until the parent has been rendered
      setSize: () => {
        setPlayerSize(paperRef, boxRef, camera, gridLayout, smBreakpoint);
      },
    }));

    return (
      <Grid
        key={camera.identifier}
        sx={{
          flexBasis: "min-content",
        }}
        size={12 / gridLayout.columns}
      >
        <Box
          ref={boxRef}
          sx={{
            position: "relative",
          }}
        >
          <TimelinePlayer key={camera.identifier} camera={camera} />
          <CameraNameOverlay camera_identifier={camera.identifier} />
        </Box>
      </Grid>
    );
  },
);

type PlayerGridProps = {
  cameras: types.CamerasOrFailedCameras;
  paperRef: React.RefObject<HTMLDivElement>;
  setPlayerItemRef: (index: number) => (ref: PlayerItemRef | null) => void;
  gridLayout: GridLayout;
};
const PlayerGrid = ({
  cameras,
  paperRef,
  setPlayerItemRef,
  gridLayout,
}: PlayerGridProps) => (
  <Grid
    container
    spacing={0}
    sx={{ height: "100%" }}
    alignContent="center"
    justifyContent="center"
  >
    {Object.values(cameras).map((camera, index) => (
      <PlayerItem
        ref={setPlayerItemRef(index)}
        key={camera.identifier}
        camera={camera}
        paperRef={paperRef}
        gridLayout={gridLayout}
      />
    ))}
  </Grid>
);

type PlayerCardProps = {
  selectedEvent: types.CameraEvent | null;
  selectedTab: "events" | "timeline";
};
export const PlayerCard = ({ selectedEvent }: PlayerCardProps) => {
  const theme = useTheme();
  const paperRef: React.MutableRefObject<HTMLDivElement | null> = useRef(null);
  const playerItemRefs = useRef<(PlayerItemRef | null)[]>([]);
  const setPlayerItemRef = (index: number) => (ref: PlayerItemRef | null) => {
    playerItemRefs.current[index] = ref;
  };

  const camerasAll = useCamerasAll();

  const {
    handlePlayPause,
    handleJumpBackward,
    handleJumpForward,
    handleLiveClick,
    handlePlaybackSpeedChange,
    handleVolumeChange,
    handleMuteToggle,
    handleMouseEnter,
    handleMouseLeave,
    handleTouchStart,
    controlsVisible,
    isHovering,
    isPlaying,
    isLive,
    isMuted,
    playbackSpeed,
  } = usePlayerCardCallbacks();

  const setPlayerItemsSize = useCallback(() => {
    playerItemRefs.current.forEach((playerItemRef) => {
      if (playerItemRef) {
        playerItemRef.setSize();
      }
    });
  }, []);

  const filteredCameras = useFilteredCameras();
  const gridLayout = useGridLayout(
    paperRef,
    filteredCameras,
    setPlayerItemsSize,
  );

  const { requestedTimestamp } = useReferencePlayerStore(
    useShallow((state) => ({
      requestedTimestamp: state.requestedTimestamp,
    })),
  );

  const camera = selectedEvent
    ? camerasAll.combinedData[selectedEvent.camera_identifier]
    : null;
  const src = camera && selectedEvent ? getSrc(selectedEvent) : undefined;

  return (
    <SyncManager>
      <Paper
        ref={(node) => {
          paperRef.current = node;
          setPlayerItemsSize();
        }}
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
              paperRef={paperRef}
              setPlayerItemRef={setPlayerItemRef}
              gridLayout={gridLayout}
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
        />
      </Paper>
    </SyncManager>
  );
};
