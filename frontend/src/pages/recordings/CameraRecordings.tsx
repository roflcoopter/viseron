import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useContext } from "react";
import { useParams } from "react-router-dom";

import { ScrollToTopOnMount } from "components/ScrollToTop";
import { Loading } from "components/loading/Loading";
import RecordingCardDaily from "components/recording/RecordingCardDaily";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { objHasValues } from "lib/helpers";
import * as types from "lib/types";

type CameraRecordingsParams = {
  identifier: string;
};
const CameraRecordings = () => {
  const viseron = useContext(ViseronContext);
  const { identifier } = useParams<
    keyof CameraRecordingsParams
  >() as CameraRecordingsParams;
  useTitle(
    `Recordings${
      identifier && identifier in viseron.cameras
        ? ` | ${viseron.cameras[identifier].name}`
        : ""
    }`
  );

  const { status, data: recordings } = useQuery<types.RecordingsCamera>({
    queryKey: [`/recordings/${identifier}?latest&daily`],
  });

  if (status === "error") {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`Error loading recordings`}</Typography>
      </Container>
    );
  }

  if (
    status === "loading" ||
    !objHasValues<types.Cameras>(viseron.cameras) ||
    !(identifier in viseron.cameras)
  ) {
    return <Loading text="Loading Recordings" />;
  }

  const camera = viseron.cameras[identifier];

  if (!recordings || !objHasValues<types.RecordingsCamera>(recordings)) {
    return (
      <Container>
        <Typography
          variant="h5"
          align="center"
        >{`No recordings for ${camera.name}`}</Typography>
      </Container>
    );
  }

  return (
    <Container>
      <ScrollToTopOnMount />
      <Typography variant="h5" align="center">
        {camera.name}
      </Typography>
      <Grid container direction="row" spacing={2}>
        {Object.keys(recordings)
          .sort()
          .reverse()
          .map((date) => (
            <Grid item key={date} xs={12} sm={12} md={6} lg={6} xl={4}>
              <RecordingCardDaily
                camera={camera}
                recording={Object.values(recordings[date])[0]}
                date={date}
              />
            </Grid>
          ))}
      </Grid>
    </Container>
  );
};

export default CameraRecordings;
