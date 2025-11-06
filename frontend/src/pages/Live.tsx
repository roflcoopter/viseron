import {
  VideoAdd,
  Maximize,
  Minimize,
  Grid,
  CenterSquare,
  ChevronRight,
  ArrowsVertical,
  Compare
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Fab from "@mui/material/Fab";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ListItemText from "@mui/material/ListItemText";
import ListItemIcon from "@mui/material/ListItemIcon";
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
  createRef,
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
import { BASE_PATH } from "lib/api/client";
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
  openContextMenu: (
    camera: types.Camera | types.FailedCamera,
    event: React.MouseEvent,
  ) => void;
  closeContextMenu: () => void;
}

const MenuContext = createContext<MenuContextType | null>(null);
function MenuProvider({ children }: { children: React.ReactNode }) {
  const { isFullscreen } = useFullscreen();
  const [isPlayerFullscreen, setPlayerFullscreen] = useState(false);
  const { swapCameraPositions } = useCameraStore();
  const { currentLayout, layoutConfig, setMainSlot } = useGridLayoutStore();
  const { setFlipView } = usePlayerSettingsStore(
    useShallow((state) => ({
      setFlipView: state.setFlipView,
    })),
  );
  const filteredCameras = useFilteredCameras();
  const [menuState, setMenuState] = useState<{
    open: boolean;
    camera: types.Camera | types.FailedCamera | null;
    anchorEl: HTMLElement | null;
  }>({
    open: false,
    camera: null,
    anchorEl: null,
  });

  const [contextMenuState, setContextMenuState] = useState<{
    open: boolean;
    camera: types.Camera | types.FailedCamera | null;
    anchorEl: HTMLElement | null;
    mouseX: number;
    mouseY: number;
  }>({
    open: false,
    camera: null,
    anchorEl: null,
    mouseX: 0,
    mouseY: 0,
  });

  const [slotMenuState, setSlotMenuState] = useState<{
    open: boolean;
    anchorEl: HTMLElement | null;
  }>({
    open: false,
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

  const openContextMenu = useCallback(
    (camera: types.Camera | types.FailedCamera, event: React.MouseEvent) => {
      event.preventDefault();
      setContextMenuState({
        open: true,
        camera,
        anchorEl: null,
        mouseX: event.clientX - 2,
        mouseY: event.clientY - 4,
      });
    },
    [],
  );

  const closeContextMenu = useCallback(() => {
    setContextMenuState({
      open: false,
      camera: null,
      anchorEl: null,
      mouseX: 0,
      mouseY: 0,
    });
    setSlotMenuState({
      open: false,
      anchorEl: null,
    });
  }, []);

  const handleSlotMenuOpen = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      setSlotMenuState({
        open: true,
        anchorEl: event.currentTarget,
      });
    },
    [],
  );

  const handleSlotMenuClose = useCallback(() => {
    setSlotMenuState({
      open: false,
      anchorEl: null,
    });
  }, []);

  const handleSetAsMain = useCallback(() => {
    if (contextMenuState.camera && currentLayout !== 'auto') {
      setMainSlot(contextMenuState.camera.identifier);
    }
    closeContextMenu();
  }, [contextMenuState.camera, currentLayout, setMainSlot, closeContextMenu]);

  const handleFlipView = useCallback(() => {
    if (contextMenuState.camera) {
      // Get current flip state and toggle it
      const currentFlipState = usePlayerSettingsStore.getState().flipViewMap[contextMenuState.camera.identifier] ?? false;
      setFlipView(contextMenuState.camera.identifier, !currentFlipState);
    }
    closeContextMenu();
  }, [contextMenuState.camera, setFlipView, closeContextMenu]);

  const handleSlotChange = useCallback(
    (targetCamera: types.Camera | types.FailedCamera) => {
      if (contextMenuState.camera && targetCamera) {
        const sourceId = contextMenuState.camera.identifier;
        const targetId = targetCamera.identifier;
        
        // Swap camera positions using the store function
        swapCameraPositions(sourceId, targetId);
        
        // If we're using a custom grid layout, update mainSlot if needed
        if (currentLayout !== 'auto' && layoutConfig.mainSlot) {
          if (layoutConfig.mainSlot === sourceId) {
            // If the main slot camera is being swapped, update mainSlot to target
            setMainSlot(targetId);
          } else if (layoutConfig.mainSlot === targetId) {
            // If target was the main slot, update mainSlot to source
            setMainSlot(sourceId);
          }
        }
      }
      closeContextMenu();
    },
    [contextMenuState.camera, swapCameraPositions, closeContextMenu, currentLayout, layoutConfig.mainSlot, setMainSlot],
  );

  const isMenuOpenForCamera = useCallback(
    (camera: types.Camera | types.FailedCamera) =>
      menuState.open && menuState.camera?.identifier === camera.identifier,
    [menuState.open, menuState.camera],
  );

  const contextValue = useMemo(
    () => ({ 
      openMenu, 
      closeMenu, 
      isMenuOpenForCamera, 
      setPlayerFullscreen,
      openContextMenu,
      closeContextMenu,
    }),
    [openMenu, closeMenu, isMenuOpenForCamera, setPlayerFullscreen, openContextMenu, closeContextMenu],
  );

  // Add global right-click listener to close context menu when right-clicking elsewhere
  useEffect(() => {
    const handleGlobalContextMenu = (event: MouseEvent) => {
      if (contextMenuState.open) {
        // Check if the right-click is outside any camera player
        const target = event.target as Element;
        const isInsideCameraPlayer = target?.closest('[data-camera-player]');
        
        if (!isInsideCameraPlayer) {
          closeContextMenu();
          // Allow default browser context menu only if our context menu was open
          // and the click was outside camera players
        }
      }
    };

    const handleGlobalClick = (event: MouseEvent) => {
      if (contextMenuState.open || slotMenuState.open) {
        // Check if click is outside the menu elements
        const target = event.target as Element;
        const isInsideMenu = target?.closest('[role="menu"]') || target?.closest('[data-camera-player]');
        
        if (!isInsideMenu) {
          closeContextMenu();
        }
      }
    };

    document.addEventListener('contextmenu', handleGlobalContextMenu);
    document.addEventListener('click', handleGlobalClick);
    
    return () => {
      document.removeEventListener('contextmenu', handleGlobalContextMenu);
      document.removeEventListener('click', handleGlobalClick);
    };
  }, [contextMenuState.open, slotMenuState.open, closeContextMenu]);

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
      {contextMenuState.open && contextMenuState.camera && (
        <Menu
          open={contextMenuState.open}
          onClose={closeContextMenu}
          anchorReference="anchorPosition"
          anchorPosition={
            contextMenuState.mouseY !== null && contextMenuState.mouseX !== null
              ? { top: contextMenuState.mouseY, left: contextMenuState.mouseX }
              : undefined
          }
          disablePortal={false}
          container={() => document.body}
          slotProps={{ 
            paper: { 
              sx: { 
                minWidth: 200,
                zIndex: isFullscreen ? 9004 : (isPlayerFullscreen ? 8100 : 1001)
              } 
            } 
          }}
          BackdropProps={{
            style: { zIndex: isFullscreen ? 9003 : (isPlayerFullscreen ? 8099 : 1000) }
          }}
          style={{ zIndex: isFullscreen ? 9004 : (isPlayerFullscreen ? 8100 : 1001) }}
        >
          <MenuItem 
            onClick={handleSlotMenuOpen}
            disabled={Object.values(filteredCameras).length <= 1}
          >
            <ListItemIcon sx={{ minWidth: 'auto'}}>
              <Compare size={16} />
            </ListItemIcon>
            <ListItemText primary="Change Slot" />
            <ListItemIcon sx={{ minWidth: 'auto', ml: 1 }}>
              <ChevronRight size={16} />
            </ListItemIcon>
          </MenuItem>
          {currentLayout !== 'auto' && (
            <MenuItem 
              onClick={handleSetAsMain}
              disabled={layoutConfig.mainSlot === contextMenuState.camera?.identifier}
            >
              <ListItemIcon sx={{ minWidth: 'auto'}}>
                <CenterSquare size={16} />
              </ListItemIcon>
              <ListItemText 
                primary="Set as Main Camera" 
                secondary={layoutConfig.mainSlot === contextMenuState.camera?.identifier ? "Already main camera" : undefined}
              />
            </MenuItem>
          )}
          <MenuItem onClick={handleFlipView}>
            <ListItemIcon sx={{ minWidth: 'auto'}}>
              <ArrowsVertical size={16} />
            </ListItemIcon>
            <ListItemText primary="Flip View 180°" />
          </MenuItem>
        </Menu>
      )}
      {slotMenuState.open && contextMenuState.camera && (
        <Menu
          open={slotMenuState.open}
          onClose={handleSlotMenuClose}
          anchorEl={slotMenuState.anchorEl}
          anchorOrigin={{ vertical: "top", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "left" }}
          disablePortal={false}
          container={() => document.body}
          slotProps={{ 
            paper: { 
              sx: { 
                minWidth: 180,
                zIndex: isFullscreen ? 9005 : (isPlayerFullscreen ? 8101 : 1002)
              } 
            } 
          }}
          BackdropProps={{
            style: { zIndex: isFullscreen ? 9004 : (isPlayerFullscreen ? 8100 : 1001) }
          }}
          style={{ zIndex: isFullscreen ? 9005 : (isPlayerFullscreen ? 8101 : 1002) }}
        >
          {Object.values(filteredCameras)
            .filter(camera => camera.identifier !== contextMenuState.camera?.identifier)
            .map((camera) => (
              <MenuItem
                key={camera.identifier}
                onClick={() => handleSlotChange(camera)}
              >
                <ListItemText primary={`${camera.name}`} />
              </MenuItem>
            ))}
          {Object.values(filteredCameras).length <= 1 && (
            <MenuItem disabled>
              <ListItemText 
                primary="No other cameras available" 
                secondary="Add more cameras to enable slot swapping"
              />
            </MenuItem>
          )}
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
        aria-hidden={isFullscreen && !isMenuVisible}
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

    // Ensure we always have a valid ref - but don't use a stale fallback
    const safePlayerRef = useMemo(() => playerRef || createRef<VideoRTC>(), [playerRef]);

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

    const handleContextMenu = useCallback(
      (event: React.MouseEvent) => {
        if (menuContext) {
          menuContext.openContextMenu(camera, event);
        }
      },
      [camera, menuContext],
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
      flipView,
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
        flipView: state.flipViewMap[camera.identifier] ?? false,
      })),
    );

    const playerMenuButton = useMemo(
      () => <PlayerMenu onMenuOpen={handleMenuOpen} />,
      [handleMenuOpen],
    );

    return mjpegPlayer ? (
      <div 
        onContextMenu={handleContextMenu} 
        style={{ 
          width: "100%", 
          height: "100%"
        }}
        data-camera-player={camera.identifier}
      >
        <MjpegPlayer
          camera={camera}
          src={`${BASE_PATH}/${camera.identifier}/mjpeg-stream`}
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
          flipView={flipView}
          isMenuOpen={isMenuOpen}
          extraButtons={playerMenuButton}
          onPlayerFullscreenChange={handlePlayerFullscreenChange}
        />
      </div>
    ) : (
      <div 
        onContextMenu={handleContextMenu} 
        style={{ 
          width: "100%", 
          height: "100%"
        }}
        data-camera-player={camera.identifier}
      >
        <LivePlayer
          playerRef={safePlayerRef}
          camera={camera}
          src={`${BASE_PATH}/live?src=${camera.identifier}`}
          controls={false}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            backgroundColor: theme.palette.background.default,
          }}
          flipView={flipView}
          isMenuOpen={isMenuOpen}
          extraButtons={playerMenuButton}
          onPlayerFullscreenChange={handlePlayerFullscreenChange}
        />
      </div>
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
