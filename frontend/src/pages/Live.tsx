import VideocamIcon from "@mui/icons-material/Videocam";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Fab from "@mui/material/Fab";
import Menu from "@mui/material/Menu";
import Paper from "@mui/material/Paper";
import Tooltip from "@mui/material/Tooltip";
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
import { LivePlayer } from "components/player/liveplayer/LivePlayer";
import { VideoRTC } from "components/player/liveplayer/video-rtc";
import { MjpegPlayer } from "components/player/mjpegplayer/MjpegPlayer";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import { objHasValues, removeURLParameter } from "lib/helpers";
import * as types from "lib/types";

// Context for managing menu state across players
interface MenuContextType {
  openMenu: (
    camera: types.Camera | types.FailedCamera,
    anchorEl: HTMLElement,
  ) => void;
  closeMenu: () => void;
  isMenuOpenForCamera: (camera: types.Camera | types.FailedCamera) => boolean;
}

const MenuContext = createContext<MenuContextType | null>(null);
const MenuProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
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
    () => ({ openMenu, closeMenu, isMenuOpenForCamera }),
    [openMenu, closeMenu, isMenuOpenForCamera],
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
          slotProps={{ paper: { sx: { minWidth: 220 } } }}
        >
          <PlayerMenuItems camera={menuState.camera} />
        </Menu>
      )}
    </MenuContext.Provider>
  );
};

export const FloatingMenu = memo(() => {
  const [cameraDialogOpen, setCameraDialogOpen] = useState(false);

  return (
    <>
      <CameraPickerDialog
        open={cameraDialogOpen}
        setOpen={setCameraDialogOpen}
      />
      <Box sx={{ position: "absolute", bottom: 10, left: 14 }}>
        <Tooltip title="Select Cameras">
          <Fab
            size="small"
            color="primary"
            onClick={() => setCameraDialogOpen(true)}
          >
            <VideocamIcon />
          </Fab>
        </Tooltip>
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
    playerRef: React.RefObject<VideoRTC>;
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
      () => <PlayerMenu camera={camera} onMenuOpen={handleMenuOpen} />,
      [camera, handleMenuOpen],
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
      />
    );
  },
);

export const PlayerCard = () => {
  const theme = useTheme();
  const paperRef: React.MutableRefObject<HTMLDivElement | null> = useRef(null);

  const renderPlayer = useCallback(
    (
      camera: types.Camera | types.FailedCamera,
      playerRef: React.RefObject<VideoRTC>,
    ) => <CameraPlayer camera={camera} playerRef={playerRef} />,
    [],
  );

  const filteredCameras = useFilteredCameras();

  return (
    <Paper
      ref={paperRef}
      variant="outlined"
      sx={{
        width: "100%",
        height: `calc(100dvh - ${theme.headerHeight}px - ${theme.headerMargin})`,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Box sx={{ flexGrow: 1, position: "relative" }}>
        <PlayerGrid
          cameras={filteredCameras as types.Cameras}
          containerRef={paperRef}
          renderPlayer={renderPlayer}
          forceBreakpoint={true}
        />
      </Box>
    </Paper>
  );
};

const Live = () => {
  useTitle("Live");
  const [searchParams] = useSearchParams();
  const { selectSingleCamera } = useCameraStore();
  const cameras = useCameras({});

  useEffect(() => {
    if (
      cameras.data &&
      objHasValues(cameras.data) &&
      searchParams.has("camera")
    ) {
      const cameraId = searchParams.get("camera") as string;
      if (cameras.data[cameraId]) {
        selectSingleCamera(cameras.data[cameraId].identifier);
        searchParams.delete("camera");
        const newUrl = removeURLParameter(window.location.href, "camera");
        window.history.pushState({ path: newUrl }, "", newUrl);
      }
    }
  }, [cameras, searchParams, selectSingleCamera]);

  if (cameras.isPending) {
    return <Loading text="Loading Cameras" />;
  }

  if (!objHasValues<typeof cameras.data>(cameras.data)) {
    return <Loading text="Waiting for cameras to register" />;
  }

  return (
    <MenuProvider>
      <Container maxWidth={false}>
        <PlayerCard />
        <FloatingMenu />
      </Container>
    </MenuProvider>
  );
};

export default Live;
