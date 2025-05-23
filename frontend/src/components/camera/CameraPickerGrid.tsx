import Grid from "@mui/material/Grid2";
import Grow from "@mui/material/Grow";
import { useTheme } from "@mui/material/styles";

import { CameraCard } from "components/camera/CameraCard";
import {
  useCameraStore,
  useFilteredCameras,
} from "components/camera/useCameraStore";
import { useCamerasAll } from "lib/api/cameras";
import * as types from "lib/types";

export function CameraPickerGrid() {
  const theme = useTheme();
  const { toggleCamera } = useCameraStore();
  const camerasAll = useCamerasAll();
  const filteredCameras = useFilteredCameras();

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
      {Object.keys(camerasAll.combinedData)
        .sort()
        .map((camera_identifier) => (
          <Grow in appear key={camera_identifier}>
            <Grid
              key={camera_identifier}
              size={{
                xs: 6,
                sm: 6,
                md: 4,
                lg: 4,
                xl: 4,
              }}
            >
              <CameraCard
                camera_identifier={camera_identifier}
                compact
                buttons={false}
                onClick={(
                  event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
                ) =>
                  handleCameraClick(
                    event,
                    camerasAll.combinedData[camera_identifier],
                  )
                }
                border={
                  filteredCameras &&
                  Object.keys(filteredCameras).includes(camera_identifier)
                    ? `2px solid ${theme.palette.primary[400]}`
                    : "2px solid transparent"
                }
              />
            </Grid>
          </Grow>
        ))}
    </Grid>
  );
}
