import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";

import CameraCard from "components/camera/CameraCard";
import FailedCameraCard from "components/camera/FailedCameraCard";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
import { objHasValues } from "lib/helpers";

const Cameras = () => {
  useTitle("Cameras");
  const cameras = useCameras({});
  const failedCameras = useCamerasFailed({});

  if (cameras.isLoading || failedCameras.isLoading) {
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
      <Typography variant="h5" align="center">
        Cameras
      </Typography>
      <Grid container direction="row" spacing={2}>
        {failedCameras.data
          ? Object.values(failedCameras.data).map((failedCamera) => (
              <Grid
                item
                xs={12}
                sm={12}
                md={6}
                lg={6}
                xl={4}
                key={failedCamera.identifier}
              >
                <FailedCameraCard failedCamera={failedCamera} />
              </Grid>
            ))
          : null}
        {cameras.data
          ? Object.keys(cameras.data).map((camera_identifier) => (
              <Grid
                item
                xs={12}
                sm={12}
                md={6}
                lg={6}
                xl={4}
                key={camera_identifier}
              >
                <CameraCard camera_identifier={camera_identifier} />
              </Grid>
            ))
          : null}
      </Grid>
    </Container>
  );
};

export default Cameras;
