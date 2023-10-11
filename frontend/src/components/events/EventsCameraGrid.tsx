import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";

import CameraCard from "components/camera/CameraCard";
import * as types from "lib/types";

type EventsCameraGridProps = {
  cameras: types.Cameras;
  changeSource: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera
  ) => void;
};
export function EventsCameraGrid({
  cameras,
  changeSource,
}: EventsCameraGridProps) {
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
                  />
                </Grid>
              </Grow>
            ))
        : null}
    </Grid>
  );
}
