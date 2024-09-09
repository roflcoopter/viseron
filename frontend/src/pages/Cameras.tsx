import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";

import { CameraCard } from "components/camera/CameraCard";
import { FailedCameraCard } from "components/camera/FailedCameraCard";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
import { objHasValues } from "lib/helpers";

const Cameras = () => {
  useTitle("Cameras");
  const cameras = useCameras({});
  const failedCameras = useCamerasFailed({});

  if (cameras.isPending || failedCameras.isPending) {
    return <Loading text="Loading Cameras" />;
  }

  if (
    !(
      objHasValues<typeof cameras.data>(cameras.data) ||
      objHasValues<typeof failedCameras.data>(failedCameras.data)
    )
  ) {
    return <Loading text="Waiting for cameras to register" />;
  }

  return (
    <Container>
      <Grid container direction="row" spacing={1}>
        {failedCameras.data
          ? Object.keys(failedCameras.data)
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
                    <FailedCameraCard
                      failedCamera={failedCameras.data[camera_identifier]}
                    />
                  </Grid>
                </Grow>
              ))
          : null}
        {cameras.data
          ? Object.keys(cameras.data)
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
                    <CameraCard camera_identifier={camera_identifier} compact />
                  </Grid>
                </Grow>
              ))
          : null}
      </Grid>
    </Container>
  );
};

export default Cameras;
