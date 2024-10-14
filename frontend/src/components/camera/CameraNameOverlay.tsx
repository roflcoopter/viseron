import CircleIcon from "@mui/icons-material/Circle";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { SxProps, Theme } from "@mui/material/styles";

import { useCamera } from "lib/api/camera";
import * as types from "lib/types";

type CameraNameOverlayProps = {
  camera_identifier: string;
};

const overlayStyles: SxProps<Theme> = {
  position: "absolute",
  zIndex: 999,
  right: "0px",
  top: "0px",
  margin: "5px",
  fontSize: "0.7rem",
  pointerEvents: "none",
  userSelect: "none",
};

const cameraNameStyles: SxProps<Theme> = {
  textShadow: "rgba(0, 0, 0, 0.88) 0px 0px 4px",
  color: "white",
};

const iconStyles: SxProps<Theme> = {
  width: "12px",
  height: "12px",
  marginLeft: 1,
};

const StatusIcon = ({ camera }: { camera: types.Camera }) =>
  camera.is_on ? (
    <CircleIcon htmlColor={camera.connected ? "red" : "gray"} sx={iconStyles} />
  ) : (
    <VideocamOffIcon htmlColor="white" sx={iconStyles} />
  );

export const CameraNameOverlay = ({
  camera_identifier,
}: CameraNameOverlayProps) => {
  const cameraQuery = useCamera(camera_identifier);
  if (!cameraQuery.data) {
    return null;
  }
  const camera = cameraQuery.data;

  const showStatusText = !camera.failed && (!camera.is_on || !camera.connected);
  const statusText =
    !camera.failed && camera.is_on ? "Disconnected" : "Camera is off";

  return (
    <Box sx={overlayStyles}>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
        }}
      >
        <Typography variant="uppercase" sx={cameraNameStyles}>
          {camera.name}
        </Typography>
        {!camera.failed && <StatusIcon camera={camera as types.Camera} />}
      </Box>
      {showStatusText && (
        <Typography
          variant="body2"
          sx={{ ...cameraNameStyles, fontSize: "0.7rem" }}
        >
          {statusText}
        </Typography>
      )}
    </Box>
  );
};
