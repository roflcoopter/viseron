import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Grow from "@mui/material/Grow";

import { Loading } from "components/loading/Loading";
import RecordingCardLatest from "components/recording/RecordingCardLatest";
import { useTitle } from "hooks/UseTitle";
import { useCameras, useCamerasFailed } from "lib/api/cameras";
import { objHasValues } from "lib/helpers";

function GridItem({
  camera_identifier,
  failed,
}: {
  camera_identifier: string;
  failed?: boolean;
}) {
  return (
    <Grow in appear key={camera_identifier}>
      <Grid
        key={camera_identifier}
        size={{
          xs: 12,
          sm: 12,
          md: 6,
          lg: 4,
          xl: 3,
        }}
      >
        <RecordingCardLatest
          camera_identifier={camera_identifier}
          failed={failed}
        />
      </Grid>
    </Grow>
  );
}

function Recordings() {
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
    <Container sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 0.5 }}>
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
}

export default Recordings;
