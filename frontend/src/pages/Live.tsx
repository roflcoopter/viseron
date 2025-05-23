import VideocamIcon from "@mui/icons-material/Videocam";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Fab from "@mui/material/Fab";
import Paper from "@mui/material/Paper";
import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
import { memo, useCallback, useRef, useState } from "react";

import { CameraPickerDialog } from "components/camera/CameraPickerDialog";
import { useFilteredCameras } from "components/camera/useCameraStore";
import { Loading } from "components/loading/Loading";
import { PlayerGrid } from "components/player/grid/PlayerGrid";
import { LivePlayer } from "components/player/liveplayer/LivePlayer";
import { VideoRTC } from "components/player/liveplayer/video-rtc";
import { useTitle } from "hooks/UseTitle";
import { useCameras } from "lib/api/cameras";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

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

export const PlayerCard = () => {
  const theme = useTheme();
  const paperRef: React.MutableRefObject<HTMLDivElement | null> = useRef(null);

  const renderPlayer = useCallback(
    (
      camera: types.Camera | types.FailedCamera,
      playerRef: React.RefObject<VideoRTC>,
    ) => (
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
      />
    ),
    [theme.palette.background.default],
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
  useTitle("Cameras");
  const cameras = useCameras({});

  if (cameras.isPending) {
    return <Loading text="Loading Cameras" />;
  }

  if (!objHasValues<typeof cameras.data>(cameras.data)) {
    return <Loading text="Waiting for cameras to register" />;
  }

  return (
    <Container maxWidth={false}>
      <PlayerCard />
      <FloatingMenu />
    </Container>
  );
};

export default Live;
