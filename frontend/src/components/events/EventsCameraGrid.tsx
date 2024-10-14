import Grid from "@mui/material/Grid2";
import Grow from "@mui/material/Grow";
import { useTheme } from "@mui/material/styles";

import { CameraCard } from "components/camera/CameraCard";
import { useCameraStore } from "components/events/utils";
import * as types from "lib/types";

type EventsCameraGridProps = {
  cameras: types.CamerasOrFailedCameras;
};
export function EventsCameraGrid({ cameras }: EventsCameraGridProps) {
  const theme = useTheme();
  const { selectedCameras, toggleCamera } = useCameraStore();

  const handleCameraClick = (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera | types.FailedCamera,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    toggleCamera(camera.identifier);
  };

  return (
    <Grid container spacing={0.5}>
      {cameras
        ? Object.keys(cameras)
            .sort()
            .map((camera_identifier) => (
              <Grow in appear key={camera_identifier}>
                <Grid
                  key={camera_identifier}
                  size={{
                    xs: 12,
                    sm: 12,
                    md: 6,
                    lg: 6,
                    xl: 4,
                  }}
                >
                  <CameraCard
                    camera_identifier={camera_identifier}
                    compact
                    buttons={false}
                    onClick={(
                      event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
                    ) => handleCameraClick(event, cameras[camera_identifier])}
                    border={
                      selectedCameras &&
                      selectedCameras.includes(camera_identifier)
                        ? `2px solid ${theme.palette.primary[400]}`
                        : "2px solid transparent"
                    }
                  />
                </Grid>
              </Grow>
            ))
        : null}
    </Grid>
  );
}
