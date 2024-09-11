import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid2";
import Grow from "@mui/material/Grow";

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
      <RecordingCardLatest
        camera_identifier={camera_identifier}
        failed={failed}
      />
    </Grid>
  </Grow>
);

const Recordings = () => {
  useTitle("Recordings");

  const cameras = useCameras({});
  const failedCameras = useCamerasFailed({});

  if (cameras.isPending || failedCameras.isPending) {
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
      <Grid container direction="row" spacing={1}>
        {failedCameras.data
          ? Object.keys(failedCameras.data)
              .sort()
              .map((camera_identifier) => (
                <GridItem
                  key={camera_identifier}
                  camera_identifier={camera_identifier}
                  failed
                />
              ))
          : null}
        {cameras.data
          ? Object.keys(cameras.data)
              .sort()
              .map((camera_identifier) => (
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
