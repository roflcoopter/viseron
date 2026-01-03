import { CircleFill, VideoOff } from "@carbon/icons-react";
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
        color: camera.is_recording
          ? "red"
          : camera.connected
            ? "green"
            : "gray",
        marginLeft: "4px",
      }}
    />
  ) : (
    <VideoOff
      size={12}
      style={{
        color: "white",
        marginLeft: "4px",
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

  let statusText = null;
  if (camera.failed) {
    statusText = "Camera error";
  } else if (camera.is_recording) {
    statusText = "Recording";
  } else if (!camera.connected) {
    statusText = "Disconnected";
  } else if (!camera.is_on) {
    statusText = "Camera is off";
  } else {
    statusText = null;
  }

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
      {statusText && (
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
