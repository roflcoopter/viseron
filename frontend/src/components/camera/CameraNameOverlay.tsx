import {
  CircleFill,
  VideoOff,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { SxProps, Theme } from "@mui/material/styles";

import { useCamera } from "lib/api/camera";
import * as types from "lib/types";

type CameraNameOverlayProps = {
  camera_identifier: string;
  extraStatusText?: string;
};

const overlayStyles: SxProps<Theme> = {
  position: "absolute",
  zIndex: 3,
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

function StatusIcon({ camera }: { camera: types.Camera }) {
  return camera.is_on ? (
    <CircleFill 
      size={12}
      style={{ 
        color: camera.connected ? "red" : "gray",
        marginLeft: "4px"
      }} 
    />
  ) : (
    <VideoOff 
      size={12}
      style={{ 
        color: "white",
        marginLeft: "4px"
      }} 
    />
  );
}

export function CameraNameOverlay({
  camera_identifier,
  extraStatusText,
}: CameraNameOverlayProps) {
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
          sx={{ ...cameraNameStyles, fontSize: "0.7rem", textAlign: "right" }}
        >
          {statusText}
        </Typography>
      )}
      {extraStatusText && (
        <Typography
          variant="body2"
          sx={{ ...cameraNameStyles, fontSize: "0.7rem", textAlign: "right" }}
        >
          {extraStatusText}
        </Typography>
      )}
    </Box>
  );
}
