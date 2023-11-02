import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";
import { useTheme } from "@mui/material/styles";

import CameraCard from "components/camera/CameraCard";
import * as types from "lib/types";

type EventsCameraGridProps = {
  cameras: types.Cameras;
  changeSource: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera
  ) => void;
  selectedCamera: types.Camera | null;
};
export function EventsCameraGrid({
  cameras,
  changeSource,
  selectedCamera,
}: EventsCameraGridProps) {
  const theme = useTheme();
  return (
    <Grid container spacing={1}>
      {cameras
        ? Object.keys(cameras)
            .sort()
            .map((camera_identifier) => (
              <Grow in appear key={camera_identifier}>
                <Grid
                  item
                  xs={12}
                  sm={12}
                  md={6}
                  lg={6}
                  xl={4}
                  key={camera_identifier}
                >
                  <CameraCard
                    camera_identifier={camera_identifier}
                    compact
                    buttons={false}
                    onClick={changeSource}
                    border={
                      selectedCamera &&
                      camera_identifier === selectedCamera.identifier
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
