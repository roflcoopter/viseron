import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardLatest from "components/recording/RecordingCardLatest";
import { useTitle } from "hooks/UseTitle";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
import { objHasValues } from "lib/helpers";

const GridItem = ({
  camera_identifier,
  failed,
}: {
  camera_identifier: string;
  failed?: boolean;
}) => (
  <Grid item xs={12} sm={12} md={6} lg={6} xl={4} key={camera_identifier}>
    <RecordingCardLatest
      camera_identifier={camera_identifier}
      failed={failed}
    />
  </Grid>
);

const Recordings = () => {
  useTitle("Recordings");

  const cameras = useCameras({});
  const failedCameras = useCamerasFailed({});

  if (cameras.isLoading || failedCameras.isLoading) {
    return <Loading text="Loading Recordings" />;
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
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        Recordings
      </Typography>
      <Grid container direction="row" spacing={2}>
        {failedCameras.data
          ? Object.keys(failedCameras.data).map((camera_identifier) => (
              <GridItem
                key={camera_identifier}
                camera_identifier={camera_identifier}
                failed
              />
            ))
          : null}
        {cameras.data
          ? Object.keys(cameras.data).map((camera_identifier) => (
              <GridItem
                key={camera_identifier}
                camera_identifier={camera_identifier}
              />
            ))
          : null}
      </Grid>
    </Container>
  );
};

export default Recordings;
