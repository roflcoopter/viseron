import {
  VideoAdd,
  Maximize,
  Minimize,
  Grid
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Fab from "@mui/material/Fab";
import Menu from "@mui/material/Menu";
import Paper from "@mui/material/Paper";
import Tooltip from "@mui/material/Tooltip";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useTheme } from "@mui/material/styles";
import {
  createContext,
  memo,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import { useShallow } from "zustand/react/shallow";

import { CameraPickerDialog } from "components/camera/CameraPickerDialog";
import {
  useCameraStore,
  useFilteredCameras,
} from "components/camera/useCameraStore";
import { Loading } from "components/loading/Loading";
import { PlayerMenu, PlayerMenuItems } from "components/player/PlayerMenu";
import { usePlayerSettingsStore } from "components/player/UsePlayerSettingsStore";
import { PlayerGrid } from "components/player/grid/PlayerGrid";
import CustomGridLayout from "components/player/grid/CustomGridLayout";
import { GridLayoutSelectorDialog } from "components/player/grid/GridLayoutSelectorDialog";
import { LivePlayer } from "components/player/liveplayer/LivePlayer";
import { VideoRTC } from "components/player/liveplayer/video-rtc";
import { MjpegPlayer } from "components/player/mjpegplayer/MjpegPlayer";
import { ViewSpeedDial } from "components/player/view/ViewSpeedDial";
import { useFullscreen } from "context/FullscreenContext";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import { objHasValues, removeURLParameter } from "lib/helpers";
import { useGridLayoutStore } from "stores/GridLayoutStore";
import * as types from "lib/types";

// Context for managing menu state across players
interface MenuContextType {
  openMenu: (
    camera: types.Camera | types.FailedCamera,
    anchorEl: HTMLElement,
  ) => void;
  closeMenu: () => void;
  isMenuOpenForCamera: (camera: types.Camera | types.FailedCamera) => boolean;
  setPlayerFullscreen: (isPlayerFullscreen: boolean) => void;
}

const MenuContext = createContext<MenuContextType | null>(null);
function MenuProvider({ children }: { children: React.ReactNode }) {
  const { isFullscreen } = useFullscreen();
  const [isPlayerFullscreen, setPlayerFullscreen] = useState(false);
  const [menuState, setMenuState] = useState<{
    open: boolean;
    camera: types.Camera | types.FailedCamera | null;
    anchorEl: HTMLElement | null;
  }>({
    open: false,
    camera: null,
    anchorEl: null,
  });

  const openMenu = useCallback(
    (camera: types.Camera | types.FailedCamera, anchorEl: HTMLElement) => {
      setMenuState({ open: true, camera, anchorEl });
    },
    [],
  );

  const closeMenu = useCallback(() => {
    setMenuState({ open: false, camera: null, anchorEl: null });
  }, []);

  const isMenuOpenForCamera = useCallback(
    (camera: types.Camera | types.FailedCamera) =>
      menuState.open && menuState.camera?.identifier === camera.identifier,
    [menuState.open, menuState.camera],
  );

  const contextValue = useMemo(
    () => ({ openMenu, closeMenu, isMenuOpenForCamera, setPlayerFullscreen }),
    [openMenu, closeMenu, isMenuOpenForCamera, setPlayerFullscreen],
  );

  return (
    <MenuContext.Provider value={contextValue}>
      {children}
      {menuState.open && menuState.camera && (
        <Menu
          anchorEl={menuState.anchorEl}
          open={menuState.open}
          onClose={closeMenu}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
          disablePortal={false}
          container={() => document.body}
          slotProps={{ 
            paper: { 
              sx: { 
                minWidth: 220,
                zIndex: isFullscreen ? 9004 : (isPlayerFullscreen ? 8100 : 1001)
              } 
            } 
          }}
          BackdropProps={{
            style: { zIndex: isFullscreen ? 9003 : (isPlayerFullscreen ? 8099 : 1000) }
          }}
          style={{ zIndex: isFullscreen ? 9004 : (isPlayerFullscreen ? 8100 : 1001) }}
        >
          <PlayerMenuItems camera={menuState.camera} />
        </Menu>
      )}
    </MenuContext.Provider>
  );
}

export const FloatingMenu = memo(({ containerRef, isFullscreen }: { containerRef: React.RefObject<HTMLDivElement | null>; isFullscreen: boolean }) => {
  const [cameraDialogOpen, setCameraDialogOpen] = useState(false);
  const [gridLayoutDialogOpen, setGridLayoutDialogOpen] = useState(false);
  const { toggleFullscreen } = useFullscreen();
  const cameras = useCameras({});
  const menuBoxRef = useRef<HTMLDivElement>(null);
  
  // State for auto-hide functionality - reset when isFullscreen prop changes
  const [hideState, setHideState] = useState({ shouldHide: false, fullscreenKey: isFullscreen });
  
  // Auto-reset state when fullscreen changes (derived state pattern)
  const currentShouldHide = hideState.fullscreenKey !== isFullscreen ? false : hideState.shouldHide;
  
  // Update state if fullscreen key is stale
  if (hideState.fullscreenKey !== isFullscreen) {
    setHideState({ shouldHide: false, fullscreenKey: isFullscreen });
  }
  
  // Calculate final visibility
  const isMenuVisible = !isFullscreen || !currentShouldHide;

  const handleFullscreenToggle = useCallback(async () => {
    if (containerRef.current) {
      await toggleFullscreen(containerRef.current);
    }
  }, [toggleFullscreen, containerRef]);

  // Auto-hide functionality for fullscreen mode
  useEffect(() => {
    if (!isFullscreen) {
      return undefined;
    }

    let hideTimeout: NodeJS.Timeout;
    const containerElement = containerRef.current;

    const handleMouseMove = (event: MouseEvent) => {
      if (!menuBoxRef.current) return;

      const rect = menuBoxRef.current.getBoundingClientRect();
      const buffer = 50; // Additional area around the menu box
      
      const isNearMenu = event.clientX >= rect.left - buffer &&
                        event.clientX <= rect.right + buffer &&
                        event.clientY >= rect.top - buffer &&
                        event.clientY <= rect.bottom + buffer;

      if (isNearMenu) {
        setHideState(prev => ({ ...prev, shouldHide: false }));
        clearTimeout(hideTimeout);
      } else {
        clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => {
          setHideState(prev => ({ ...prev, shouldHide: true }));
        }, 2000); // Hide after 2 seconds of no mouse activity near menu
      }
    };

    const handleMouseLeave = () => {
      clearTimeout(hideTimeout);
      hideTimeout = setTimeout(() => {
        setHideState(prev => ({ ...prev, shouldHide: true }));
      }, 1000); // Hide after 1 second when mouse leaves the container
    };

    // Show menu initially for 3 seconds when entering fullscreen
    hideTimeout = setTimeout(() => {
      setHideState(prev => ({ ...prev, shouldHide: true }));
    }, 3000);

    document.addEventListener('mousemove', handleMouseMove);
    if (containerElement) {
      containerElement.addEventListener('mouseleave', handleMouseLeave);
    }

    return () => {
      clearTimeout(hideTimeout);
      document.removeEventListener('mousemove', handleMouseMove);
      if (containerElement) {
        containerElement.removeEventListener('mouseleave', handleMouseLeave);
      }
    };
  }, [isFullscreen, containerRef]);

  return (
    <>
      <CameraPickerDialog
        open={cameraDialogOpen}
        setOpen={setCameraDialogOpen}
      />
      <GridLayoutSelectorDialog
        open={gridLayoutDialogOpen}
        onClose={() => setGridLayoutDialogOpen(false)}
        cameras={cameras.data || {}}
      />
      <Box 
        ref={menuBoxRef}
        sx={{ 
          position: "absolute", 
          bottom: 10, 
          left: isFullscreen ? 11 : 23, 
          zIndex: 1000,
          opacity: isFullscreen && !isMenuVisible ? 0 : 1,
          transition: 'opacity 0.3s ease-in-out',
          pointerEvents: isFullscreen && !isMenuVisible ? 'none' : 'auto'
        }}
      >
        <Tooltip 
          title="Select Cameras"
          PopperProps={{
            style: { zIndex: isFullscreen ? 9003 : 999 }
          }}
        >
          <Fab
            size="small"
            color="primary"
            onClick={() => setCameraDialogOpen(true)}
            sx={{ mr: 1 }}
          >
            <VideoAdd size={20}/>
          </Fab>
        </Tooltip>
        <Tooltip 
          title="Grid Layout"
          PopperProps={{
            style: { zIndex: isFullscreen ? 9003 : 999 }
          }}
        >
          <Fab
            size="small"
            color="primary"
            onClick={() => setGridLayoutDialogOpen(true)}
            sx={{ mr: 1 }}
          >
            <Grid size={20}/>
          </Fab>
        </Tooltip>
        <Tooltip 
          title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
          PopperProps={{
            style: { zIndex: isFullscreen ? 9003 : 999 }
          }}
        >
          <Fab
            size="small"
            color="primary"
            onClick={handleFullscreenToggle}
          >
            {isFullscreen ? <Minimize size={20}/> : <Maximize size={20}/>}
          </Fab>
        </Tooltip>
        <Box sx={{ display: 'inline-block', verticalAlign: 'bottom'}}>
          <ViewSpeedDial inline size="small" />
        </Box>
      </Box>
    </>
  );
});

const CameraPlayer = memo(
  ({
    camera,
    playerRef,
  }: {
    camera: types.Camera | types.FailedCamera;
    playerRef: React.RefObject<VideoRTC | null>;
  }) => {
    const theme = useTheme();
    const menuContext = useContext(MenuContext);

    const handleMenuOpen = useCallback(
      (event: React.MouseEvent<HTMLElement>) => {
        if (menuContext) {
          menuContext.openMenu(camera, event.currentTarget as HTMLElement);
        }
      },
      [camera, menuContext],
    );

    const handlePlayerFullscreenChange = useCallback(
      (isFullscreen: boolean) => {
        menuContext?.setPlayerFullscreen(isFullscreen);
      },
      [menuContext],
    );

    const isMenuOpen = menuContext?.isMenuOpenForCamera(camera) ?? false;

    const {
      mjpegPlayer,
      drawObjects,
      drawMotion,
      drawObjectMask,
      drawMotionMask,
      drawZones,
      drawPostProcessorMask,
    } = usePlayerSettingsStore(
      useShallow((state) => ({
        // mjpegPlayer defaults to true if live_stream_available is false, otherwise true
        mjpegPlayer: !camera.live_stream_available
          ? true
          : (state.mjpegPlayerMap[camera.identifier] ?? false),
        drawObjects: state.drawObjectsMap[camera.identifier] ?? false,
        drawMotion: state.drawMotionMap[camera.identifier] ?? false,
        drawObjectMask: state.drawObjectMaskMap[camera.identifier] ?? false,
        drawMotionMask: state.drawMotionMaskMap[camera.identifier] ?? false,
        drawZones: state.drawZonesMap[camera.identifier] ?? false,
        drawPostProcessorMask:
          state.drawPostProcessorMaskMap[camera.identifier] ?? false,
      })),
    );

    const playerMenuButton = useMemo(
      () => <PlayerMenu onMenuOpen={handleMenuOpen} />,
      [handleMenuOpen],
    );

    return mjpegPlayer ? (
      <MjpegPlayer
        camera={camera}
        src={`/${camera.identifier}/mjpeg-stream`}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          backgroundColor: theme.palette.background.default,
        }}
        drawObjects={drawObjects}
        drawMotion={drawMotion}
        drawObjectMask={drawObjectMask}
        drawMotionMask={drawMotionMask}
        drawZones={drawZones}
        drawPostProcessorMask={drawPostProcessorMask}
        isMenuOpen={isMenuOpen}
        extraButtons={playerMenuButton}
        onPlayerFullscreenChange={handlePlayerFullscreenChange}
      />
    ) : (
      <LivePlayer
        playerRef={playerRef}
        camera={camera}
        src={`/live?src=${camera.identifier}`}
        controls={false}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          backgroundColor: theme.palette.background.default,
        }}
        isMenuOpen={isMenuOpen}
        extraButtons={playerMenuButton}
        onPlayerFullscreenChange={handlePlayerFullscreenChange}
      />
    );
  },
);

export function PlayerCard() {
  const { currentLayout } = useGridLayoutStore();
  const theme = useTheme();
  const isMobileOrSmall = useMediaQuery(theme.breakpoints.down('md'));
  const paperRef: React.MutableRefObject<HTMLDivElement | null> = useRef(null);

  const renderPlayer = useCallback(
    (
      camera: types.Camera | types.FailedCamera,
      playerRef: React.RefObject<VideoRTC | null>,
    ) => <CameraPlayer camera={camera} playerRef={playerRef} />,
    [],
  );

  const filteredCameras = useFilteredCameras();

  // Use auto layout if:
  // 1. Current layout is 'auto', OR
  // 2. Device is mobile/small (below md breakpoint)
  const shouldUseAutoLayout = currentLayout === 'auto' || isMobileOrSmall;

  return (
    <Paper
      ref={paperRef}
      variant="outlined"
      sx={{
        width: "100%",
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        maxHeight: "100%",
      }}
    >
      <Box sx={{ flexGrow: 1, position: "relative", overflow: "hidden", maxHeight: "100%" }}>
        {shouldUseAutoLayout ? (
          <PlayerGrid
            cameras={filteredCameras as types.Cameras}
            containerRef={paperRef}
            renderPlayer={renderPlayer}
            forceBreakpoint
          />
        ) : (
          <CustomGridLayout
            cameras={filteredCameras as types.Cameras}
            containerRef={paperRef}
            renderPlayer={renderPlayer}
          />
        )}
      </Box>
    </Paper>
  );
}

function Live() {
  useTitle("Live");
  const theme = useTheme();
  const [searchParams] = useSearchParams();
  const { selectSingleCamera } = useCameraStore();
  const { resetLayout } = useGridLayoutStore();
  const { isFullscreen } = useFullscreen();
  const cameras = useCameras({});
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (
      cameras.data &&
      objHasValues(cameras.data) &&
      searchParams.has("camera")
    ) {
      const cameraId = searchParams.get("camera") as string;
      if (cameras.data[cameraId]) {
        // Reset grid layout store to auto when camera query is present
        resetLayout();
        
        selectSingleCamera(cameras.data[cameraId].identifier);
        searchParams.delete("camera");
        const newUrl = removeURLParameter(window.location.href, "camera");
        window.history.pushState({ path: newUrl }, "", newUrl);
      }
    }
  }, [cameras, searchParams, selectSingleCamera, resetLayout]);

  if (cameras.isPending) {
    return <Loading text="Loading Cameras" />;
  }

  if (!objHasValues<typeof cameras.data>(cameras.data)) {
    return <Loading text="Waiting for cameras to register" />;
  }

  return (
    <MenuProvider>
      <Container 
        maxWidth={false} 
        ref={containerRef} 
        sx={{ 
          paddingX: isFullscreen ? 0 : 2,
          height: isFullscreen ? '100vh' : `calc(100dvh - ${theme.headerHeight}px - ${theme.headerMargin})`,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          maxHeight: isFullscreen ? '100vh' : `calc(100dvh - ${theme.headerHeight}px - ${theme.headerMargin})`,
        }}
      >
        <PlayerCard />
        <FloatingMenu containerRef={containerRef} isFullscreen={isFullscreen} />
      </Container>
    </MenuProvider>
  );
}

export default Live;
