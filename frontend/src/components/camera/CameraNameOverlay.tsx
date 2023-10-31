import Typography from "@mui/material/Typography";

import * as types from "lib/types";

type CameraNameOverlayProps = {
  camera: types.Camera;
};
export const CameraNameOverlay = ({ camera }: CameraNameOverlayProps) => (
  <Typography
    variant="uppercase"
    style={{
      textShadow: "rgba(0, 0, 0, 0.88) 0px 0px 4px",
      textTransform: "uppercase",
      fontSize: "0.7rem",
      fontWeight: 800,
      color: "white",
      position: "absolute",
      zIndex: 999,
      right: "0px",
      margin: "5px",
    }}
  >
    {camera.name}
  </Typography>
);
